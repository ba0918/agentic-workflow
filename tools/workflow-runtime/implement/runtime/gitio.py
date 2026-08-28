"""Small Git process boundary."""
from pathlib import Path
import subprocess

from runtime.types import RuntimeResult, failure, ok

def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)

def head_commit(root: Path) -> str | None:
    result = run_git(root, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None

def changed_documents(root: Path, old: str, new: str = "HEAD") -> list[str]:
    result = run_git(root, "diff", "--name-only", old, new, "--", "docs/")
    return sorted(result.stdout.splitlines()) if result.returncode == 0 else []


def run_git_bytes(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )


def staged_paths(worktree: Path) -> RuntimeResult[list[str]]:
    result = run_git(worktree, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if result.returncode != 0:
        return failure("git_inspection_failed", "staged paths could not be inspected")
    return ok(sorted(filter(None, result.stdout.splitlines())))


def commit_paths(worktree: Path, commit: str) -> RuntimeResult[list[str]]:
    if run_git(worktree, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return failure("commit_invalid", "commit evidence names a missing Git commit")
    result = run_git(
        worktree, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit
    )
    if result.returncode != 0:
        return failure("git_inspection_failed", "commit paths could not be inspected")
    return ok(sorted(filter(None, result.stdout.splitlines())))


def commits_after(worktree: Path, approval_commit: str) -> RuntimeResult[list[str]]:
    result = run_git(worktree, "rev-list", "--reverse", f"{approval_commit}..HEAD")
    if result.returncode != 0:
        return failure("git_inspection_failed", "implementation commit range could not be inspected")
    return ok(list(filter(None, result.stdout.splitlines())))
