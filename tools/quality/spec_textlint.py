#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.quality.project_paths import resolve_project_root
from tools.quality.repository_snapshot import (
    SnapshotError,
    create_repository_snapshot,
    worktree_spec_paths,
)


SCOPE_ENVIRONMENT_VARIABLE = "AGENTIC_QUALITY_SCOPE"
SNAPSHOT_ENVIRONMENT_VARIABLE = "AGENTIC_QUALITY_SNAPSHOT"
SPEC_DIRECTORY = Path("docs/spec")
SUPPORTED_SCOPES = frozenset({"worktree", "staged", "all"})


def lintable_spec_paths(project_root: Path) -> list[Path]:
    spec_root = project_root / SPEC_DIRECTORY
    if not spec_root.exists():
        return []
    selected = []
    for candidate in spec_root.rglob("*.md"):
        if not stat.S_ISREG(candidate.stat(follow_symlinks=False).st_mode):
            relative = candidate.relative_to(project_root).as_posix()
            raise SnapshotError(f"{relative} is not a regular file")
        selected.append(candidate.relative_to(project_root))
    return sorted(selected)


def run_textlint(project_root: Path, paths: Sequence[Path], scope: str) -> int:
    if not paths:
        return 0
    executable = project_root / "node_modules" / ".bin" / "textlint"
    if scope == "staged":
        exit_code = 0
        for path in paths:
            completed = subprocess.run(
                [str(executable), "--stdin", "--stdin-filename", str(path)],
                cwd=project_root,
                input=(project_root / path).read_bytes(),
                check=False,
            )
            if completed.returncode != 0 and exit_code == 0:
                exit_code = completed.returncode
        return exit_code
    completed = subprocess.run(
        [str(executable), *(str(path) for path in paths)],
        cwd=project_root,
        check=False,
    )
    return completed.returncode


def lint_snapshot(project_root: Path, scope: str) -> int:
    return run_textlint(project_root, lintable_spec_paths(project_root), scope)


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    project_root = resolve_project_root(options.root, Path(__file__))
    scope = os.environ.get(SCOPE_ENVIRONMENT_VARIABLE, "worktree")
    if scope not in SUPPORTED_SCOPES:
        print(f"unsupported quality scope: {scope}", file=sys.stderr)
        return 2
    try:
        if scope == "worktree":
            return run_textlint(
                project_root,
                worktree_spec_paths(project_root),
                scope,
            )
        if os.environ.get(SNAPSHOT_ENVIRONMENT_VARIABLE) == "1":
            return lint_snapshot(project_root, scope)
        with create_repository_snapshot(project_root, scope) as snapshot:
            return lint_snapshot(snapshot.root, scope)
    except (SnapshotError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
