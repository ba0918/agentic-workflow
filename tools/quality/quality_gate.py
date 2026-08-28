#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.quality.project_paths import resolve_project_root
from tools.quality.repository_snapshot import SnapshotError, create_repository_snapshot


@dataclass(frozen=True)
class Check:
    name: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class CheckFailure:
    name: str
    exit_code: int
    output: str


class ConfigurationError(ValueError):
    pass


def load_checks(config_path: Path) -> list[Check]:
    document = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("checks"), list):
        raise ConfigurationError("checks must be a list")
    if not document["checks"]:
        raise ConfigurationError("no checks configured")

    checks = []
    for index, value in enumerate(document["checks"]):
        if not isinstance(value, dict):
            raise ConfigurationError(f"checks[{index}] must be an object")
        name = value.get("name")
        argv = value.get("argv")
        if not isinstance(name, str) or not name:
            raise ConfigurationError(f"checks[{index}].name must be a non-empty string")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(argument, str) or not argument for argument in argv)
        ):
            raise ConfigurationError(
                f"checks[{index}].argv must be a non-empty string list"
            )
        checks.append(Check(name=name, argv=tuple(argv)))
    return checks


def run_checks(
    checks: list[Check], working_directory: Path, scope: str
) -> list[CheckFailure]:
    failures = []
    environment = {
        **os.environ,
        "AGENTIC_QUALITY_SCOPE": scope,
        "AGENTIC_QUALITY_SNAPSHOT": "1",
    }
    for check in checks:
        try:
            completed = subprocess.run(
                check.argv,
                cwd=working_directory,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            failures.append(
                CheckFailure(
                    name=check.name,
                    exit_code=127,
                    output=str(error),
                )
            )
            continue
        if completed.returncode != 0:
            failures.append(
                CheckFailure(
                    name=check.name,
                    exit_code=completed.returncode,
                    output=(completed.stdout + completed.stderr).strip(),
                )
            )
    return failures


def failure_diagnostics(failures: list[CheckFailure]) -> str:
    return "\n\n".join(
        f"[{failure.name}] exited {failure.exit_code}\n{failure.output}"
        for failure in failures
    )


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument(
        "--scope",
        choices=("worktree", "staged", "all"),
        default="worktree",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    project_root = resolve_project_root(options.root, Path(__file__))
    try:
        with create_repository_snapshot(project_root, options.scope) as snapshot:
            config_path = (
                options.config.resolve()
                if options.config is not None
                else snapshot.root / "tools" / "quality" / "checks.json"
            )
            checks = load_checks(config_path)
            failures = run_checks(checks, snapshot.root, options.scope)
    except SnapshotError as error:
        failures = [
            CheckFailure(
                name="snapshot",
                exit_code=1,
                output=str(error),
            )
        ]
    except (ConfigurationError, json.JSONDecodeError, OSError) as error:
        failures = [
            CheckFailure(
                name="configuration",
                exit_code=1,
                output=str(error),
            )
        ]
    if failures:
        print(failure_diagnostics(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
