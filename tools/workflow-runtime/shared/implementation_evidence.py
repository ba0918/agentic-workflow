"""Canonical interpretation of version 2 implementation evidence."""
from __future__ import annotations

import re
from typing import NamedTuple


JsonObject = dict[str, object]
COMPLETIONS = {"test", "check", "artifact", "external"}
STEP_EVENTS = {"red", "green", "refactor", "check", "artifact", "external", "commit"}
SHA = re.compile(r"[0-9a-f]{40,64}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class EvidenceFailure(NamedTuple):
    code: str
    message: str


class EvidenceResult(NamedTuple):
    value: JsonObject | None
    error: EvidenceFailure | None

    @property
    def ok(self) -> bool:
        return self.error is None

    def required(self) -> JsonObject:
        if self.value is None:
            raise RuntimeError("implementation evidence result has no value")
        return self.value

    def required_error(self) -> EvidenceFailure:
        if self.error is None:
            raise RuntimeError("implementation evidence result has no failure")
        return self.error


def _ok(value: JsonObject) -> EvidenceResult:
    return EvidenceResult(value, None)


def _failure(code: str, message: str) -> EvidenceResult:
    return EvidenceResult(None, EvidenceFailure(code, message))


def _object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    normalized: JsonObject = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        normalized[key] = item
    return normalized


def _objects(value: object) -> list[JsonObject] | None:
    if not isinstance(value, list):
        return None
    normalized: list[JsonObject] = []
    for item in value:
        object_value = _object(item)
        if object_value is None:
            return None
        normalized.append(object_value)
    return normalized


def _text(value: JsonObject, field_name: str) -> str | None:
    candidate = value.get(field_name)
    return candidate if isinstance(candidate, str) and candidate else None


def _steps(value: object) -> list[JsonObject] | None:
    candidates = _objects(value)
    if candidates is None:
        return None
    normalized: list[JsonObject] = []
    identifiers: set[str] = set()
    for item in candidates:
        step_id = _text(item, "id")
        completion = _text(item, "completion")
        if step_id is None or completion not in COMPLETIONS or step_id in identifiers:
            return None
        checks = item.get("checks")
        if not _valid_declared_checks(completion, checks):
            return None
        identifiers.add(step_id)
        step: JsonObject = {"id": step_id, "completion": completion}
        if isinstance(checks, list):
            step["checks"] = list(checks)
        normalized.append(step)
    return normalized


def _valid_declared_checks(completion: str, value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    if completion != "check":
        return not value
    return bool(value) and all(isinstance(command, str) and command for command in value)


def _declared_checks_match(step: JsonObject, checks: list[JsonObject]) -> bool:
    declared = step.get("checks")
    return declared is None or [check.get("command") for check in checks] == declared


def _valid_evidence(step: JsonObject, event: JsonObject) -> bool:
    completion = _text(step, "completion")
    event_type = _text(event, "event_type")
    if completion == "test":
        return event_type == "refactor" and event.get("exit_code") == 0
    if event_type != completion:
        return False
    if completion not in {"check", "artifact"}:
        return event.get("condition_met") is True
    checks = _objects(event.get("checks"))
    if checks is None or completion == "check" and not checks:
        return False
    succeeded = all(check.get("exit_code") == 0 for check in checks)
    return succeeded and (completion != "check" or _declared_checks_match(step, checks))


def _completed_steps(steps: list[JsonObject], events: list[JsonObject]) -> set[str]:
    completed: set[str] = set()
    for step in steps:
        step_id = _text(step, "id")
        if step_id is None:
            continue
        positions = [
            index
            for index, event in enumerate(events)
            if event.get("step") == step_id and _valid_evidence(step, event)
        ]
        if positions and _completion_has_commit(step, events, positions[-1]):
            completed.add(step_id)
    return completed


def _completion_has_commit(
    step: JsonObject,
    events: list[JsonObject],
    evidence_position: int,
) -> bool:
    evidence = events[evidence_position]
    completion = _text(step, "completion")
    commit_required = completion in {"test", "artifact"} or bool(
        evidence.get("changed_paths")
    )
    if not commit_required:
        return True
    step_id = _text(step, "id")
    return any(
        event.get("event_type") == "commit" and event.get("step") == step_id
        for event in events[evidence_position + 1 :]
    )


def _mapping(
    old_steps: list[JsonObject],
    new_steps: list[JsonObject],
    value: object,
) -> dict[str, str] | None:
    candidates = _objects(value)
    if candidates is None:
        return None
    old = {_text(step, "id"): _text(step, "completion") for step in old_steps}
    new = {_text(step, "id"): _text(step, "completion") for step in new_steps}
    mapping: dict[str, str] = {}
    targets: set[str] = set()
    for item in candidates:
        old_id = _text(item, "old")
        new_id = _text(item, "new")
        if old_id is None or new_id is None:
            return None
        if (
            old_id not in old
            or new_id not in new
            or old_id in mapping
            or new_id in targets
            or old[old_id] != new[new_id]
        ):
            return None
        mapping[old_id] = new_id
        targets.add(new_id)
    return mapping


def _safe_paths(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(path, str) and path for path in value
    )


def _snapshot(value: object) -> bool:
    snapshot = _object(value)
    if snapshot is None:
        return False
    files = _object(snapshot.get("files"))
    command = _text(snapshot, "command")
    if files is None or command is None or DIGEST.fullmatch(command) is None:
        return False
    return all(
        path and isinstance(digest, str) and DIGEST.fullmatch(digest) is not None
        for path, digest in files.items()
    )


def _valid_test_event(event: JsonObject) -> bool:
    return (
        _text(event, "step") is not None
        and _text(event, "command") is not None
        and isinstance(event.get("exit_code"), int)
        and _snapshot(event.get("snapshot"))
    )


def _valid_check_event(event: JsonObject, event_type: str) -> bool:
    checks = _objects(event.get("checks"))
    if _text(event, "step") is None or checks is None:
        return False
    if event_type == "check" and not checks:
        return False
    return all(isinstance(check.get("exit_code"), int) for check in checks) and _safe_paths(
        event.get("changed_paths")
    )


def _valid_external_event(event: JsonObject) -> bool:
    return (
        _text(event, "step") is not None
        and isinstance(event.get("condition_met"), bool)
        and _text(event, "checked") is not None
        and _text(event, "summary") is not None
        and _safe_paths(event.get("changed_paths"))
    )


def _valid_commit_event(event: JsonObject) -> bool:
    safety = _object(event.get("safety"))
    commit = _text(event, "commit")
    return (
        _text(event, "step") is not None
        and commit is not None
        and SHA.fullmatch(commit) is not None
        and safety is not None
        and _safe_paths(safety.get("paths"))
        and isinstance(safety.get("unplanned"), list)
    )


def _valid_step_event(event: JsonObject, event_type: str) -> bool | None:
    if event_type in {"red", "green", "refactor"}:
        return _valid_test_event(event)
    if event_type in {"check", "artifact"}:
        return _valid_check_event(event, event_type)
    if event_type == "external":
        return _valid_external_event(event)
    if event_type == "commit":
        return _valid_commit_event(event)
    return None


def _valid_document_event(event: JsonObject, event_type: str) -> bool | None:
    if event_type == "recovering":
        commit = _text(event, "current_commit")
        return (
            commit is not None
            and SHA.fullmatch(commit) is not None
            and _safe_paths(event.get("changed_documents"))
            and _text(event, "reason") is not None
        )
    if event_type == "rebound":
        commit = _text(event, "approval_commit")
        return (
            commit is not None
            and SHA.fullmatch(commit) is not None
            and _text(event, "reason") is not None
        )
    return None


def _valid_resume_event(event: JsonObject, event_type: str) -> bool | None:
    if event_type == "resumed":
        branch_head = _text(event, "branch_head")
        return (
            branch_head is not None
            and SHA.fullmatch(branch_head) is not None
            and _safe_paths(event.get("unexplained_commits"))
            and _safe_paths(event.get("uncommitted_paths"))
        )
    if event_type in {"stopped", "resume-candidate-retired", "human_gate"}:
        return _text(event, "reason") is not None
    return None


def _valid_boundary_event(event: JsonObject, event_type: str) -> bool:
    document_result = _valid_document_event(event, event_type)
    if document_result is not None:
        return document_result
    resume_result = _valid_resume_event(event, event_type)
    if resume_result is not None:
        return resume_result
    if event_type == "implementation_green":
        return _safe_paths(event.get("completed_steps")) and _safe_paths(
            event.get("uncommitted_outside_scope", [])
        )
    if event_type == "worktree-bound":
        return _text(event, "branch") is not None and _text(event, "worktree") is not None
    if event_type in {"delegated", "returned"}:
        field_name = "role" if event_type == "delegated" else "outcome"
        return field_name not in event or isinstance(event[field_name], str)
    return False


def _valid_event(event: JsonObject) -> bool:
    event_type = _text(event, "event_type")
    if event_type is None:
        return False
    step_result = _valid_step_event(event, event_type)
    return step_result if step_result is not None else _valid_boundary_event(event, event_type)


class _Derivation:
    def __init__(self, active_steps: list[JsonObject], approval_commit: object) -> None:
        self.active_steps = active_steps
        self.approval_commit = approval_commit
        self.completed: set[str] = set()
        self.segment: list[JsonObject] = []
        self.segments: list[JsonObject] = []
        self.test_stages: dict[str, str] = {}
        self.red_snapshots: dict[str, object] = {}
        self.stopped = False
        self.resume_candidate_retired = False


def _step_contract(state: _Derivation, event: JsonObject) -> JsonObject | None:
    event_step = _text(event, "step")
    return next(
        (step for step in state.active_steps if _text(step, "id") == event_step),
        None,
    )


def _step_order_valid(
    state: _Derivation,
    contract: JsonObject,
) -> bool:
    completed_now = state.completed | _completed_steps(state.active_steps, state.segment)
    next_step = next(
        (
            _text(step, "id")
            for step in state.active_steps
            if _text(step, "id") not in completed_now
        ),
        None,
    )
    contract_id = _text(contract, "id")
    contract_index = state.active_steps.index(contract)
    prior_incomplete = any(
        _text(step, "id") not in completed_now
        for step in state.active_steps[:contract_index]
    )
    return contract_id in completed_now or contract_id == next_step or not prior_incomplete


def _apply_test_stage(
    state: _Derivation,
    contract: JsonObject,
    event: JsonObject,
    event_type: str,
) -> EvidenceFailure | None:
    if _text(contract, "completion") != "test":
        return EvidenceFailure("transition_invalid", "test stage belongs to a non-test step")
    contract_id = _text(contract, "id")
    if contract_id is None:
        return EvidenceFailure("transition_invalid", "test stage has no step")
    previous = state.test_stages.get(contract_id)
    exit_code = event.get("exit_code")
    valid = (
        event_type == "red" and exit_code != 0
        or event_type == "green" and exit_code == 0 and previous == "red"
        or event_type == "refactor" and exit_code == 0 and previous == "green"
    )
    if not valid:
        return EvidenceFailure("transition_invalid", "test stages must follow RED, GREEN, REFACTOR")
    snapshot = event.get("snapshot")
    if event_type == "red":
        state.red_snapshots[contract_id] = snapshot
    elif snapshot != state.red_snapshots.get(contract_id):
        return EvidenceFailure("frozen_red_mismatch", "GREEN and REFACTOR must use the accepted RED snapshot")
    state.test_stages[contract_id] = event_type
    return None


def _stage_evidence_valid(contract: JsonObject, event: JsonObject, event_type: str) -> bool:
    completion = _text(contract, "completion")
    if event_type == "external":
        return completion == "external"
    if event_type not in {"check", "artifact"}:
        return True
    checks = _objects(event.get("checks"))
    if checks is None or any(check.get("exit_code") != 0 for check in checks):
        return False
    return completion == event_type and (
        event_type != "check" or _declared_checks_match(contract, checks)
    )


def _apply_step_event(state: _Derivation, event: JsonObject) -> EvidenceFailure | None:
    event_type = _text(event, "event_type")
    if event_type not in STEP_EVENTS:
        return None
    contract = _step_contract(state, event)
    if contract is None:
        return EvidenceFailure("transition_invalid", "implementation event names an unknown active step")
    if not _step_order_valid(state, contract):
        return EvidenceFailure("step_order_invalid", "implementation evidence must follow plan step order")
    if event_type in {"red", "green", "refactor"}:
        return _apply_test_stage(state, contract, event, event_type)
    if not _stage_evidence_valid(contract, event, event_type):
        return EvidenceFailure("transition_invalid", "check or artifact evidence does not complete its step")
    return None


def _close_segment(state: _Derivation) -> None:
    state.completed |= _completed_steps(state.active_steps, state.segment)
    state.segments.append(
        {
            "approval_commit": state.approval_commit,
            "commits": [
                item["commit"]
                for item in state.segment
                if item.get("event_type") == "commit"
            ],
        }
    )


def _apply_boundary(state: _Derivation, event: JsonObject) -> EvidenceFailure | None:
    event_type = _text(event, "event_type")
    if event_type not in {"recovering", "rebound"}:
        state.segment.append(event)
        return None
    _close_segment(state)
    if event_type == "recovering":
        state.approval_commit = event.get("current_commit")
        state.segment = []
        return None
    new_steps = _steps(event.get("steps"))
    mapping = _mapping(state.active_steps, new_steps or [], event.get("mappings"))
    if new_steps is None or mapping is None:
        return EvidenceFailure("rebound_mapping_invalid", "rebound step mapping is invalid")
    state.completed = {
        mapping[step_id] for step_id in state.completed if step_id in mapping
    }
    state.active_steps = new_steps
    state.test_stages = {}
    state.red_snapshots = {}
    state.approval_commit = event.get("approval_commit")
    state.segment = []
    return None


def _apply_event(state: _Derivation, event: JsonObject) -> EvidenceFailure | None:
    event_type = _text(event, "event_type")
    if state.stopped and event_type not in {"resumed", "rebound", "resume-candidate-retired"}:
        return EvidenceFailure("transition_invalid", "stopped implementation requires resumed or rebound")
    state.stopped = event_type == "stopped"
    if event_type in {"resumed", "rebound"}:
        state.stopped = False
    if event_type == "resume-candidate-retired":
        state.resume_candidate_retired = True
    elif event_type == "resumed":
        state.resume_candidate_retired = False
    step_failure = _apply_step_event(state, event)
    return step_failure or _apply_boundary(state, event)


def _legacy_evidence(binding: JsonObject | None, events: object) -> bool:
    binding_is_legacy = binding is not None and binding.get("version") == 1
    if not isinstance(events, list):
        return binding_is_legacy
    return binding_is_legacy or any(
        isinstance(event, dict) and event.get("version") == 1 for event in events
    )


def _validated_input(
    binding: object,
    events: object,
) -> tuple[JsonObject, list[JsonObject], list[JsonObject]] | EvidenceFailure:
    binding_object = _object(binding)
    if _legacy_evidence(binding_object, events):
        return EvidenceFailure("legacy_evidence_unsupported", "version 1 implementation evidence is unsupported")
    event_objects = _objects(events)
    if binding_object is None or event_objects is None:
        return EvidenceFailure("evidence_invalid", "implementation binding and events must be structured values")
    if binding_object.get("version") != 2:
        return EvidenceFailure("evidence_invalid", "implementation binding version must be 2")
    steps = _steps(binding_object.get("steps"))
    if steps is None:
        return EvidenceFailure("step_contract_invalid", "implementation steps are invalid")
    for expected, event in enumerate(event_objects, 1):
        if event.get("version") != 2 or event.get("sequence") != expected or not _valid_event(event):
            return EvidenceFailure("evidence_invalid", "implementation events must be contiguous valid version 2 values")
    return binding_object, event_objects, steps


def _commits(segments: list[JsonObject]) -> list[str]:
    commits: list[str] = []
    for segment in segments:
        candidates = segment.get("commits")
        if isinstance(candidates, list):
            commits.extend(commit for commit in candidates if isinstance(commit, str))
    return commits


def derive_implementation(binding: object, events: object) -> EvidenceResult:
    validated = _validated_input(binding, events)
    if isinstance(validated, EvidenceFailure):
        return _failure(validated.code, validated.message)
    binding_object, event_objects, steps = validated
    state = _Derivation(steps, binding_object.get("approval_commit"))
    for event in event_objects:
        event_failure = _apply_event(state, event)
        if event_failure is not None:
            return _failure(event_failure.code, event_failure.message)
    _close_segment(state)
    ordered_completed = [
        step_id
        for step in state.active_steps
        if (step_id := _text(step, "id")) in state.completed
    ]
    resume_step = next(
        (
            step_id
            for step in state.active_steps
            if (step_id := _text(step, "id")) not in state.completed
        ),
        None,
    )
    return _ok(
        {
            "approval_commit": state.approval_commit,
            "steps": state.active_steps,
            "completed_steps": ordered_completed,
            "resume_step": resume_step,
            "segments": state.segments,
            "commits": _commits(state.segments),
            "resume_candidate_retired": state.resume_candidate_retired,
        }
    )
