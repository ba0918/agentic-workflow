#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from project_paths import resolve_project_root


SCOPE_ENVIRONMENT_VARIABLE = "AGENTIC_QUALITY_SCOPE"
SPEC_DIRECTORY = Path("docs/spec")


class GitPathError(RuntimeError):
    pass


def git_paths(project_root: Path, arguments: Sequence[str]) -> set[Path]:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        diagnostic = os.fsdecode(completed.stderr).strip()
        raise GitPathError(diagnostic or f"git exited {completed.returncode}")
    return {
        Path(os.fsdecode(value))
        for value in completed.stdout.split(b"\0")
        if value
    }


def changed_paths(project_root: Path, scope: str) -> set[Path]:
    if scope == "staged":
        return git_paths(
            project_root,
            [
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=ACMR",
                "-z",
                "--",
                str(SPEC_DIRECTORY),
            ],
        )
    tracked = git_paths(
        project_root,
        [
            "diff",
            "HEAD",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
            "--",
            str(SPEC_DIRECTORY),
        ],
    )
    untracked = git_paths(
        project_root,
        [
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            str(SPEC_DIRECTORY),
        ],
    )
    return tracked | untracked


def lintable_spec_paths(project_root: Path, scope: str) -> list[Path]:
    spec_root = (project_root / SPEC_DIRECTORY).resolve()
    selected = []
    for relative_path in changed_paths(project_root, scope):
        candidate = project_root / relative_path
        resolved = candidate.resolve()
        if (
            relative_path.suffix == ".md"
            and resolved.is_relative_to(spec_root)
            and candidate.is_file()
        ):
            selected.append(relative_path)
    return sorted(selected)


def run_textlint(project_root: Path, paths: Sequence[Path]) -> int:
    if not paths:
        return 0
    executable = project_root / "node_modules" / ".bin" / "textlint"
    completed = subprocess.run(
        [str(executable), *(str(path) for path in paths)],
        cwd=project_root,
        check=False,
    )
    return completed.returncode


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    project_root = resolve_project_root(options.root, Path(__file__))
    scope = os.environ.get(SCOPE_ENVIRONMENT_VARIABLE, "worktree")
    if scope not in {"worktree", "staged"}:
        print(f"unsupported quality scope: {scope}", file=sys.stderr)
        return 2
    try:
        paths = lintable_spec_paths(project_root, scope)
    except GitPathError as error:
        print(str(error), file=sys.stderr)
        return 2
    return run_textlint(project_root, paths)


if __name__ == "__main__":
    raise SystemExit(main())
