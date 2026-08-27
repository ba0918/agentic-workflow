#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence


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
    environment = {**os.environ, "AGENTIC_QUALITY_SCOPE": scope}
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


def stop_response(failures: list[CheckFailure]) -> dict[str, object]:
    if not failures:
        return {"continue": True}
    return {
        "decision": "block",
        "reason": f"Quality gate failed. Fix every reported check:\n\n{failure_diagnostics(failures)}",
    }


def failure_diagnostics(failures: list[CheckFailure]) -> str:
    return "\n\n".join(
        f"[{failure.name}] exited {failure.exit_code}\n{failure.output}"
        for failure in failures
    )


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", choices=("hook", "cli"), default="hook")
    parser.add_argument("--scope", choices=("worktree", "staged"), default="worktree")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    project_root = (
        options.root.resolve()
        if options.root is not None
        else Path(__file__).resolve().parents[2]
    )
    config_path = (
        options.config.resolve()
        if options.config is not None
        else project_root / ".codex" / "quality" / "checks.json"
    )
    try:
        checks = load_checks(config_path)
    except (ConfigurationError, json.JSONDecodeError, OSError) as error:
        failures = [
            CheckFailure(
                name="configuration",
                exit_code=1,
                output=str(error),
            )
        ]
    else:
        failures = run_checks(checks, project_root, options.scope)
    if options.output == "cli":
        if failures:
            print(failure_diagnostics(failures), file=sys.stderr)
            return 1
        return 0
    print(json.dumps(stop_response(failures)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
