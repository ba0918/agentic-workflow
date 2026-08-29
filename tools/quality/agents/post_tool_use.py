#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.quality.file_checks import select_file_checks
from tools.quality.quality_gate import failure_diagnostics, run_checks


PATCH_START = "*** Begin Patch"
PATCH_FILE_LINE = re.compile(r"^\*\*\* (Add File|Update File|Move to): (.+?)\s*$")


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def patch_paths(patch: str) -> tuple[str, ...]:
    paths: list[str] = []
    for line in patch.splitlines():
        match = PATCH_FILE_LINE.match(line)
        if match is None:
            continue
        marker, path = match.groups()
        if marker == "Move to" and paths:
            paths[-1] = path
        else:
            paths.append(path)
    return tuple(dict.fromkeys(paths))


def edited_paths(hook_input: object) -> tuple[str, ...]:
    if not isinstance(hook_input, Mapping):
        return ()
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return ()
    file_path = tool_input.get("file_path")
    if isinstance(file_path, str) and file_path:
        return (file_path,)
    command = tool_input.get("command")
    if isinstance(command, str) and PATCH_START in command:
        return patch_paths(command)
    return ()


def repository_relative_path(
    path: str, project_root: Path, working_directory: Path
) -> str | None:
    resolved = (working_directory / path).resolve()
    if not resolved.is_relative_to(project_root):
        return None
    return resolved.relative_to(project_root).as_posix()


def block_response(diagnostics: Mapping[str, str]) -> dict[str, str]:
    reports = "\n\n".join(
        f"== {path} ==\n{diagnostic}" for path, diagnostic in diagnostics.items()
    )
    return {
        "decision": "block",
        "reason": "Quality checks failed for the edited files. "
        f"Fix every reported check in those files:\n\n{reports}",
    }


def hook_working_directory(hook_input: object, project_root: Path) -> Path:
    if isinstance(hook_input, Mapping) and isinstance(hook_input.get("cwd"), str):
        return Path(hook_input["cwd"])
    return project_root


def check_edited_files(hook_input: object, project_root: Path) -> dict[str, str]:
    working_directory = hook_working_directory(hook_input, project_root)
    diagnostics: dict[str, str] = {}
    for path in edited_paths(hook_input):
        relative_path = repository_relative_path(path, project_root, working_directory)
        if relative_path is None:
            continue
        failures = run_checks(
            list(select_file_checks(relative_path)), project_root, "worktree"
        )
        if failures:
            diagnostics[relative_path] = failure_diagnostics(failures)
    return diagnostics


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
    diagnostics = check_edited_files(hook_input, project_root)
    if diagnostics:
        print(json.dumps(block_response(diagnostics)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
