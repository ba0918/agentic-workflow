#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence


QUALITY_DIRECTORY = Path(__file__).resolve().parents[1]


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for path_option in ("--config", "--root"):
        parser.add_argument(path_option, type=Path)
    parser.add_argument(
        "--scope", choices=("worktree", "staged", "all"), default="worktree"
    )
    return parser.parse_args(arguments)


def stop_response(exit_code: int, diagnostic: str) -> dict[str, object]:
    if exit_code == 0:
        return {"continue": True}
    return {
        "decision": "block",
        "reason": "Quality gate failed. Fix every reported check:\n\n"
        f"{diagnostic}",
    }


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    command = [
        sys.executable,
        str(QUALITY_DIRECTORY / "quality_gate.py"),
        "--scope",
        options.scope,
    ]
    if options.root is not None:
        command.extend(("--root", str(options.root)))
    if options.config is not None:
        command.extend(("--config", str(options.config)))
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    diagnostic = (completed.stdout + completed.stderr).strip()
    print(json.dumps(stop_response(completed.returncode, diagnostic)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
