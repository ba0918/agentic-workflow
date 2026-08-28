"""Append-only JSON evidence storage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from runtime.types import JsonObject, RuntimeResult, failure, ok

def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

def write_once(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path

def write_atomic(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise OSError(f"refusing to replace symlink: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path

def read_json(path: Path) -> RuntimeResult[JsonObject]:
    if path.is_symlink() or not path.is_file():
        return failure("evidence_unavailable", f"evidence is unavailable: {path.name}")
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
            return failure("evidence_invalid", f"evidence is invalid: {path.name}")
        return ok({str(key): value for key, value in loaded.items()})
    except (OSError, json.JSONDecodeError) as error:
        return failure("evidence_invalid", f"evidence is invalid: {path.name}", str(error))
