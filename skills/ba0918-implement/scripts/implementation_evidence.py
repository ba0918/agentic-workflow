"""Canonical interpretation of version 2 implementation evidence."""
from __future__ import annotations

import re
from typing import NamedTuple


JsonObject = dict[str, object]
COMPLETIONS = {"test", "check", "artifact", "external"}
STEP_EVENTS = {"red", "green", "refactor", "check", "artifact", "external", "commit"}
GATE_TIMINGS = {"before_edit", "before_commit", "before_implementation_green"}
GATE_RESULTS = {"approved", "rejected"}
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
        human_gates = _human_gates(item.get("human_gates", []))
        if human_gates is None:
            return None
        identifiers.add(step_id)
        step: JsonObject = {"id": step_id, "completion": completion}
        if isinstance(checks, list):
            step["checks"] = list(checks)
        if human_gates:
            step["human_gates"] = human_gates
        normalized.append(step)
    gate_ids = [
        gate.get("gate_id") for step in normalized
        for gate in _objects(step.get("human_gates", [])) or []
    ]
    if len(gate_ids) != len(set(gate_ids)):
        return None
    return normalized


def _strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def _safe_gate_path(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/"):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _gate_target(value: object) -> JsonObject | None:
    target = _object(value)
    if target is None:
        return None
    if target.get("kind") == "files" and set(target) == {"kind", "paths"}:
        paths = _strings(target.get("paths"))
        if paths and len(paths) == len(set(paths)) and all(_safe_gate_path(path) for path in paths):
            return {"kind": "files", "paths": paths}
    sequence = target.get("sequence")
    if (
        target.get("kind") == "event" and set(target) == {"kind", "sequence"}
        and isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0
    ):
        return {"kind": "event", "sequence": sequence}
    return None


def _human_gates(value: object) -> list[JsonObject] | None:
    gates = _objects(value)
    if gates is None:
        return None
    normalized: list[JsonObject] = []
    identifiers: set[str] = set()
    for gate in gates:
        if set(gate) != {
            "gate_id", "sections", "criterion", "target", "timing", "allowed_results",
        }:
            return None
        gate_id = _text(gate, "gate_id")
        sections = _strings(gate.get("sections"))
        criterion = _text(gate, "criterion")
        target = _gate_target(gate.get("target"))
        timing = _text(gate, "timing")
        results = _strings(gate.get("allowed_results"))
        identity_valid = (
            gate_id is not None
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", gate_id) is not None
            and gate_id not in identifiers
        )
        sections_valid = bool(
            sections and len(sections) == len(set(sections))
            and all(section.strip() for section in sections)
        )
        results_valid = bool(
            results is not None and len(results) == len(GATE_RESULTS)
            and set(results) == GATE_RESULTS
        )
        if not all((
            identity_valid, sections_valid, criterion is not None,
            target is not None, timing in GATE_TIMINGS, results_valid,
        )):
            return None
        if gate_id is None:
            return None
        identifiers.add(gate_id)
        normalized.append({
            "gate_id": gate_id,
            "sections": sections,
            "criterion": criterion,
            "target": target,
            "timing": timing,
            "allowed_results": results,
        })
    return normalized


def normalize_steps(value: object) -> list[JsonObject] | None:
    """Return canonical Step contracts for a binding boundary."""
    return _steps(value)


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


def _artifact_paths(event: JsonObject) -> list[str] | None:
    if "paths" in event:
        return _strings(event.get("paths"))
    return _strings(event.get("changed_paths"))


def _artifact_paths_observed(event: JsonObject) -> bool:
    targets = set(_artifact_paths(event) or [])
    observed = set(_strings(event.get("changed_paths")) or [])
    return bool(targets) and targets <= observed


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
    if completion == "artifact" and not _artifact_paths_observed(event):
        return False
    succeeded = all(check.get("exit_code") == 0 for check in checks)
    return succeeded and (completion != "check" or _declared_checks_match(step, checks))


class _GateApproval(NamedTuple):
    event: JsonObject
    carried: bool = False


def _raw_completion(step: JsonObject, events: list[JsonObject]) -> tuple[int, int] | None:
    step_id = _text(step, "id")
    last_red = -1
    if _text(step, "completion") == "test":
        last_red = max(
            (
                index for index, event in enumerate(events)
                if event.get("step") == step_id and event.get("event_type") == "red"
            ),
            default=-1,
        )
    positions = [
        index for index, event in enumerate(events)
        if index > last_red and event.get("step") == step_id and _valid_evidence(step, event)
    ]
    if not positions:
        return None
    evidence_position = positions[-1]
    completion = _text(step, "completion")
    commit_required = completion in {"test", "artifact"} or bool(
        events[evidence_position].get("changed_paths")
    )
    if not commit_required:
        return evidence_position, evidence_position
    commit_position = next(
        (
            index for index in range(evidence_position + 1, len(events))
            if events[index].get("event_type") == "commit"
            and events[index].get("step") == step_id
            and _commit_covers_artifact(step, events[evidence_position], events[index])
        ),
        None,
    )
    return None if commit_position is None else (evidence_position, commit_position)


def _commit_covers_artifact(
    step: JsonObject, evidence: JsonObject, commit: JsonObject,
) -> bool:
    if _text(step, "completion") != "artifact":
        return True
    safety = _object(commit.get("safety")) or {}
    committed = set(_strings(safety.get("paths")) or [])
    targets = set(_artifact_paths(evidence) or [])
    return bool(targets) and targets <= committed


def _target_changed(target: JsonObject, events: list[JsonObject]) -> bool:
    if target.get("kind") != "files":
        return False
    paths = set(_strings(target.get("paths")) or [])
    for event in events:
        changed = event.get("changed_paths")
        if event.get("event_type") == "commit":
            safety = _object(event.get("safety")) or {}
            changed = safety.get("paths")
        if paths & set(_strings(changed) or []):
            return True
    return False


def _event_position(events: list[JsonObject], sequence: object) -> int:
    return next(
        (
            index for index, event in enumerate(events)
            if event.get("sequence") == sequence
        ),
        -1,
    )


def _first_step_work(events: list[JsonObject], step_id: str | None) -> int:
    return next(
        (
            index for index, event in enumerate(events)
            if event.get("step") == step_id and event.get("event_type") in STEP_EVENTS
        ),
        len(events),
    )


def _gate_satisfied(
    step: JsonObject,
    gate: JsonObject,
    events: list[JsonObject],
    approvals: dict[tuple[str, str], _GateApproval],
    *,
    completion_carried: bool = False,
) -> bool:
    step_id = _text(step, "id")
    gate_id = _text(gate, "gate_id")
    approval = approvals.get((step_id or "", gate_id or ""))
    if approval is None or approval.event.get("result") != "approved":
        return False
    timing = gate.get("timing")
    approval_index = _event_position(events, approval.event.get("sequence"))
    raw = _raw_completion(step, events)
    if timing == "before_edit":
        return approval.carried or 0 <= approval_index < _first_step_work(events, step_id)
    if raw is None:
        return bool(
            timing == "before_implementation_green"
            and completion_carried
            and approval.carried
            and not _target_changed(_object(gate.get("target")) or {}, events)
        )
    evidence_position, completion_position = raw
    if timing == "before_commit":
        if not approval.carried and not evidence_position < approval_index < completion_position:
            return False
        end = completion_position
    else:
        if not approval.carried and approval_index <= completion_position:
            return False
        end = len(events)
    start = approval_index + 1 if approval_index >= 0 else 0
    return not _target_changed(_object(gate.get("target")) or {}, events[start:end])


def _completed_steps(
    steps: list[JsonObject],
    events: list[JsonObject],
    approvals: dict[tuple[str, str], _GateApproval] | None = None,
) -> set[str]:
    active_approvals = approvals or {}
    completed: set[str] = set()
    for step in steps:
        step_id = _text(step, "id")
        if step_id is None:
            continue
        gates = _objects(step.get("human_gates", [])) or []
        if _raw_completion(step, events) is not None and all(
            gate.get("timing") == "before_implementation_green"
            or _gate_satisfied(step, gate, events, active_approvals)
            for gate in gates
        ):
            completed.add(step_id)
    return completed


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


def _gate_contracts_equal(old_step: JsonObject, new_step: JsonObject) -> bool:
    old_gates = _objects(old_step.get("human_gates", [])) or []
    new_gates = _objects(new_step.get("human_gates", [])) or []
    return old_gates == new_gates


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
    if event_type == "human_gate" and "gate_id" in event:
        return all(
            _text(event, field) is not None
            for field in ("reason", "step", "gate_id", "result")
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
        self.approvals: dict[tuple[str, str], _GateApproval] = {}
        self.seen_events: list[JsonObject] = []
        self.stopped = False
        self.resume_candidate_retired = False
        self.complete = False


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
    completed_now = state.completed | _completed_steps(
        state.active_steps, state.segment, state.approvals,
    )
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
        state.completed.discard(contract_id)
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
    return completion == event_type and _valid_evidence(contract, event)


def _apply_step_event(state: _Derivation, event: JsonObject) -> EvidenceFailure | None:
    event_type = _text(event, "event_type")
    if event_type not in STEP_EVENTS:
        return None
    contract = _step_contract(state, event)
    contract_failure = _step_contract_failure(state, contract)
    if contract_failure is not None or contract is None:
        return contract_failure
    gate_failure = _required_gate_failure(state, contract, event_type)
    if gate_failure is not None:
        return gate_failure
    if event_type in {"red", "green", "refactor"}:
        return _apply_test_stage(state, contract, event, event_type)
    if not _stage_evidence_valid(contract, event, event_type):
        return EvidenceFailure("transition_invalid", "check or artifact evidence does not complete its step")
    return None


def _step_contract_failure(
    state: _Derivation, contract: JsonObject | None,
) -> EvidenceFailure | None:
    if contract is None:
        return EvidenceFailure(
            "step_unknown", "implementation event names an unknown active step",
        )
    if not _step_order_valid(state, contract):
        return EvidenceFailure(
            "step_order_invalid", "implementation evidence must follow plan step order",
        )
    return None


def _gate_contract(step: JsonObject, gate_id: object) -> JsonObject | None:
    gates = _objects(step.get("human_gates", [])) or []
    return next((gate for gate in gates if gate.get("gate_id") == gate_id), None)


def _required_gate_failure(
    state: _Derivation, step: JsonObject, event_type: str | None,
) -> EvidenceFailure | None:
    step_id = _text(step, "id") or ""
    gates = _objects(step.get("human_gates", [])) or []
    for gate in gates:
        timing = gate.get("timing")
        gate_id = _text(gate, "gate_id") or ""
        approval = state.approvals.get((step_id, gate_id))
        if timing == "before_edit" and (
            approval is None or approval.event.get("result") != "approved"
        ):
            return EvidenceFailure("human_gate_required", "declared Human gate needs approval")
        if event_type == "commit" and timing == "before_commit" and not _before_commit_ready(
            step, gate, state.segment, approval,
        ):
            return EvidenceFailure("human_gate_required", "declared Human gate needs approval")
    return None


def _before_commit_ready(
    step: JsonObject,
    gate: JsonObject,
    events: list[JsonObject],
    approval: _GateApproval | None,
) -> bool:
    if approval is None or approval.event.get("result") != "approved":
        return False
    evidence_positions = [
        index for index, item in enumerate(events)
        if item.get("step") == _text(step, "id") and _valid_evidence(step, item)
    ]
    if not evidence_positions:
        return False
    approval_sequence = approval.event.get("sequence")
    approval_index = next(
        (
            index for index, item in enumerate(events)
            if item.get("sequence") == approval_sequence
        ),
        -1,
    )
    if not approval.carried and approval_index <= evidence_positions[-1]:
        return False
    start = approval_index + 1 if approval_index >= 0 else 0
    return not _target_changed(_object(gate.get("target")) or {}, events[start:])


def _human_gate_failure(state: _Derivation, event: JsonObject) -> EvidenceFailure | None:
    step_id = _text(event, "step")
    gate_id = _text(event, "gate_id")
    step = next(
        (item for item in state.active_steps if _text(item, "id") == step_id), None,
    )
    gate = _gate_contract(step, gate_id) if step is not None else None
    if step is None or gate is None:
        return EvidenceFailure("human_gate_unknown", "Human gate is not declared by the active plan")
    if event.get("result") not in (_strings(gate.get("allowed_results")) or []):
        return EvidenceFailure("human_gate_result_invalid", "Human gate result is not allowed")
    target = _object(gate.get("target")) or {}
    if target.get("kind") == "event" and not any(
        prior.get("sequence") == target.get("sequence") for prior in state.seen_events
    ):
        return EvidenceFailure("human_gate_target_invalid", "Human gate event target does not exist")
    timing_failure = _human_gate_timing_failure(state, step, gate)
    if timing_failure is not None:
        return timing_failure
    key = (step_id or "", gate_id or "")
    if event.get("result") == "approved":
        state.approvals[key] = _GateApproval(event)
    else:
        state.approvals.pop(key, None)
    return None


def _human_gate_timing_failure(
    state: _Derivation, step: JsonObject, gate: JsonObject,
) -> EvidenceFailure | None:
    step_id = _text(step, "id")
    step_events = [
        item for item in state.segment
        if item.get("step") == step_id and item.get("event_type") in STEP_EVENTS
    ]
    raw = _raw_completion(step, state.segment)
    timing = gate.get("timing")
    if timing == "before_edit" and step_events:
        return EvidenceFailure("human_gate_timing_invalid", "before_edit gate is too late")
    if timing == "before_commit" and (
        raw is not None or not any(_valid_evidence(step, item) for item in state.segment)
    ):
        return EvidenceFailure(
            "human_gate_timing_invalid", "before_commit gate is outside its boundary",
        )
    if timing == "before_implementation_green" and raw is None:
        return EvidenceFailure(
            "human_gate_timing_invalid", "before_implementation_green gate is too early",
        )
    return None


def _close_segment(state: _Derivation) -> None:
    state.completed |= _completed_steps(
        state.active_steps, state.segment, state.approvals,
    )
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
        state.approvals = {
            key: _GateApproval(approval.event, carried=True)
            for key, approval in state.approvals.items()
        }
        state.approval_commit = event.get("current_commit")
        state.segment = []
        return None
    old_steps = state.active_steps
    new_steps = _steps(event.get("steps"))
    mapping = _mapping(old_steps, new_steps or [], event.get("mappings"))
    if new_steps is None or mapping is None:
        return EvidenceFailure("rebound_mapping_invalid", "rebound step mapping is invalid")
    old_by_id = {_text(step, "id"): step for step in old_steps}
    new_by_id = {_text(step, "id"): step for step in new_steps}
    equivalent = {
        old_id: new_id for old_id, new_id in mapping.items()
        if _gate_contracts_equal(old_by_id[old_id], new_by_id[new_id])
    }
    state.completed = {
        equivalent[step_id] for step_id in state.completed if step_id in equivalent
    }
    state.approvals = {
        (equivalent[step_id], gate_id): _GateApproval(approval.event, carried=True)
        for (step_id, gate_id), approval in state.approvals.items()
        if step_id in equivalent
    }
    state.active_steps = new_steps
    state.test_stages = {}
    state.red_snapshots = {}
    state.approval_commit = event.get("approval_commit")
    state.segment = []
    return None


def _implementation_green_failure(
    state: _Derivation, event: JsonObject,
) -> EvidenceFailure | None:
    completed = state.completed | _completed_steps(
        state.active_steps, state.segment, state.approvals,
    )
    expected = {_text(step, "id") for step in state.active_steps}
    if completed != expected:
        has_green_gate = any(
            gate.get("timing") == "before_implementation_green"
            for step in state.active_steps
            for gate in (_objects(step.get("human_gates", [])) or [])
        )
        if has_green_gate:
            return EvidenceFailure("human_gate_required", "declared Human gate needs approval")
        return EvidenceFailure("transition_invalid", "implementation is not complete")
    final_gates = [
        (step, gate) for step in state.active_steps
        for gate in (_objects(step.get("human_gates", [])) or [])
        if gate.get("timing") == "before_implementation_green"
    ]
    if not all(
        _gate_satisfied(
            step, gate, state.segment, state.approvals,
            completion_carried=_text(step, "id") in state.completed,
        )
        for step, gate in final_gates
    ):
        return EvidenceFailure("human_gate_required", "declared Human gate needs approval")
    ordered = [
        step_id for step in state.active_steps
        if (step_id := _text(step, "id")) in completed
    ]
    if _strings(event.get("completed_steps")) != ordered:
        return EvidenceFailure(
            "transition_invalid", "implementation_green must list completed active steps",
        )
    return None


def _update_run_state(state: _Derivation, event_type: str | None) -> None:
    if event_type == "stopped":
        state.stopped = True
    elif event_type in {"resumed", "rebound", "resume-candidate-retired"}:
        state.stopped = False
    if event_type == "resume-candidate-retired":
        state.resume_candidate_retired = True
    elif event_type == "resumed":
        state.resume_candidate_retired = False


def _apply_event(state: _Derivation, event: JsonObject) -> EvidenceFailure | None:
    event_type = _text(event, "event_type")
    returning_completed_delegation = (
        state.complete
        and event_type == "returned"
        and bool(state.seen_events)
        and state.seen_events[-1].get("event_type") == "implementation_green"
    )
    if state.complete and not returning_completed_delegation:
        return EvidenceFailure(
            "run_already_complete", "completed implementation evidence cannot be extended",
        )
    if state.stopped and event_type not in {
        "returned", "resumed", "rebound", "resume-candidate-retired",
    }:
        return EvidenceFailure("run_stopped", "stopped implementation requires resumed or rebound")
    _update_run_state(state, event_type)
    if event_type == "implementation_green":
        completion_failure = _implementation_green_failure(state, event)
        if completion_failure is not None:
            return completion_failure
        state.complete = True
    if event_type == "human_gate" and "gate_id" in event:
        gate_failure = _human_gate_failure(state, event)
        if gate_failure is not None:
            return gate_failure
    step_failure = _apply_step_event(state, event)
    boundary_failure = step_failure or _apply_boundary(state, event)
    if boundary_failure is None:
        state.seen_events.append(event)
    return boundary_failure


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
