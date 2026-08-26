"""Canonical interpretation of version 2 implementation evidence."""
from __future__ import annotations

from typing import Any, NamedTuple

COMPLETIONS = {"test", "check", "artifact", "external"}
SHA = __import__("re").compile(r"[0-9a-f]{40,64}")

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
    if not isinstance(value, list):
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
        return isinstance(checks, list) and bool(checks) and all(
            isinstance(check, dict) and check.get("exit_code") == 0 for check in checks
        )
    return event.get("condition_met") is True

def _completed_steps(steps: list[dict], events: list[dict]) -> set[str]:
    completed: set[str] = set()
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
            completed.add(step["id"])
    return completed

def _mapping(old_steps: list[dict], new_steps: list[dict], value: object) -> dict[str, str] | None:
    if not isinstance(value, list):
        return None
    old = {step["id"]: step["completion"] for step in old_steps}
    new = {step["id"]: step["completion"] for step in new_steps}
    mapping: dict[str, str] = {}
    targets: set[str] = set()
    for item in value:
        if (
            not isinstance(item, dict) or item.get("old") not in old or item.get("new") not in new
            or item["old"] in mapping or item["new"] in targets or old[item["old"]] != new[item["new"]]
        ):
            return None
        mapping[item["old"]] = item["new"]
        targets.add(item["new"])
    return mapping

def _safe_paths(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(path, str) and path for path in value)

def _snapshot(value: object) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("files"), dict):
        return False
    digest = __import__("re").compile(r"sha256:[0-9a-f]{64}")
    return (
        isinstance(value.get("command"), str) and digest.fullmatch(value["command"]) is not None
        and all(isinstance(path, str) and path and isinstance(item, str) and digest.fullmatch(item) is not None
                for path, item in value["files"].items())
    )

def _valid_event(event: dict) -> bool:
    kind = event.get("event_type")
    if not isinstance(kind, str) or not kind:
        return False
    if kind in {"red", "green", "refactor"}:
        return (
            isinstance(event.get("step"), str) and bool(event["step"])
            and isinstance(event.get("command"), str) and bool(event["command"])
            and isinstance(event.get("exit_code"), int)
            and _snapshot(event.get("snapshot"))
        )
    if kind in {"check", "artifact"}:
        checks = event.get("checks")
        return (
            isinstance(event.get("step"), str) and bool(event["step"])
            and isinstance(checks, list) and bool(checks)
            and all(isinstance(check, dict) and isinstance(check.get("exit_code"), int) for check in checks)
            and _safe_paths(event.get("changed_paths"))
        )
    if kind == "external":
        return (
            isinstance(event.get("step"), str) and bool(event["step"])
            and isinstance(event.get("condition_met"), bool)
            and _safe_paths(event.get("changed_paths"))
        )
    if kind == "commit":
        safety = event.get("safety")
        return (
            isinstance(event.get("step"), str) and bool(event["step"])
            and isinstance(event.get("commit"), str) and SHA.fullmatch(event["commit"]) is not None
            and isinstance(safety, dict) and _safe_paths(safety.get("paths"))
            and isinstance(safety.get("unplanned"), list)
        )
    if kind == "recovering":
        return (
            isinstance(event.get("current_commit"), str) and SHA.fullmatch(event["current_commit"]) is not None
            and _safe_paths(event.get("changed_documents"))
            and isinstance(event.get("reason"), str) and bool(event["reason"].strip())
        )
    if kind == "rebound":
        return (
            isinstance(event.get("approval_commit"), str) and SHA.fullmatch(event["approval_commit"]) is not None
            and isinstance(event.get("reason"), str) and bool(event["reason"].strip())
        )
    if kind == "implementation_green":
        return _safe_paths(event.get("completed_steps"))
    if kind == "worktree-bound":
        return isinstance(event.get("branch"), str) and bool(event["branch"]) and isinstance(event.get("worktree"), str) and bool(event["worktree"])
    if kind == "human_gate":
        return isinstance(event.get("reason"), str) and bool(event["reason"].strip())
    if kind in {"delegated", "returned"}:
        field = "role" if kind == "delegated" else "outcome"
        return field not in event or isinstance(event[field], str)
    if kind == "resumed":
        return (
            isinstance(event.get("branch_head"), str) and SHA.fullmatch(event["branch_head"]) is not None
            and _safe_paths(event.get("unexplained_commits")) and _safe_paths(event.get("uncommitted_paths"))
        )
    if kind == "stopped":
        return isinstance(event.get("reason"), str) and bool(event["reason"].strip())
    return False

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
        if not _valid_event(event):
            return _failure("evidence_invalid", "implementation event schema is invalid")
    active_steps = steps
    approval_commit = binding.get("approval_commit")
    completed: set[str] = set()
    segment: list[dict] = []
    segments: list[dict] = []
    test_stages: dict[str, str] = {}
    stopped = False
    for event in events:
        kind = event["event_type"]
        if stopped and kind not in {"resumed", "rebound"}:
            return _failure("transition_invalid", "stopped implementation requires resumed or rebound")
        stopped = kind == "stopped"
        if kind in {"resumed", "rebound"}:
            stopped = False
        if kind in {"red", "green", "refactor", "check", "artifact", "external", "commit"}:
            contract = next((step for step in active_steps if step["id"] == event.get("step")), None)
            if contract is None:
                return _failure("transition_invalid", "implementation event names an unknown active step")
            if kind in {"red", "green", "refactor"}:
                if contract["completion"] != "test":
                    return _failure("transition_invalid", "test stage belongs to a non-test step")
                previous = test_stages.get(contract["id"])
                valid = (
                    (kind == "red" and event["exit_code"] != 0)
                    or (kind == "green" and event["exit_code"] == 0 and previous == "red")
                    or (kind == "refactor" and event["exit_code"] == 0 and previous == "green")
                )
                if not valid:
                    return _failure("transition_invalid", "test stages must follow RED, GREEN, REFACTOR")
                test_stages[contract["id"]] = kind
            elif kind in {"check", "artifact"} and (
                kind != contract["completion"] or any(check["exit_code"] != 0 for check in event["checks"])
            ):
                return _failure("transition_invalid", "check or artifact evidence does not complete its step")
            elif kind == "external" and contract["completion"] != "external":
                return _failure("transition_invalid", "external evidence belongs to a non-external step")
        if event.get("event_type") not in {"recovering", "rebound"}:
            segment.append(event)
            continue
        completed |= _completed_steps(active_steps, segment)
        segments.append({
            "approval_commit": approval_commit,
            "commits": [item["commit"] for item in segment if item.get("event_type") == "commit"],
        })
        if event.get("event_type") == "recovering":
            approval_commit = event["current_commit"]
            segment = []
            continue
        new_steps = _steps(event.get("steps"))
        mapping = _mapping(active_steps, new_steps or [], event.get("mappings"))
        if new_steps is None or mapping is None:
            return _failure("rebound_mapping_invalid", "rebound step mapping is invalid")
        completed = {mapping[step_id] for step_id in completed if step_id in mapping}
        active_steps = new_steps
        test_stages = {mapping[step]: state for step, state in test_stages.items() if step in mapping}
        approval_commit = event.get("approval_commit")
        segment = []
    completed |= _completed_steps(active_steps, segment)
    segments.append({
        "approval_commit": approval_commit,
        "commits": [item["commit"] for item in segment if item.get("event_type") == "commit"],
    })
    ordered_completed = [step["id"] for step in active_steps if step["id"] in completed]
    resume_step = next((step["id"] for step in active_steps if step["id"] not in completed), None)
    return _ok({
        "approval_commit": approval_commit, "steps": active_steps,
        "completed_steps": ordered_completed, "resume_step": resume_step, "segments": segments,
    })
