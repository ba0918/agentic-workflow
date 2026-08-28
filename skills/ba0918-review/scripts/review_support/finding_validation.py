"""Validate findings against an active review binding."""
from __future__ import annotations

from collections.abc import Callable

import review_model
from review_support.types import (
    JsonObject,
    RuntimeResult,
    failure,
    object_value,
    ok,
    string_values,
)
from review_support.validation import safe_finding_strings


def validate_finding_for_binding(
    binding: JsonObject,
    item: object,
    *,
    spec_commit: str | None = None,
    commit_exists: Callable[[str], bool],
) -> RuntimeResult[JsonObject]:
    """Validate a finding against the active review binding."""

    checked = review_model.validate_finding(item)
    if not checked.ok:
        assert checked.error is not None
        return RuntimeResult(None, failure(checked.error.code, checked.error.message).error)
    content = safe_finding_strings(item)
    if not content.ok:
        return RuntimeResult(None, content.error)
    finding = object_value(item)
    assert finding is not None
    options = object_value(binding.get("review_options")) or {}
    profiles = string_values(options.get("profiles")) or []
    active_commit = spec_commit or str(
        binding.get("spec_commit") or binding.get("approval_commit") or "",
    )
    specification = object_value(finding.get("specification")) or {}
    allowed_paths = string_values(binding.get("spec_paths")) or ["docs/spec/"]
    path = specification.get("path")
    allowed = isinstance(path, str) and any(
        path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/")
        for prefix in allowed_paths
    )
    mismatch = (
        finding.get("profile") not in profiles
        or finding.get("spec_commit") != active_commit
        or not allowed
        or not commit_exists(str(finding.get("spec_commit", "")))
    )
    if mismatch:
        return RuntimeResult(
            None,
            failure(
                "finding_binding_invalid",
                "finding profile or specification does not match the active review",
            ).error,
        )
    return ok(finding)
