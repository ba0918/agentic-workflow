from pathlib import PurePosixPath

from tools.quality.configuration_contract import (
    PYTHON_ROOTS,
    python_structure_check,
    python_types_check,
)
from tools.quality.quality_gate import Check


SPEC_DIRECTORY = "docs/spec"


def _is_canonical_python(path: PurePosixPath) -> bool:
    return path.suffix == ".py" and any(
        path.is_relative_to(root) for root in PYTHON_ROOTS
    )


def _is_spec_markdown(path: PurePosixPath) -> bool:
    return path.suffix == ".md" and path.is_relative_to(SPEC_DIRECTORY)


def _python_checks(path: str) -> tuple[Check, ...]:
    return (
        python_structure_check(path),
        python_types_check(path),
    )


def select_file_checks(relative_path: str) -> tuple[Check, ...]:
    path = PurePosixPath(relative_path)
    if _is_canonical_python(path):
        return _python_checks(relative_path)
    if _is_spec_markdown(path):
        return (Check("spec-textlint", ("node_modules/.bin/textlint", relative_path)),)
    return ()
