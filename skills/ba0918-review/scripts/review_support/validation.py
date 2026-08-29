"""Pure validation for review bindings, text, and recorded executions."""
from __future__ import annotations

from pathlib import PurePosixPath

from review_support.types import (
    COMMIT,
    SAFE_ID,
    JsonObject,
    RuntimeResult,
    failure,
    object_value,
    ok,
    string_values,
)


def _validate_execution_binding(binding: JsonObject) -> RuntimeResult[JsonObject]:
    invalid = (
        SAFE_ID.fullmatch(str(binding.get("plan_key", ""))) is None
        or SAFE_ID.fullmatch(str(binding.get("run_id", ""))) is None
        or COMMIT.fullmatch(str(binding.get("approval_commit", ""))) is None
        or not isinstance(binding.get("implement_sequence"), int)
    )
    if invalid:
        return RuntimeResult(None, failure("review_binding_invalid", "execution review binding is invalid").error)
    return ok(binding)


def _validate_standalone_binding(binding: JsonObject) -> RuntimeResult[JsonObject]:
    if binding.get("kind") != "standalone" or SAFE_ID.fullmatch(str(binding.get("review_id", ""))) is None:
        return RuntimeResult(None, failure("review_binding_invalid", "standalone review binding is invalid").error)
    review_input = object_value(binding.get("input"))
    invalid = (
        review_input is None
        or review_input.get("kind") not in {"branch", "commits"}
        or COMMIT.fullmatch(str(review_input.get("base", ""))) is None
        or COMMIT.fullmatch(str(review_input.get("head", ""))) is None
        or COMMIT.fullmatch(str(binding.get("spec_commit", ""))) is None
        or string_values(binding.get("spec_paths")) is None
    )
    if invalid:
        return RuntimeResult(None, failure("review_binding_invalid", "standalone review commit binding is invalid").error)
    assert review_input is not None
    if review_input.get("kind") == "branch" and not isinstance(review_input.get("branch"), str):
        return RuntimeResult(None, failure("review_binding_invalid", "branch review binding is invalid").error)
    unsafe_path = any(
        PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts
        for path in string_values(binding.get("spec_paths")) or []
    )
    if unsafe_path:
        return RuntimeResult(None, failure("review_binding_invalid", "review specification path is invalid").error)
    return ok(binding)


def validate_review_binding(binding: object) -> RuntimeResult[JsonObject]:
    """Validate the stable version 2 binding schema."""

    value = object_value(binding)
    if value is None or value.get("version") != 2:
        return RuntimeResult(None, failure("review_binding_invalid", "review binding must be a version 2 object").error)
    if value.get("kind") == "execution":
        return _validate_execution_binding(value)
    return _validate_standalone_binding(value)


def bounded_text(value: object, *, required: bool = True) -> RuntimeResult[str]:
    """Validate user-controlled text before it enters evidence."""

    if not isinstance(value, str):
        return RuntimeResult(None, failure("bounded_text_invalid", "review text must be a bounded string").error)
    normalized = value.strip()
    invalid = (required and not normalized) or len(normalized) > 2000 or "\x00" in normalized
    if invalid:
        return RuntimeResult(None, failure("bounded_text_invalid", "review text is empty, too long, or contains NUL").error)
    return ok(normalized)


def _safe_mapping_strings(value: JsonObject) -> RuntimeResult[None]:
    for key, item in value.items():
        checked = safe_finding_strings(item, field=key)
        if not checked.ok:
            return checked
    return ok()


def _safe_sequence_strings(value: list[object], field: str) -> RuntimeResult[None]:
    for item in value:
        checked = safe_finding_strings(item, field=field)
        if not checked.ok:
            return checked
    return ok()


def _safe_string(value: str, field: str) -> RuntimeResult[None]:
    limit = 4096 if field == "oracle" else 512 if field == "path" else 2000
    if len(value) > limit or "\x00" in value:
        return RuntimeResult(None, failure("finding_content_invalid", f"finding {field} is unsafe").error)
    candidate = PurePosixPath(value)
    if field == "path" and (candidate.is_absolute() or ".." in candidate.parts):
        return RuntimeResult(None, failure("finding_content_invalid", "finding path must be repository-relative").error)
    return ok()


def safe_finding_strings(value: object, *, field: str = "finding") -> RuntimeResult[None]:
    """Recursively validate strings stored in review evidence."""

    mapping = object_value(value)
    if mapping is not None:
        return _safe_mapping_strings(mapping)
    if isinstance(value, list):
        return _safe_sequence_strings(value, field)
    if isinstance(value, str):
        return _safe_string(value, field)
    return ok()


def review_execution(operation: str, exit_code: int, summary: str) -> RuntimeResult[JsonObject]:
    """Record a targeted-review execution exactly as the reviewer ran it."""

    checked_operation = bounded_text(operation)
    checked_summary = bounded_text(summary)
    if not checked_operation.ok:
        return RuntimeResult(None, checked_operation.error)
    if not checked_summary.ok:
        return RuntimeResult(None, checked_summary.error)
    return ok({
        "operation": checked_operation.required(),
        "working_directory": ".",
        "exit_code": exit_code,
        "summary": checked_summary.required(),
    })
