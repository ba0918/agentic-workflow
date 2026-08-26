"""Durable JSON reads and collision-refusing writes under .agents/."""
import errno
import json
import os
import secrets
from pathlib import Path

from typing import Callable

from runtime.types import RuntimeResult, ok, failure


def classify_write_error(error: OSError) -> str:
    if isinstance(error, PermissionError) or error.errno in {errno.EACCES, errno.EPERM}:
        return "permission_required"
    if error.errno in {errno.EROFS, errno.ENOSPC, errno.EIO, errno.EDQUOT}:
        return "persistence_unavailable"
    if error.errno == errno.EEXIST:
        return "write_collision"
    return "persistence_unavailable"

def _write_through_temporary(
    path: Path,
    data: bytes,
    opener: Callable[..., int],
    place: Callable[[Path, Path], None],
) -> RuntimeResult:
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}"
        descriptor = opener(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        place(temporary, path)
        return ok(path)
    except OSError as error:
        return failure(classify_write_error(error), f"cannot persist {path.name}", str(error))
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

def write_once(
    path: Path,
    data: bytes,
    *,
    opener: Callable[..., int] = os.open,
) -> RuntimeResult:
    """Append-only: os.link refuses a target that already exists, so nothing is ever replaced."""
    return _write_through_temporary(path, data, opener, os.link)

def write_atomic(
    path: Path,
    data: bytes,
    *,
    opener: Callable[..., int] = os.open,
) -> RuntimeResult:
    """Replace a file whole, or leave the previous one. Not write_once: this file is rewritten on
    every append, and a reader must never see a half-written one."""
    return _write_through_temporary(path, data, opener, os.replace)

def safe_agent_roots(main_checkout: Path) -> RuntimeResult:
    root = main_checkout.resolve()
    paths = [
        root / ".agents",
        root / ".agents/artifacts",
        root / ".agents/tmp",
    ]
    for path in paths:
        if path.is_symlink():
            return failure("unsafe_path", f"symlink is not allowed: {path}")
        resolved = path.resolve(strict=False)
        try:
            if os.path.commonpath((str(root), str(resolved))) != str(root):
                return failure("unsafe_path", f"agent path escapes repository: {path}")
        except ValueError:
            return failure("unsafe_path", f"agent path escapes repository: {path}")
    return ok(paths)

def read_json(path: Path) -> RuntimeResult:
    if path.is_symlink() or not path.is_file():
        return failure("artifact_unavailable", f"artifact is unavailable: {path.name}")
    try:
        return ok(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        return failure("artifact_invalid", f"artifact is invalid: {path.name}", str(error))
