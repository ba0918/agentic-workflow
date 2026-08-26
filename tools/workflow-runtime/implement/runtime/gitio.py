"""Small Git process boundary."""
from pathlib import Path
import subprocess

def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)

def head_commit(root: Path) -> str | None:
    result = run_git(root, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None

def changed_documents(root: Path, old: str, new: str = "HEAD") -> list[str]:
    result = run_git(root, "diff", "--name-only", old, new, "--", "docs/")
    return sorted(result.stdout.splitlines()) if result.returncode == 0 else []
