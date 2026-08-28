"""Temporary, resumable brainstorm state."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
from collections.abc import Iterator

SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,63}\Z")
ITEM_KINDS = {"agreement", "prohibition", "undecided", "delegated", "rejected", "revision"}
SECRET = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*\S+|\bsk-[A-Za-z0-9_-]{8,}")
JSON_BLOCK = re.compile(r"\A# Brainstorm progress\n\n```json\n(?P<body>.*)\n```\n\Z", re.DOTALL)
JsonObject = dict[str, object]

class ProgressError(ValueError):
    pass

class UnsafeProgress(ProgressError):
    pass

class InvalidProgress(ProgressError):
    pass

class RevisionConflict(ProgressError):
    def __init__(self, current_path: Path, candidate_path: Path) -> None:
        super().__init__(f"revision conflict; candidate preserved at {candidate_path}")
        self.current_path = current_path
        self.candidate_path = candidate_path

def _object(value: object) -> JsonObject | None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return None
    return {str(key): item for key, item in value.items()}


def _item_errors(value: object) -> tuple[list[str], list[JsonObject], list[str]]:
    if not isinstance(value, list):
        return ["items must be a list"], [], []
    errors: list[str] = []
    items: list[JsonObject] = []
    identifiers: list[str] = []
    for index, raw_item in enumerate(value):
        item = _object(raw_item)
        if item is None:
            errors.append(f"item {index} must be an object")
            continue
        items.append(item)
        item_id = item.get("id")
        if not isinstance(item_id, str) or ITEM_ID.fullmatch(item_id) is None:
            errors.append(f"item {index} has an invalid id")
        else:
            identifiers.append(item_id)
        kind = item.get("kind")
        if kind not in ITEM_KINDS:
            errors.append(f"item {index} has an invalid kind")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"item {index} text must be non-empty")
        reason = item.get("reason")
        if kind in {"undecided", "delegated", "rejected", "revision"} and (
            not isinstance(reason, str) or not reason.strip()
        ):
            errors.append(f"item {index} needs a reason")
    return errors, items, identifiers


def _revision_errors(items: list[JsonObject], known_ids: set[str]) -> list[str]:
    errors: list[str] = []
    for index, item in enumerate(items):
        if item.get("kind") != "revision":
            continue
        replaces = item.get("replaces")
        if not isinstance(replaces, list) or not replaces or not all(
            isinstance(reference, str) for reference in replaces
        ):
            errors.append(f"revision item {index} needs replacement ids")
            continue
        references = [reference for reference in replaces if isinstance(reference, str)]
        if len(references) != len(set(references)) or any(
            reference not in known_ids or reference == item.get("id")
            for reference in references
        ):
            errors.append(f"revision item {index} references a missing item")
    return errors


def validate_state(value: JsonObject) -> tuple[str, ...]:
    errors: list[str] = []
    session_id = value.get("session_id")
    if not isinstance(session_id, str) or SESSION_ID.fullmatch(session_id) is None:
        errors.append("unsafe session id")
    revision = value.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("revision must be a positive integer")
    for field in ("current_position", "next_topic"):
        text = value.get(field)
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{field} must be non-empty text")
    item_errors, items, identifiers = _item_errors(value.get("items"))
    errors.extend(item_errors)
    if len(identifiers) != len(set(identifiers)):
        errors.append("item ids must be unique")
    errors.extend(_revision_errors(items, set(identifiers)))
    if any("identity" in key.lower() for key in value):
        errors.append("identity fields are not supported")
    return tuple(errors)

def encode_markdown(value: JsonObject) -> str:
    errors = validate_state(value)
    if errors:
        raise InvalidProgress("; ".join(errors))
    return "# Brainstorm progress\n\n```json\n" + json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n```\n"

def decode_markdown(text: str) -> JsonObject:
    match = JSON_BLOCK.fullmatch(text)
    if match is None:
        raise InvalidProgress("unsupported progress format")
    try:
        decoded: object = json.loads(match.group("body"))
    except json.JSONDecodeError as error:
        raise InvalidProgress(f"invalid progress JSON: {error.msg}") from error
    value = _object(decoded)
    if value is None:
        raise InvalidProgress("progress root must be an object")
    errors = validate_state(value)
    if errors:
        raise InvalidProgress("; ".join(errors))
    return value

def _ideas_directory(project_root: Path) -> Path:
    root = project_root.resolve()
    path = root / ".agents/tmp/ideas"
    cursor = root
    for part in Path(".agents/tmp/ideas").parts:
        cursor /= part
        if cursor.is_symlink():
            raise UnsafeProgress(f"progress path contains symlink: {cursor}")
    path.mkdir(parents=True, exist_ok=True)
    return path

def _path(project_root: Path, session_id: str) -> Path:
    if SESSION_ID.fullmatch(session_id) is None:
        raise UnsafeProgress("unsafe session id")
    target = _ideas_directory(project_root) / f"{session_id}.md"
    if target.is_symlink():
        raise UnsafeProgress(f"progress file is a symlink: {target}")
    return target

def _write_atomic(path: Path, text: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise UnsafeProgress(f"progress file became a symlink: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

@contextmanager
def _revision_lock(target: Path) -> Iterator[None]:
    lock_path = target.with_name(f".{target.stem}.lock")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise UnsafeProgress(f"cannot open revision lock: {lock_path}") from error
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

def load_progress(project_root: Path, session_id: str) -> JsonObject:
    path = _path(project_root, session_id)
    if not path.is_file():
        raise InvalidProgress(f"progress does not exist: {session_id}")
    return decode_markdown(path.read_text(encoding="utf-8"))

def _conflict_path(target: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    candidate = target.with_name(f"{target.stem}.conflict-{stamp}.md")
    suffix = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem}.conflict-{stamp}-{suffix}.md")
        suffix += 1
    return candidate


def save_progress(project_root: Path, value: JsonObject, *, expected_revision: int) -> Path:
    errors = validate_state(value)
    if errors:
        if "unsafe session id" in errors:
            raise UnsafeProgress("; ".join(errors))
        raise InvalidProgress("; ".join(errors))
    if SECRET.search(json.dumps(value, ensure_ascii=False)):
        raise UnsafeProgress("progress contains a secret-like value")
    session_id = value.get("session_id")
    if not isinstance(session_id, str):
        raise UnsafeProgress("unsafe session id")
    target = _path(project_root, session_id)
    with _revision_lock(target):
        if target.exists():
            current = decode_markdown(target.read_text(encoding="utf-8"))
            if current.get("revision") != expected_revision:
                candidate = _conflict_path(target)
                _write_atomic(candidate, encode_markdown(value))
                raise RevisionConflict(target, candidate)
        elif expected_revision != 0:
            raise InvalidProgress("expected revision does not exist")
        _write_atomic(target, encode_markdown(value))
    return target

def finish_wrap(project_root: Path, session_id: str, *, approved: bool, write_succeeded: bool) -> bool:
    if not approved or not write_succeeded:
        return False
    path = _path(project_root, session_id)
    path.unlink(missing_ok=True)
    path.with_name(f".{path.stem}.lock").unlink(missing_ok=True)
    return True
