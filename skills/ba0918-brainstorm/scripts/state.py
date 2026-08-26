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
from typing import Any

SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,63}\Z")
ITEM_KINDS = {"agreement", "prohibition", "undecided", "delegated", "rejected", "revision"}
SECRET = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*\S+|\bsk-[A-Za-z0-9_-]{8,}")
JSON_BLOCK = re.compile(r"\A# Brainstorm progress\n\n```json\n(?P<body>.*)\n```\n\Z", re.DOTALL)

class ProgressError(ValueError):
    pass

class UnsafeProgress(ProgressError):
    pass

class InvalidProgress(ProgressError):
    pass

class RevisionConflict(ProgressError):
    def __init__(self, current_path: Path, candidate_path: Path):
        super().__init__(f"revision conflict; candidate preserved at {candidate_path}")
        self.current_path = current_path
        self.candidate_path = candidate_path

def validate_state(value: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value.get("session_id"), str) or SESSION_ID.fullmatch(value["session_id"]) is None:
        errors.append("unsafe session id")
    revision = value.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("revision must be a positive integer")
    for field in ("current_position", "next_topic"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append(f"{field} must be non-empty text")
    items = value.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list")
    else:
        ids: list[str] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"item {index} must be an object")
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or ITEM_ID.fullmatch(item_id) is None:
                errors.append(f"item {index} has an invalid id")
            else:
                ids.append(item_id)
            kind = item.get("kind")
            if kind not in ITEM_KINDS:
                errors.append(f"item {index} has an invalid kind")
            if not isinstance(item.get("text"), str) or not item["text"].strip():
                errors.append(f"item {index} text must be non-empty")
            if kind in {"undecided", "delegated", "rejected", "revision"} and (
                not isinstance(item.get("reason"), str) or not item["reason"].strip()
            ):
                errors.append(f"item {index} needs a reason")
        if len(ids) != len(set(ids)):
            errors.append("item ids must be unique")
        known_ids = set(ids)
        for index, item in enumerate(items):
            if not isinstance(item, dict) or item.get("kind") != "revision":
                continue
            replaces = item.get("replaces")
            if not isinstance(replaces, list) or not replaces or any(
                not isinstance(reference, str) for reference in replaces
            ):
                errors.append(f"revision item {index} needs replacement ids")
            elif len(replaces) != len(set(replaces)) or any(
                reference not in known_ids or reference == item.get("id") for reference in replaces
            ):
                errors.append(f"revision item {index} references a missing item")
    if any("identity" in key.lower() for key in value):
        errors.append("identity fields are not supported")
    return tuple(errors)

def encode_markdown(value: dict[str, Any]) -> str:
    errors = validate_state(value)
    if errors:
        raise InvalidProgress("; ".join(errors))
    return "# Brainstorm progress\n\n```json\n" + json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n```\n"

def decode_markdown(text: str) -> dict[str, Any]:
    match = JSON_BLOCK.fullmatch(text)
    if match is None:
        raise InvalidProgress("unsupported progress format")
    try:
        value = json.loads(match.group("body"))
    except json.JSONDecodeError as error:
        raise InvalidProgress(f"invalid progress JSON: {error.msg}") from error
    if not isinstance(value, dict):
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
def _revision_lock(target: Path):
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

def load_progress(project_root: Path, session_id: str) -> dict[str, Any]:
    path = _path(project_root, session_id)
    if not path.is_file():
        raise InvalidProgress(f"progress does not exist: {session_id}")
    return decode_markdown(path.read_text(encoding="utf-8"))

def save_progress(project_root: Path, value: dict[str, Any], *, expected_revision: int) -> Path:
    errors = validate_state(value)
    if errors:
        if "unsafe session id" in errors:
            raise UnsafeProgress("; ".join(errors))
        raise InvalidProgress("; ".join(errors))
    if SECRET.search(json.dumps(value, ensure_ascii=False)):
        raise UnsafeProgress("progress contains a secret-like value")
    target = _path(project_root, value["session_id"])
    with _revision_lock(target):
        if target.exists():
            current = decode_markdown(target.read_text(encoding="utf-8"))
            if current["revision"] != expected_revision:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                candidate = target.with_name(f"{target.stem}.conflict-{stamp}.md")
                suffix = 1
                while candidate.exists():
                    candidate = target.with_name(f"{target.stem}.conflict-{stamp}-{suffix}.md")
                    suffix += 1
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
