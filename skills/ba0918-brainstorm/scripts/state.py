"""Safe persistence for resumable brainstorm meaning state."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


ALLOWED_KINDS = {"agreement", "prohibition", "undecided", "delegated", "rejected", "revision"}
SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SECRET = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*\S+|\bsk-[A-Za-z0-9_-]{8,}"
)
JSON_BLOCK = re.compile(r"\A# Brainstorm progress\n\n```json\n(?P<body>.*)\n```\n\Z", re.DOTALL)


class ProgressError(ValueError):
    """Base error for invalid or unsafe progress operations."""


class UnsafeProgress(ProgressError):
    """The requested path or content is unsafe."""


class InvalidProgress(ProgressError):
    """The progress state violates its semantic contract."""


class RevisionConflict(ProgressError):
    """A concurrent update was preserved instead of being merged."""

    def __init__(self, current_path: Path, candidate_path: Path):
        super().__init__(f"revision conflict; candidate preserved at {candidate_path}")
        self.current_path = current_path
        self.candidate_path = candidate_path


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _without_identity(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "content_identity"}


def _meaning(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"content_identity", "revision", "history"}
    }


def content_identity(value: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(_without_identity(value))).hexdigest()
    return f"sha256:{digest}"


def validate_state(value: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    session_id = value.get("session_id")
    if not isinstance(session_id, str) or SESSION_ID.fullmatch(session_id) is None:
        errors.append("unsafe session id")
    revision = value.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("revision must be a positive integer")
    for field in ("current_position", "next_topic"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append(f"{field} must be non-empty text")

    items = value.get("items")
    seen: set[str] = set()
    if not isinstance(items, list):
        errors.append("items must be a list")
    else:
        replacements: list[tuple[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                errors.append("item must be an object")
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                errors.append("item id must be non-empty text")
            elif item_id in seen:
                errors.append(f"duplicate item id: {item_id}")
            else:
                seen.add(item_id)
            kind = item.get("kind")
            if kind not in ALLOWED_KINDS:
                errors.append(f"unknown item kind: {kind}")
            if not isinstance(item.get("text"), str) or not item["text"].strip():
                errors.append(f"item {item_id} must have text")
            if kind in {"delegated", "rejected", "revision"} and not str(item.get("reason", "")).strip():
                errors.append(f"item {item_id} must have a reason")
            replaces = item.get("replaces", [])
            if not isinstance(replaces, list) or not all(isinstance(target, str) for target in replaces):
                errors.append(f"item {item_id} replaces must be a list of ids")
            else:
                replacements.extend((str(item_id), target) for target in replaces)
        for item_id, target in replacements:
            if target not in seen:
                errors.append(f"item {item_id} replaces unknown id: {target}")

    history = value.get("history")
    if not isinstance(history, list) or not history:
        errors.append("history must be a non-empty list")
    else:
        for entry in history:
            entry_revision = entry.get("revision") if isinstance(entry, dict) else None
            if isinstance(entry_revision, int) and isinstance(revision, int) and entry_revision > revision:
                errors.append(f"history revision exceeds current revision: {entry_revision}")
            if not isinstance(entry, dict) or not isinstance(entry.get("summary"), str) or not entry["summary"].strip():
                errors.append("history entry must have a summary")

    identity = value.get("content_identity")
    if identity is not None and identity != content_identity(value):
        errors.append("content identity mismatch")
    return tuple(errors)


def encode_markdown(value: dict[str, Any]) -> str:
    errors = validate_state(value)
    if errors:
        raise InvalidProgress("; ".join(errors))
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return f"# Brainstorm progress\n\n```json\n{body}\n```\n"


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


def _progress_directory(project_root: Path) -> Path:
    root = project_root.resolve()
    relative = Path(".agents/artifacts/ideas/progress")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise UnsafeProgress(f"progress path contains symlink: {cursor}")
    cursor.mkdir(parents=True, exist_ok=True)
    if not cursor.is_dir():
        raise UnsafeProgress("progress path is not a directory")
    return cursor


def _path(project_root: Path, session_id: str) -> Path:
    if SESSION_ID.fullmatch(session_id) is None:
        raise UnsafeProgress("unsafe session id")
    path = _progress_directory(project_root) / f"{session_id}.md"
    if path.is_symlink():
        raise UnsafeProgress(f"progress file is a symlink: {path}")
    return path


def _reject_secrets(value: dict[str, Any]) -> None:
    if SECRET.search(json.dumps(value, ensure_ascii=False)):
        raise UnsafeProgress("progress contains a secret-like value")


def _atomic_write(path: Path, text: str, *, replace: bool) -> None:
    if path.exists() and not replace:
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise UnsafeProgress(f"progress file became a symlink: {path}")
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError:
                return
    finally:
        temporary.unlink(missing_ok=True)


def load_progress(project_root: Path, session_id: str) -> dict[str, Any]:
    path = _path(project_root, session_id)
    if not path.is_file():
        raise InvalidProgress(f"progress does not exist: {session_id}")
    return decode_markdown(path.read_text(encoding="utf-8"))


def save_progress(project_root: Path, value: dict[str, Any], *, expected_revision: int) -> Path:
    candidate = json.loads(json.dumps(value, ensure_ascii=False))
    session_id = candidate.get("session_id", "")
    path = _path(project_root, session_id)
    _reject_secrets(candidate)
    candidate["content_identity"] = content_identity(candidate)
    errors = validate_state(candidate)
    if errors:
        raise InvalidProgress("; ".join(errors))

    if path.exists():
        current = decode_markdown(path.read_text(encoding="utf-8"))
        if current["revision"] != expected_revision:
            suffix = candidate["content_identity"].split(":", 1)[1][:12]
            conflict = path.with_name(f"{path.stem}.conflict-{suffix}.md")
            _atomic_write(conflict, encode_markdown(candidate), replace=False)
            raise RevisionConflict(path, conflict)
        if _meaning(current) == _meaning(candidate):
            return path
    elif expected_revision != 0:
        raise RevisionConflict(path, path.with_name(f"{path.stem}.conflict-missing.md"))

    if candidate["revision"] != expected_revision + 1:
        raise InvalidProgress("candidate revision must equal expected revision plus one")
    _atomic_write(path, encode_markdown(candidate), replace=True)
    return path


def finish_wrap(project_root: Path, session_id: str, *, approved: bool, write_succeeded: bool) -> bool:
    if not approved or not write_succeeded:
        return False
    path = _path(project_root, session_id)
    if not path.exists():
        return False
    path.unlink()
    return True
