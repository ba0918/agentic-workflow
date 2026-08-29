#!/usr/bin/env python3

import configparser
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.quality.quality_gate import Check, load_checks


PYTHON_ROOTS = ("tools/quality", "tools/workflow-runtime")
PYTHON_PATH = (
    "PYTHONPATH=tools/quality:tools/workflow-runtime/implement:"
    "tools/workflow-runtime/review:tools/workflow-runtime/shared"
)
UV_CACHE = "UV_CACHE_DIR=/tmp/agentic-workflow-uv-cache"


def uv_command(package: str, executable: str, *arguments: str) -> tuple[str, ...]:
    return (
        "uv",
        "run",
        "--with",
        package,
        executable,
        *arguments,
    )


def python_structure_check(*target_paths: str) -> Check:
    """Build a pylint check for the given target paths."""
    return Check(
        "python-structure",
        (
            "env",
            PYTHON_PATH,
            UV_CACHE,
            *uv_command(
                "pylint==4.0.5",
                "python",
                "-m",
                "pylint",
                "--rcfile=tools/quality/pylint.rc",
                *target_paths,
            ),
        ),
    )


def python_types_check(*target_paths: str) -> Check:
    """Build a mypy check for the given target paths."""
    return Check(
        "python-types",
        (
            "env",
            UV_CACHE,
            *uv_command(
                "mypy==1.18.2",
                "mypy",
                "--config-file",
                "tools/quality/mypy.ini",
                *target_paths,
            ),
        ),
    )


REQUIRED_PYLINT = frozenset(
    {
        "F",
        "E",
        "W",
        "invalid-name",
        "disallowed-name",
        "too-many-arguments",
        "too-many-positional-arguments",
        "too-many-locals",
        "too-many-return-statements",
        "too-many-branches",
        "too-many-statements",
        "too-many-boolean-expressions",
        "too-many-nested-blocks",
        "duplicate-code",
        "too-many-public-methods",
        "too-many-ancestors",
        "forbidden-lint-suppression",
        "forbidden-layer-import",
        "forbidden-type-escape-hatch",
        "forbidden-pure-layer-call",
    }
)
PURE_LAYER_OPTIONS = {
    "pure-layer-patterns": frozenset({
        "*/tools/workflow-runtime/review/review_model.py",
        "*/tools/workflow-runtime/shared/implementation_evidence.py",
    }),
    "pure-layer-forbidden-imports": frozenset({
        "fcntl", "os", "pathlib", "shutil", "socket", "subprocess", "tempfile",
    }),
    "pure-layer-forbidden-calls": frozenset({"input", "open", "print"}),
}
EXPECTED_CHECKS = (
    Check(
        "configuration-contract",
        ("python3", "tools/quality/configuration_contract.py"),
    ),
    python_structure_check(*PYTHON_ROOTS),
    python_types_check(*PYTHON_ROOTS),
    Check(
        "spec-textlint",
        ("python3", "tools/quality/spec_textlint.py"),
    ),
)


def _read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    with path.open(encoding="utf-8") as handle:
        parser.read_file(handle)
    return parser


def _pylint_errors(path: Path) -> list[str]:
    parser = _read_ini(path)
    errors: list[str] = []
    enabled = frozenset(
        item.strip()
        for item in parser.get("MESSAGES CONTROL", "enable", fallback="").split(",")
        if item.strip()
    )
    if enabled != REQUIRED_PYLINT:
        errors.append("Pylint enabled rules differ from the canonical set")
    if parser.get("MESSAGES CONTROL", "disable", fallback="") != "all":
        errors.append("Pylint must select its canonical rules from disable=all")
    if parser.get("MAIN", "load-plugins", fallback="") != "plugins.design_checker":
        errors.append("Pylint must load the canonical design plugin")
    for option, expected in PURE_LAYER_OPTIONS.items():
        configured = frozenset(
            item.strip()
            for item in parser.get(
                "BA0918-DESIGN", option, fallback=""
            ).split(",")
            if item.strip()
        )
        if configured != expected:
            errors.append(f"Pylint {option} differs from the canonical boundary")
    return errors


def _mypy_errors(path: Path) -> list[str]:
    parser = _read_ini(path)
    errors: list[str] = []
    if parser.sections() != ["mypy"]:
        errors.append("mypy per-module overrides are forbidden")
    required = {
        "strict": "True",
        "follow_untyped_imports": "True",
        "explicit_package_bases": "True",
    }
    for option, expected in required.items():
        if parser.get("mypy", option, fallback="") != expected:
            errors.append(f"mypy {option} must be {expected}")
    for forbidden in ("ignore_errors", "exclude"):
        if parser.has_option("mypy", forbidden):
            errors.append(f"mypy {forbidden} is forbidden")
    expected_paths = {
        "tools/workflow-runtime/brainstorm",
        "tools/workflow-runtime/plan",
        "tools/workflow-runtime/implement",
        "tools/workflow-runtime/review",
        "tools/workflow-runtime/shared",
    }
    configured_paths = set(parser.get("mypy", "mypy_path", fallback="").split(":"))
    if configured_paths != expected_paths:
        errors.append("mypy_path differs from the canonical runtime roots")
    return errors


def _check_errors(path: Path) -> list[str]:
    checks = load_checks(path)
    if tuple(checks) != EXPECTED_CHECKS:
        return ["quality checks differ from the canonical commands and roots"]
    return []


def validate_configuration(project_root: Path) -> tuple[str, ...]:
    quality_root = project_root / "tools" / "quality"
    errors = [
        *_pylint_errors(quality_root / "pylint.rc"),
        *_mypy_errors(quality_root / "mypy.ini"),
        *_check_errors(quality_root / "checks.json"),
    ]
    return tuple(errors)


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    try:
        errors = validate_configuration(project_root)
    except (configparser.Error, OSError, ValueError) as error:
        errors = (str(error),)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
