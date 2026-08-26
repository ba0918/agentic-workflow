"""Canonical interpretation of version 2 implementation evidence."""
from __future__ import annotations

from typing import Any, NamedTuple

COMPLETIONS = {"test", "check", "artifact", "external"}

class EvidenceFailure(NamedTuple):
    code: str
    message: str

class EvidenceResult(NamedTuple):
    value: Any | None
    error: EvidenceFailure | None

    @property
    def ok(self) -> bool:
        return self.error is None

def _ok(value: Any) -> EvidenceResult:
    return EvidenceResult(value, None)

def _failure(code: str, message: str) -> EvidenceResult:
    return EvidenceResult(None, EvidenceFailure(code, message))

def _steps(value: object) -> list[dict] | None:
    if not isinstance(value, list) or not value:
        return None
    normalized: list[dict] = []
    ids: set[str] = set()
    for item in value:
        if (
            not isinstance(item, dict) or not isinstance(item.get("id"), str)
            or not item["id"] or item.get("completion") not in COMPLETIONS or item["id"] in ids
        ):
            return None
        ids.add(item["id"])
        normalized.append({"id": item["id"], "completion": item["completion"]})
    return normalized

def _valid_evidence(step: dict, event: dict) -> bool:
    kind = step["completion"]
    if kind == "test":
        return event.get("event_type") == "refactor" and event.get("exit_code") == 0
    if event.get("event_type") != kind:
        return False
    if kind in {"check", "artifact"}:
        checks = event.get("checks")
        return isinstance(checks, list) and bool(checks) and all(check.get("exit_code") == 0 for check in checks)
    return event.get("condition_met") is True

def derive_implementation(binding: object, events: object) -> EvidenceResult:
    if not isinstance(binding, dict) or not isinstance(events, list):
        return _failure("evidence_invalid", "implementation binding and events must be structured values")
    if binding.get("version") == 1 or any(isinstance(event, dict) and event.get("version") == 1 for event in events):
        return _failure("legacy_evidence_unsupported", "version 1 implementation evidence is unsupported")
    if binding.get("version") != 2:
        return _failure("evidence_invalid", "implementation binding version must be 2")
    steps = _steps(binding.get("steps"))
    if steps is None:
        return _failure("step_contract_invalid", "implementation steps are invalid")
    for expected, event in enumerate(events, 1):
        if not isinstance(event, dict) or event.get("version") != 2 or event.get("sequence") != expected:
            return _failure("evidence_invalid", "implementation events must be contiguous version 2 values")
    completed: list[str] = []
    for step in steps:
        positions = [index for index, event in enumerate(events) if event.get("step") == step["id"] and _valid_evidence(step, event)]
        if not positions:
            continue
        evidence = events[positions[-1]]
        commit_required = step["completion"] in {"test", "artifact"} or bool(evidence.get("changed_paths"))
        has_commit = any(
            event.get("event_type") == "commit" and event.get("step") == step["id"]
            for event in events[positions[-1] + 1:]
        )
        if not commit_required or has_commit:
            completed.append(step["id"])
    resume_step = next((step["id"] for step in steps if step["id"] not in completed), None)
    return _ok({
        "approval_commit": binding.get("approval_commit"), "steps": steps,
        "completed_steps": completed, "resume_step": resume_step,
    })
