"""Pure implementation-event transition rules."""
from __future__ import annotations

from typing import NamedTuple

from runtime.deps import implementation_evidence

from runtime.types import (
    COMMIT_SHA, JsonObject, RuntimeFailure, RuntimeResult, failure, object_values, ok,
)


EVENT_TYPES = {
    "worktree-bound", "red", "green", "refactor", "check", "artifact", "external",
    "commit", "human_gate", "delegated", "returned", "resumed", "rebound", "recovering",
    "resume-candidate-retired", "stopped", "implementation_green",
}
STEP_EVENTS = {"red", "green", "refactor", "check", "artifact", "external", "commit"}
TEST_EVENTS = {"red", "green", "refactor"}


class EventCandidate(NamedTuple):
    event_type: str
    fields: JsonObject
    actor: str
    derived: bool = False


def _step_contract(binding: JsonObject, step_id: str) -> JsonObject | None:
    steps = object_values(binding.get("steps")) or []
    return next((step for step in steps if step.get("id") == step_id), None)


def _events_for_step(events: list[JsonObject], step_id: str) -> list[JsonObject]:
    return [event for event in events if event.get("step") == step_id]


def _active_delegation(events: list[JsonObject]) -> bool:
    active = False
    for event in events:
        if event.get("event_type") == "delegated":
            active = True
        elif event.get("event_type") == "returned":
            active = False
    return active


def _implementation_stopped(events: list[JsonObject]) -> bool:
    stopped = False
    for event in events:
        event_type = event.get("event_type")
        if event_type == "stopped":
            stopped = True
        elif event_type in {"resumed", "rebound", "resume-candidate-retired"}:
            stopped = False
    return stopped


def _run_state_error(events: list[JsonObject], candidate: EventCandidate) -> RuntimeFailure | None:
    implementation_complete = any(
        event.get("event_type") == "implementation_green" for event in events
    )
    returning_completed_delegation = (
        implementation_complete
        and bool(events)
        and events[-1].get("event_type") == "implementation_green"
        and candidate.event_type == "returned"
        and candidate.actor == "cycle"
    )
    if implementation_complete and not returning_completed_delegation:
        return RuntimeFailure("run_already_complete", "completed implementation evidence cannot be extended")
    stopped = _implementation_stopped(events)
    returning_stopped_delegation = (
        stopped
        and candidate.event_type == "returned"
        and candidate.actor == "cycle"
    )
    if (
        stopped
        and not returning_stopped_delegation
        and candidate.event_type not in {"resumed", "rebound", "resume-candidate-retired"}
    ):
        return RuntimeFailure(
            "run_stopped", "stopped implementation must be resumed or rebound before more work"
        )
    return None


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
    if event_type in {"recovering", "stopped", "rebound"} and not str(
        fields.get("reason", "")
    ).strip():
        return RuntimeFailure("event_field_missing", f"{event_type} needs a reason")
    if event_type == "resume-candidate-retired" and not str(fields.get("reason", "")).strip():
        return RuntimeFailure(
            "event_field_missing", "logical run retirement needs a reason"
        )
    return _document_boundary_error(candidate)


def _document_boundary_error(candidate: EventCandidate) -> RuntimeFailure | None:
    event_type = candidate.event_type
    fields = candidate.fields
    if event_type == "rebound" and COMMIT_SHA.fullmatch(
        str(fields.get("approval_commit", ""))
    ) is None:
        return RuntimeFailure("event_field_invalid", "rebound needs an approval commit")
    recovering_invalid = event_type == "recovering" and "current_commit" in fields and (
        COMMIT_SHA.fullmatch(str(fields.get("current_commit", ""))) is None
        or not fields.get("changed_documents")
    )
    if recovering_invalid:
        return RuntimeFailure(
            "event_field_invalid", "document recovery needs a commit and changed documents"
        )
    if event_type == "rebound" and (
        object_values(fields.get("steps")) is None or not isinstance(fields.get("mappings"), list)
    ):
        return RuntimeFailure("event_field_invalid", "rebound needs new steps and mappings")
    return None


def _test_stage_error(
    completion: object, prior: list[JsonObject], candidate: EventCandidate,
) -> RuntimeFailure | None:
    fields = candidate.fields
    if completion != "test" or not str(fields.get("command", "")).strip():
        return RuntimeFailure(
            "stage_invalid", "test stages need a declared test step and command"
        )
    exit_code = fields.get("exit_code")
    if not isinstance(exit_code, int):
        return RuntimeFailure("stage_invalid", "test stage needs an integer exit code")
    if candidate.event_type == "red" and exit_code == 0:
        return RuntimeFailure("stage_invalid", "RED must fail")
    test_stages = [
        event.get("event_type") for event in prior if event.get("event_type") in TEST_EVENTS
    ]
    previous = test_stages[-1] if test_stages else None
    if candidate.event_type == "green" and (exit_code != 0 or previous != "red"):
        return RuntimeFailure(
            "transition_invalid", "GREEN needs a prior RED and a passing command"
        )
    if candidate.event_type == "refactor" and (exit_code != 0 or previous != "green"):
        return RuntimeFailure(
            "transition_invalid", "REFACTOR needs a prior GREEN and a passing command"
        )
    return None


def _check_stage_error(contract: JsonObject, candidate: EventCandidate) -> RuntimeFailure | None:
    event_type = candidate.event_type
    fields = candidate.fields
    if event_type != contract.get("completion"):
        return RuntimeFailure("stage_invalid", "evidence kind does not match step completion")
    if event_type == "external":
        valid = str(fields.get("summary", "")).strip() and isinstance(
            fields.get("condition_met"), bool
        )
        return None if valid else RuntimeFailure(
            "stage_invalid", "external evidence needs a bounded summary and explicit condition result"
        )
    checks = object_values(fields.get("checks"))
    invalid_checks = (
        checks is None
        or event_type == "check" and not checks
        or checks is not None and any(check.get("exit_code") != 0 for check in checks)
    )
    declared = contract.get("checks")
    commands_mismatch = (
        event_type == "check"
        and declared is not None
        and checks is not None
        and [check.get("command") for check in checks] != declared
    )
    if invalid_checks or commands_mismatch:
        return RuntimeFailure("stage_invalid", "check evidence needs successful commands")
    return None


def _commit_error(
    completion: object, prior: list[JsonObject], fields: JsonObject,
) -> RuntimeFailure | None:
    if COMMIT_SHA.fullmatch(str(fields.get("commit", ""))) is None:
        return RuntimeFailure("commit_invalid", "commit evidence needs a full Git SHA")
    safety = fields.get("safety")
    if not isinstance(safety, dict) or not all(isinstance(key, str) for key in safety):
        return RuntimeFailure(
            "commit_invalid", "commit evidence needs canonical safety results"
        )
    paths = safety.get("paths")
    unplanned = safety.get("unplanned")
    if (
        not isinstance(paths, list)
        or not all(isinstance(path, str) and path for path in paths)
        or not isinstance(unplanned, list)
    ):
        return RuntimeFailure(
            "commit_invalid", "commit evidence needs canonical safety results"
        )
    required = "refactor" if completion == "test" else completion
    if not any(event.get("event_type") == required for event in prior):
        return RuntimeFailure(
            "transition_invalid", "commit needs completed step evidence"
        )
    return None


def _step_error(
    binding: JsonObject, events: list[JsonObject], candidate: EventCandidate,
) -> RuntimeFailure | None:
    step_id = candidate.fields.get("step")
    if not isinstance(step_id, str):
        return RuntimeFailure("step_unknown", "event step is not declared by the run")
    contract = _step_contract(binding, step_id)
    if contract is None:
        return RuntimeFailure("step_unknown", "event step is not declared by the run")
    prior = _events_for_step(events, step_id)
    if candidate.event_type in TEST_EVENTS:
        return _test_stage_error(contract.get("completion"), prior, candidate)
    if candidate.event_type in {"check", "artifact", "external"}:
        return _check_stage_error(contract, candidate)
    return _commit_error(contract.get("completion"), prior, candidate.fields)


def validate_event(
    binding: JsonObject, events: list[JsonObject], candidate: EventCandidate,
) -> RuntimeResult[None]:
    if candidate.event_type not in EVENT_TYPES:
        return failure(
            "event_type_invalid", f"unsupported implementation event: {candidate.event_type}"
        )
    for event_error in (
        _run_state_error(events, candidate),
        _writer_error(binding, events, candidate),
        _boundary_error(binding, events, candidate),
        _step_error(binding, events, candidate) if candidate.event_type in STEP_EVENTS else None,
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
