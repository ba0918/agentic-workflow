#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.quality.file_checks import select_file_checks
from tools.quality.quality_gate import failure_diagnostics, run_checks


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def edited_path(hook_input: object) -> str | None:
    if not isinstance(hook_input, Mapping):
        return None
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return None
    file_path = tool_input.get("file_path")
    return file_path if isinstance(file_path, str) and file_path else None


def repository_relative_path(path: str, project_root: Path) -> str | None:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(project_root):
        return None
    return resolved.relative_to(project_root).as_posix()


def block_response(relative_path: str, diagnostic: str) -> dict[str, str]:
    return {
        "decision": "block",
        "reason": f"Quality checks failed for {relative_path}. "
        "Fix every reported check in that file:\n\n"
        f"{diagnostic}",
    }


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    project_root = (
        options.root.resolve() if options.root is not None else default_project_root()
    )
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"unreadable hook input: {error}", file=sys.stderr)
        return 1
    path = edited_path(hook_input)
    relative_path = (
        repository_relative_path(path, project_root) if path is not None else None
    )
    if relative_path is None:
        return 0
    failures = run_checks(
        list(select_file_checks(relative_path)), project_root, "worktree"
    )
    if failures:
        print(json.dumps(block_response(relative_path, failure_diagnostics(failures))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
