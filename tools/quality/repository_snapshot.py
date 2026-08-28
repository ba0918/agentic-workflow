from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile


PYTHON_ROOTS = (Path("tools/quality"), Path("tools/workflow-runtime"))
SPEC_ROOT = Path("docs/spec")
SUPPORTED_SCOPES = frozenset({"worktree", "staged", "all"})


class SnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositorySnapshot:
    root: Path
    scope: str


def _run_git(repository_root: Path, arguments: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        diagnostic = os.fsdecode(completed.stderr).strip()
        raise SnapshotError(diagnostic or f"git exited {completed.returncode}")
    return completed.stdout


def _git_paths(repository_root: Path, arguments: Sequence[str]) -> set[Path]:
    return {
        Path(os.fsdecode(value))
        for value in _run_git(repository_root, arguments).split(b"\0")
        if value
    }


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_worktree_path(repository_root: Path, snapshot_root: Path, path: Path) -> None:
    source = repository_root / path
    destination = snapshot_root / path
    if not source.is_symlink() and not source.exists():
        _remove_path(destination)
        return
    _remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
        return
    if stat.S_ISREG(source.stat(follow_symlinks=False).st_mode):
        shutil.copy2(source, destination, follow_symlinks=False)


def _checkout_index(repository_root: Path, snapshot_root: Path) -> None:
    prefix = f"{snapshot_root}{os.sep}"
    _run_git(
        repository_root,
        ["checkout-index", "--all", "--force", f"--prefix={prefix}"],
    )


def _overlay_tracked_worktree(repository_root: Path, snapshot_root: Path) -> None:
    tracked = _git_paths(repository_root, ["ls-files", "-z"])
    for path in tracked:
        _copy_worktree_path(repository_root, snapshot_root, path)
def _spec_candidates(repository_root: Path, scope: str) -> set[Path]:
    if scope == "worktree":
        tracked = _git_paths(
            repository_root,
            [
                "diff",
                "HEAD",
                "--name-only",
                "--diff-filter=ACMRT",
                "-z",
                "--",
                SPEC_ROOT.as_posix(),
            ],
        )
        untracked = _git_paths(
            repository_root,
            [
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                SPEC_ROOT.as_posix(),
            ],
        )
        return tracked | untracked
    if scope == "staged":
        return _git_paths(
            repository_root,
            [
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=ACMRT",
                "-z",
                "--",
                SPEC_ROOT.as_posix(),
            ],
        )
    return _git_paths(
        repository_root,
        ["ls-files", "-z", "--", SPEC_ROOT.as_posix()],
    )


def _prune_spec_markdown(snapshot_root: Path, candidates: set[Path]) -> None:
    spec_root = snapshot_root / SPEC_ROOT
    if not spec_root.exists():
        return
    markdown = set(spec_root.rglob("*.md"))
    selected = {snapshot_root / path for path in candidates if path.suffix == ".md"}
    for path in markdown - selected:
        _remove_path(path)


def _regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)
    except FileNotFoundError:
        return False


def _validate_python_sources(snapshot_root: Path) -> None:
    for relative_root in PYTHON_ROOTS:
        root = snapshot_root / relative_root
        if root.is_symlink():
            raise SnapshotError(
                f"{relative_root.as_posix()} is not a regular directory"
            )
        if not root.exists():
            continue
        if not stat.S_ISDIR(root.stat(follow_symlinks=False).st_mode):
            raise SnapshotError(
                f"{relative_root.as_posix()} is not a regular directory"
            )
        for current_root, directories, files in os.walk(root, followlinks=False):
            current = Path(current_root)
            for directory in directories:
                candidate = current / directory
                if candidate.is_symlink() or not stat.S_ISDIR(
                    candidate.stat(follow_symlinks=False).st_mode
                ):
                    relative = candidate.relative_to(snapshot_root).as_posix()
                    raise SnapshotError(f"{relative} is not a regular directory")
            for filename in files:
                source = current / filename
                if source.suffix == ".py" and not _regular_file(source):
                    relative = source.relative_to(snapshot_root).as_posix()
                    raise SnapshotError(f"{relative} is not a regular file")


def _validate_spec_sources(snapshot_root: Path, candidates: set[Path]) -> None:
    for relative in sorted(path for path in candidates if path.suffix == ".md"):
        if not _regular_file(snapshot_root / relative):
            raise SnapshotError(f"{relative.as_posix()} is not a regular file")


def worktree_spec_paths(repository_root: Path) -> list[Path]:
    resolved_root = repository_root.resolve()
    candidates = _spec_candidates(resolved_root, "worktree")
    _validate_spec_sources(resolved_root, candidates)
    return sorted(path for path in candidates if path.suffix == ".md")


def _link_dependencies(repository_root: Path, snapshot_root: Path) -> None:
    dependencies = repository_root / "node_modules"
    destination = snapshot_root / "node_modules"
    if dependencies.is_dir() and not destination.exists():
        destination.symlink_to(dependencies, target_is_directory=True)


@contextmanager
def create_repository_snapshot(
    repository_root: Path,
    scope: str,
) -> Iterator[RepositorySnapshot]:
    if scope not in SUPPORTED_SCOPES:
        raise SnapshotError(f"unsupported quality scope: {scope}")
    resolved_root = repository_root.resolve()
    if scope == "worktree":
        _validate_python_sources(resolved_root)
        yield RepositorySnapshot(root=resolved_root, scope=scope)
        return
    with tempfile.TemporaryDirectory(prefix="agentic-quality-") as directory:
        snapshot_root = Path(directory)
        _checkout_index(resolved_root, snapshot_root)
        if scope == "all":
            _overlay_tracked_worktree(resolved_root, snapshot_root)
        candidates = _spec_candidates(resolved_root, scope)
        _prune_spec_markdown(snapshot_root, candidates)
        _validate_python_sources(snapshot_root)
        _validate_spec_sources(snapshot_root, candidates)
        _link_dependencies(resolved_root, snapshot_root)
        yield RepositorySnapshot(root=snapshot_root, scope=scope)
