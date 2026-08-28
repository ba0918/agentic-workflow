"""Filesystem and changed-content safety checks."""
from pathlib import Path
from typing import Mapping

from runtime.gitio import run_git, run_git_bytes
from runtime.secret_detect import contains_secret
from runtime.staging import assess_paths
from runtime.types import JsonObject, Run, RuntimeResult, failure, ok


def worktree(binding: JsonObject, run: Run) -> Path:
    value = binding.get("worktree")
    return Path(value) if isinstance(value, str) and value else run.root


def content_safety(
    checkout: Path,
    paths: list[str],
    *,
    index: bool = False,
    commit: str | None = None,
    working_tree: bool = False,
) -> RuntimeResult[None]:
    for path in paths:
        tracked = run_git(checkout, "ls-files", "--error-unmatch", "--", path).returncode == 0
        if working_tree and not tracked:
            result = _untracked_content(checkout, path)
        else:
            result = _diff_content(
                checkout, path, index=index, commit=commit, working_tree=working_tree
            )
        if not result.ok:
            error = result.error
            if error is None:
                return failure("git_inspection_failed", "changed content could not be inspected")
            return failure(error.code, error.message, error.detail)
        if contains_secret(result.required()):
            return failure("secret_content", "secret-shaped content is not allowed", path)
    return ok(None)


def _untracked_content(checkout: Path, path: str) -> RuntimeResult[bytes]:
    try:
        return ok((checkout / path).read_bytes())
    except OSError:
        return failure(
            "git_inspection_failed", "untracked content could not be inspected", path
        )


def _diff_content(
    checkout: Path,
    path: str,
    *,
    index: bool,
    commit: str | None,
    working_tree: bool,
) -> RuntimeResult[bytes]:
    if working_tree:
        content = run_git_bytes(checkout, "diff", "--unified=0", "--", path)
    elif index:
        content = run_git_bytes(checkout, "diff", "--cached", "--unified=0", "--", path)
    else:
        content = run_git_bytes(
            checkout, "show", "--format=", "--unified=0", commit or "", "--", path
        )
    if content.returncode != 0:
        return failure(
            "git_inspection_failed", "changed diff content could not be inspected", path
        )
    added = b"\n".join(
        line[1:]
        for line in content.stdout.splitlines()
        if line.startswith(b"+") and not line.startswith(b"+++")
    )
    return ok(added)


def assess_safety(
    binding: JsonObject,
    paths: list[str],
    reasons: Mapping[str, str] | None = None,
) -> RuntimeResult[JsonObject]:
    expected = binding.get("expected_paths")
    expected_paths = [path for path in expected if isinstance(path, str)] if isinstance(
        expected, list
    ) else []
    assessed = assess_paths(paths, expected_paths=expected_paths, reasons=reasons or {})
    if not assessed.ok:
        return assessed
    value = assessed.required()
    return ok({"paths": value["paths"], "unplanned": value["unplanned"]})


def test_bytes(checkout: Path, paths: list[str]) -> RuntimeResult[dict[str, bytes]]:
    values: dict[str, bytes] = {}
    for relative in paths:
        target = checkout / relative
        if target.is_symlink() or not target.is_file():
            return failure(
                "frozen_red_unavailable", f"test or fixture is unavailable: {relative}"
            )
        values[relative] = target.read_bytes()
    return ok(values)
