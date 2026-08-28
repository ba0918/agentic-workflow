"""Git and filesystem boundaries for review evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol

from review_support.types import COMMIT, JsonObject, RuntimeResult, failure, object_value, ok
from review_support.validation import validate_review_binding


class BinarySyncHandle(Protocol):
    """Minimal binary file interface needed by atomic evidence writes."""

    def write(self, data: bytes) -> int:
        """Write bytes and return the number accepted."""

    def flush(self) -> None:
        """Flush buffered bytes."""

    def fileno(self) -> int:
        """Return the operating-system file descriptor."""


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run Git without raising so callers can map failures to stable errors."""

    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def commit(root: Path, reference: str | None) -> RuntimeResult[str]:
    """Resolve an existing commit reference."""

    if not reference:
        return RuntimeResult(None, failure("commit_not_found", "Git commit reference is missing").error)
    result = git(root, "rev-parse", "--verify", f"{reference}^{{commit}}")
    value = result.stdout.strip()
    if result.returncode != 0 or COMMIT.fullmatch(value) is None:
        return RuntimeResult(None, failure("commit_not_found", f"Git commit does not exist: {reference}").error)
    return ok(value)


def default_branch(root: Path) -> RuntimeResult[str]:
    """Resolve the unique default branch without guessing among candidates."""

    remote = git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if remote.returncode == 0 and remote.stdout.strip():
        return ok(remote.stdout.strip())
    candidates = {
        name
        for name in ("main", "master", "trunk")
        if git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0
    }
    if len(candidates) != 1:
        return RuntimeResult(None, failure("comparison_base_required", "default branch is not unique").error)
    return ok(next(iter(candidates)))


def changed_paths(root: Path, start: str, end: str) -> RuntimeResult[list[str]]:
    """List paths changed in a commit range."""

    result = git(root, "diff", "--name-only", start, end)
    if result.returncode != 0:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation changed paths are unavailable").error)
    return ok(sorted(filter(None, result.stdout.splitlines())))


def uncommitted_paths(worktree: Path) -> RuntimeResult[list[str]]:
    """Decode all paths represented by porcelain-v1 status."""

    result = git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if result.returncode != 0:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation worktree status is unavailable").error)
    paths: set[str] = set()
    records = iter(result.stdout.split("\0"))
    for record in records:
        if len(record) < 4:
            continue
        paths.add(record[3:])
        if "R" in record[:2] or "C" in record[:2]:
            renamed = next(records, "")
            if not renamed:
                return RuntimeResult(None, failure("execution_input_invalid", "implementation rename status is incomplete").error)
            paths.add(renamed)
    return ok(sorted(paths))


def read_object(path: Path, code: str, message: str) -> RuntimeResult[JsonObject]:
    """Read a JSON object from a trusted, already-bounded path."""

    try:
        value = object_value(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        value = None
    if value is None:
        return RuntimeResult(None, failure(code, message).error)
    return ok(value)


def review_directory(root: Path, binding: JsonObject) -> Path:
    """Resolve a binding's symlink-free evidence directory."""

    repository = root.resolve()
    checked = validate_review_binding(binding)
    if not checked.ok:
        raise ValueError(checked.required_error().message)
    if binding["kind"] == "execution":
        path = repository / ".agents/evidence" / str(binding["plan_key"]) / str(binding["run_id"]) / "review"
    else:
        path = repository / ".agents/evidence/reviews" / str(binding["review_id"])
    cursor = repository
    for part in path.relative_to(repository).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"symlink is not allowed: {cursor}")
    resolved = path.resolve()
    evidence_root = (repository / ".agents/evidence").resolve()
    if not resolved.is_relative_to(evidence_root):
        raise ValueError("review directory is outside the evidence store")
    return resolved


def write_once(path: Path, value: JsonObject) -> None:
    """Atomically create canonical JSON without replacing existing evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            _write_and_sync(handle, data)
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_and_sync(handle: BinarySyncHandle, data: bytes) -> None:
    handle.write(data)
    handle.flush()
    os.fsync(handle.fileno())
