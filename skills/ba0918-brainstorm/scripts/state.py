"""Temporary, resumable brainstorm state."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
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
    if not isinstance(value.get("items"), list):
        errors.append("items must be a list")
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
    return True
