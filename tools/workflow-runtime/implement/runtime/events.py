"""Pure implementation-event transition rules."""
from __future__ import annotations

from typing import NamedTuple

from runtime.deps import implementation_evidence

from runtime.types import (
    JsonObject, RuntimeFailure, RuntimeResult, failure, ok,
)


EVENT_TYPES = {
    "worktree-bound", "red", "green", "refactor", "check", "artifact", "external",
    "commit", "human_gate", "delegated", "returned", "resumed", "rebound", "recovering",
    "resume-candidate-retired", "stopped", "implementation_green",
}
STEP_EVENTS = {"red", "green", "refactor", "check", "artifact", "external", "commit"}


class EventCandidate(NamedTuple):
    event_type: str
    fields: JsonObject
    actor: str
    derived: bool = False


def _active_delegation(events: list[JsonObject]) -> bool:
    active = False
    for event in events:
        if event.get("event_type") == "delegated":
            active = True
        elif event.get("event_type") == "returned":
            active = False
    return active


def _writer_error(
    binding: JsonObject, events: list[JsonObject], candidate: EventCandidate,
) -> RuntimeFailure | None:
    active = _active_delegation(events)
    if candidate.actor == "cycle":
        allowed = binding.get("delegated") is True and (
            candidate.event_type == "worktree-bound" and not events
            or candidate.event_type == "delegated" and not active
            or candidate.event_type == "returned" and active
            or candidate.event_type in {"resumed", "resume-candidate-retired"} and not active
        )
        if not allowed:
            return RuntimeFailure(
                "writer_not_allowed", "cycle writes only delegation and resume-control boundaries"
            )
    elif candidate.actor != "implement":
        return RuntimeFailure("writer_not_allowed", "unknown evidence writer")
    elif candidate.event_type in {"delegated", "returned"}:
        return RuntimeFailure(
            "writer_not_allowed", "cycle is the only writer of delegation boundaries"
        )
    elif binding.get("delegated") is True and not active:
        return RuntimeFailure(
            "writer_not_allowed", "implement writes delegated evidence only during active delegation"
        )
    return None


def _boundary_error(
    binding: JsonObject, events: list[JsonObject], candidate: EventCandidate,
) -> RuntimeFailure | None:
    event_type = candidate.event_type
    fields = candidate.fields
    if event_type == "implementation_green" and not candidate.derived:
        return RuntimeFailure(
            "event_not_recordable", "implementation_green is derived by complete_run"
        )
    if event_type == "worktree-bound" and (
        events
        or fields.get("branch") != binding.get("branch")
        or fields.get("worktree") != binding.get("worktree")
    ):
        return RuntimeFailure(
            "worktree_binding_invalid", "worktree-bound must be the first event and match binding"
        )
    if event_type == "delegated" and any(
        not isinstance(fields.get(name), str) or not fields[name] for name in ("role", "model")
    ):
        return RuntimeFailure(
            "event_field_missing", "delegated must record the runner (role) and the model"
        )
    return None


def _candidate_event(events: list[JsonObject], candidate: EventCandidate) -> JsonObject:
    return {
        **candidate.fields,
        "version": 2,
        "sequence": len(events) + 1,
        "event_type": candidate.event_type,
        "writer": candidate.actor,
    }


def _mapped_reducer_error(
    candidate: EventCandidate, error: RuntimeFailure | None,
) -> RuntimeFailure:
    if error is None:
        return RuntimeFailure("implementation_evidence_invalid", "implementation evidence is invalid")
    event_type = candidate.event_type
    if error.code == "evidence_invalid":
        return _invalid_event_error(candidate, error)
    stage_transition = (
        event_type in {"red", "check", "artifact", "external"}
        or event_type in {"green", "refactor"}
        and error.message == "test stage belongs to a non-test step"
    )
    if error.code == "transition_invalid" and stage_transition:
        return RuntimeFailure("stage_invalid", error.message)
    return error


def _invalid_event_error(
    candidate: EventCandidate, error: RuntimeFailure,
) -> RuntimeFailure:
    event_type = candidate.event_type
    if event_type in STEP_EVENTS and not isinstance(candidate.fields.get("step"), str):
        return RuntimeFailure("step_unknown", "event step is not declared by the run")
    if event_type == "commit":
        return RuntimeFailure("commit_invalid", error.message)
    if event_type in {"red", "green", "refactor", "check", "artifact", "external"}:
        return RuntimeFailure("stage_invalid", error.message)
    return _invalid_boundary_error(event_type, error)


def _invalid_boundary_error(event_type: str, error: RuntimeFailure) -> RuntimeFailure:
    if event_type in {"recovering", "rebound", "resumed"}:
        return RuntimeFailure("event_field_invalid", error.message)
    if event_type in {"stopped", "resume-candidate-retired"}:
        return RuntimeFailure("event_field_missing", error.message)
    return error


def _reducer_error(
    binding: JsonObject, events: list[JsonObject], candidate: EventCandidate,
) -> RuntimeFailure | None:
    derived = derive_implementation(binding, [*events, _candidate_event(events, candidate)])
    if derived.ok:
        return None
    return _mapped_reducer_error(candidate, derived.error)


def validate_event(
    binding: JsonObject, events: list[JsonObject], candidate: EventCandidate,
) -> RuntimeResult[None]:
    if candidate.event_type not in EVENT_TYPES:
        return failure(
            "event_type_invalid", f"unsupported implementation event: {candidate.event_type}"
        )
    for event_error in (
        _writer_error(binding, events, candidate),
        _boundary_error(binding, events, candidate),
        _reducer_error(binding, events, candidate),
    ):
        if event_error is not None:
            return failure(event_error.code, event_error.message, event_error.detail)
    return ok(None)


def derive_implementation(
    binding: JsonObject, event_values: list[JsonObject],
) -> RuntimeResult[JsonObject]:
    derived = implementation_evidence.derive_implementation(binding, event_values)
    if not derived.ok or derived.value is None:
        error = derived.error
        code = error.code if error is not None else "implementation_evidence_invalid"
        message = error.message if error is not None else "implementation evidence is invalid"
        return failure(code, message)
    return ok(derived.value)
