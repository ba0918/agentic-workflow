"""Repository-side execution setup."""
from pathlib import Path
from runtime.gitio import run_git
from runtime.types import RuntimeResult, failure, ok

def repository_root(path: Path) -> RuntimeResult:
    result = run_git(path, "rev-parse", "--show-toplevel")
    if result.returncode:
        return failure("repository_unavailable", "path is not in a Git repository", result.stderr.strip())
    return ok(Path(result.stdout.strip()).resolve())
