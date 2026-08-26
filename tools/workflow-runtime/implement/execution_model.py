#!/usr/bin/env python3
"""Pure validation and state derivation for implement execution evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
import re
from typing import Any, NamedTuple


IDENTITY = re.compile(r"sha256:[0-9a-f]{64}")
PLAN_ID = re.compile(r"[0-9]{14}")
ATTEMPT_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
COMMIT_SHA = re.compile(r"[0-9a-f]{40,64}")
# Only a behavior failure is an approved missing behavior; import, fixture, permission and
# network failures are never an expected RED, so the candidate may not predict them.
EXPECTED_RED_FAILURE_KIND = "behavior_failure"
GENERIC_FAILURE_SIGNATURE = re.compile(
    r"(?i)^(?:failed(?:\s*\([^)]*\))?|errors?|[0-9]+\s+(?:failed|errors?)|"
    r"exit(?:\s+code)?[=: ]+\d+)$"
)
APPROVAL_RESULTS = ["approved", "rejected"]
RAW_LOG_FIELDS = {"stdout", "stderr", "provider_log", "raw_log"}
SECRET_VALUE_FIELDS = {"environment", "environment_values", "secret", "password", "credential"}
SECRET_FIELD = re.compile(r"(?i)(?:api[_-]?key|secret|token|password|credential)")
SECRET_ARGUMENT = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|credential)\s*[=:]\s*\S+"
)
GATE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STEP_ID = re.compile(r"step-[1-9][0-9]*")
HUMAN_GATE_TIMINGS = {
    "before_edit": 0,
    "before_commit": 1,
    "before_implementation_green": 2,
}
HUMAN_GATE_RESULTS = ["approved", "rejected"]
ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ModelFailure(NamedTuple):
    code: str
    field: str | None
    message: str


class ModelResult(NamedTuple):
    value: Any | None
    error: ModelFailure | None

    @property
    def ok(self) -> bool:
        return self.error is None


def _ok(value: Any = None) -> ModelResult:
    return ModelResult(value, None)


def _failure(code: str, field: str | None, message: str) -> ModelResult:
    return ModelResult(None, ModelFailure(code, field, message))


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def content_identity(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "" not in path.parts


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _first_forbidden_field(value: object, forbidden: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden:
                return key
            nested = _first_forbidden_field(child, forbidden)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _first_forbidden_field(child, forbidden)
            if nested is not None:
                return nested
    return None


def _first_secret_field(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_FIELD.search(key):
                return key
            nested = _first_secret_field(child)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _first_secret_field(child)
            if nested is not None:
                return nested
    return None


def _validate_human_gates(value: object) -> ModelResult:
    if not isinstance(value, list):
        return _failure("human_gate_binding_invalid", "human_gates", "human gates must be a list")
    gate_ids: set[str] = set()
    for gate in value:
        if not isinstance(gate, dict) or set(gate) != {
            "gate_id",
            "step_id",
            "sections",
            "criterion",
            "target",
            "timing",
            "allowed_results",
        }:
            return _failure("human_gate_binding_invalid", "human_gates", "human gate fields are invalid")
        gate_id = gate["gate_id"]
        if not _matches(GATE_ID, gate_id) or gate_id in gate_ids:
            return _failure("human_gate_binding_invalid", "human_gates.gate_id", "human gate id is invalid")
        gate_ids.add(gate_id)
        if not _matches(STEP_ID, gate["step_id"]):
            return _failure("human_gate_binding_invalid", "human_gates.step_id", "human gate step is invalid")
        sections = gate["sections"]
        if not isinstance(sections, list) or not sections or len(sections) != len(set(sections)) or any(
            not isinstance(section, str) or not section.strip() for section in sections
        ):
            return _failure("human_gate_binding_invalid", "human_gates.sections", "human gate sections are invalid")
        if not isinstance(gate["criterion"], str) or not gate["criterion"].strip() or len(gate["criterion"]) > 500:
            return _failure("human_gate_binding_invalid", "human_gates.criterion", "human gate criterion is invalid")
        target = gate["target"]
        if not isinstance(target, dict) or target.get("kind") not in {"files", "event"}:
            return _failure("human_gate_binding_invalid", "human_gates.target", "human gate target is invalid")
        if target["kind"] == "files":
            if set(target) != {"kind", "paths"}:
                return _failure("human_gate_binding_invalid", "human_gates.target", "human gate target fields are invalid")
            paths = target["paths"]
            if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)) or any(
                not _safe_relative_path(path) for path in paths
            ):
                return _failure("human_gate_binding_invalid", "human_gates.target.paths", "human gate paths are invalid")
        elif set(target) != {"kind", "content_identity"} or not _matches(
            IDENTITY, target.get("content_identity")
        ):
            return _failure("human_gate_binding_invalid", "human_gates.target", "human gate event target is invalid")
        if gate["timing"] not in HUMAN_GATE_TIMINGS:
            return _failure("human_gate_binding_invalid", "human_gates.timing", "human gate timing is invalid")
        if gate["allowed_results"] != HUMAN_GATE_RESULTS:
            return _failure("human_gate_binding_invalid", "human_gates.allowed_results", "human gate results are invalid")
    return _ok(value)


def _validate_test_summary(value: object) -> ModelResult:
    if not isinstance(value, dict):
        return _failure("test_summary_invalid", "test_summary", "test summary must be an object")
    if value.get("status") == "complete":
        if set(value) != {"status", "passed", "failed", "skipped"} or any(
            type(value[field]) is not int or value[field] < 0
            for field in ("passed", "failed", "skipped")
        ):
            return _failure(
                "test_summary_invalid",
                "test_summary",
                "complete test summary counts are invalid",
            )
        return _ok(value)
    if value.get("status") == "unavailable":
        if (
            set(value) != {"status", "reason"}
            or not isinstance(value["reason"], str)
            or not value["reason"].strip()
            or len(value["reason"]) > 500
        ):
            return _failure(
                "test_summary_invalid",
                "test_summary",
                "unavailable test summary reason is invalid",
            )
        return _ok(value)
    return _failure("test_summary_invalid", "test_summary.status", "test summary status is invalid")


def _validate_plan_binding(plan: object) -> ModelResult:
    if not isinstance(plan, dict) or set(plan) != {
        "id",
        "path",
        "revision",
        "content_identity",
    }:
        return _failure("plan_binding_invalid", "plan", "plan binding fields are invalid")
    if not _matches(PLAN_ID, plan["id"]):
        return _failure("plan_binding_invalid", "plan.id", "plan id is invalid")
    if not _safe_relative_path(plan["path"]):
        return _failure("plan_binding_invalid", "plan.path", "plan path is unsafe")
    if not isinstance(plan["revision"], int) or plan["revision"] < 1:
        return _failure("plan_binding_invalid", "plan.revision", "plan revision is invalid")
    if not _matches(IDENTITY, plan["content_identity"]):
        return _failure("plan_binding_invalid", "plan.content_identity", "plan identity is invalid")
    return _ok(plan)


def _validate_spec_bindings(specs: object) -> ModelResult:
    if not isinstance(specs, list) or not specs:
        return _failure("spec_binding_invalid", "specs", "at least one spec is required")
    spec_paths: set[str] = set()
    for spec in specs:
        if not isinstance(spec, dict) or set(spec) != {"path", "content_identity"}:
            return _failure("spec_binding_invalid", "specs", "spec binding fields are invalid")
        if not _safe_relative_path(spec["path"]) or spec["path"] in spec_paths:
            return _failure("spec_binding_invalid", "specs.path", "spec path is unsafe or duplicated")
        spec_paths.add(spec["path"])
        if not _matches(IDENTITY, spec["content_identity"]):
            return _failure("spec_binding_invalid", "specs.content_identity", "spec identity is invalid")
    return _ok(specs)


def _validate_write_scope(scopes: object) -> ModelResult:
    if not isinstance(scopes, list) or not scopes or any(not _safe_relative_path(item) for item in scopes):
        return _failure("write_scope_invalid", "write_scope", "write scope is invalid")
    return _ok(scopes)


def validate_binding(value: object) -> ModelResult:
    secret = _first_secret_field(value)
    if secret is not None:
        return _failure("secret_value_forbidden", secret, "secret values are not allowed in a binding")
    required = {
        "version",
        "attempt_id",
        "plan",
        "specs",
        "repository_identity",
        "base_head",
        "branch",
        "worktree",
        "write_scope",
        "human_gates",
        "executor",
    }
    if not isinstance(value, dict) or set(value) != required:
        return _failure("binding_fields_invalid", None, "binding fields are missing or unknown")
    if value["version"] != 1:
        return _failure("binding_version_invalid", "version", "unsupported binding version")
    if not _matches(ATTEMPT_ID, value["attempt_id"]):
        return _failure("attempt_id_invalid", "attempt_id", "attempt id is not path-safe")

    plan = _validate_plan_binding(value["plan"])
    if not plan.ok:
        return plan
    specs = _validate_spec_bindings(value["specs"])
    if not specs.ok:
        return specs

    if not _matches(IDENTITY, value["repository_identity"]):
        return _failure("repository_identity_invalid", "repository_identity", "repository identity is invalid")
    if not _matches(COMMIT_SHA, value["base_head"]):
        return _failure("base_head_invalid", "base_head", "base HEAD is invalid")
    if not isinstance(value["branch"], str) or not value["branch"] or value["branch"].startswith("-"):
        return _failure("branch_invalid", "branch", "branch name is invalid")
    if not isinstance(value["worktree"], str) or not value["worktree"].strip():
        return _failure("worktree_invalid", "worktree", "worktree path is invalid")
    scopes = _validate_write_scope(value["write_scope"])
    if not scopes.ok:
        return scopes
    human_gates = _validate_human_gates(value["human_gates"])
    if not human_gates.ok:
        return human_gates
    executor = value["executor"]
    if not isinstance(executor, dict) or set(executor) not in (
        {"executor", "backend", "session_id"},
        {"executor", "backend", "session_id", "reason"},
    ):
        return _failure("executor_invalid", "executor", "executor provenance is invalid")
    for field in ("executor", "backend", "session_id"):
        if not isinstance(executor[field], str) or not executor[field] or len(executor[field]) > 256:
            return _failure("executor_invalid", f"executor.{field}", "executor provenance is invalid")
    unavailable = "unavailable" in {executor["backend"], executor["session_id"]}
    if unavailable != ("reason" in executor):
        return _failure("executor_invalid", "executor.reason", "unavailable provenance requires one reason")
    if "reason" in executor and (
        not isinstance(executor["reason"], str)
        or not executor["reason"].strip()
        or len(executor["reason"]) > 500
    ):
        return _failure("executor_invalid", "executor.reason", "executor reason is invalid")
    return _ok(value)


def validate_snapshot(expected: object, observed: object) -> ModelResult:
    if not isinstance(expected, dict) or not isinstance(observed, dict):
        return _failure("identity_drift", None, "identity snapshot is not a mapping")
    for key in sorted(set(expected) | set(observed)):
        if expected.get(key) != observed.get(key):
            return _failure("identity_drift", key, f"identity drift detected at {key}")
    return _ok(observed)


def validate_write_path(relative_path: str, scopes: list[str]) -> ModelResult:
    if not _safe_relative_path(relative_path):
        return _failure("write_scope_violation", relative_path, "write path is unsafe")
    candidate = PurePosixPath(relative_path)
    for raw_scope in scopes:
        if not _safe_relative_path(raw_scope):
            continue
        scope = PurePosixPath(raw_scope)
        if candidate == scope:
            return _ok(relative_path)
        if scope.suffix == "" and candidate.parts[: len(scope.parts)] == scope.parts:
            return _ok(relative_path)
    return _failure("write_scope_violation", relative_path, "write path is outside the approved scope")


def validate_relative_path(relative_path: object) -> ModelResult:
    if not _safe_relative_path(relative_path):
        return _failure("unsafe_path", None, "path must be repository-relative without traversal")
    return _ok(relative_path)


def _validate_oracle(value: object, *, require_observed: bool) -> ModelResult:
    forbidden = _first_secret_field(value)
    if forbidden is not None:
        return _failure("secret_value_forbidden", forbidden, "only environment names may be recorded")
    required = {
        "version",
        "step_id",
        "sections",
        "test_targets",
        "command",
        "cwd",
        "environment_names",
        "timeout_seconds",
        "expected_failure_kind",
        "failure_signature",
    }
    if require_observed:
        required.add("observed_failure_kind")
    if not isinstance(value, dict) or not required.issubset(value):
        return _failure("oracle_field_missing", None, "oracle fields are missing")
    if set(value) != required:
        return _failure("oracle_fields_invalid", None, "oracle fields are unknown or unexpected")
    if value["version"] != 1 or not isinstance(value["step_id"], str) or not value["step_id"]:
        return _failure("oracle_field_invalid", "step_id", "oracle step is invalid")
    if not isinstance(value["sections"], list) or not value["sections"]:
        return _failure("oracle_field_invalid", "sections", "oracle sections are invalid")
    test_targets = value["test_targets"]
    if require_observed:
        if not isinstance(test_targets, list) or not test_targets:
            return _failure("oracle_field_invalid", "test_targets", "test targets are invalid")
        target_paths: set[str] = set()
        for target in test_targets:
            if not isinstance(target, dict) or set(target) != {"path", "content_identity"}:
                return _failure("oracle_field_invalid", "test_targets", "test target fields are invalid")
            if (
                not _safe_relative_path(target["path"])
                or target["path"] in target_paths
                or not _matches(IDENTITY, target["content_identity"])
            ):
                return _failure("oracle_field_invalid", "test_targets", "test target is invalid")
            target_paths.add(target["path"])
    elif not isinstance(test_targets, list) or not test_targets or not all(
        isinstance(path, str) for path in test_targets
    ):
        return _failure("oracle_field_invalid", "test_targets", "test targets must be path strings")
    elif len(test_targets) != len(set(test_targets)):
        return _failure("oracle_field_invalid", "test_targets", "test targets must be unique")
    elif any(not _safe_relative_path(path) for path in test_targets):
        return _failure(
            "oracle_field_invalid", "test_targets", "test targets must be safe relative paths"
        )
    if not isinstance(value["command"], list) or not value["command"] or not all(
        isinstance(part, str) and part for part in value["command"]
    ):
        return _failure("oracle_field_invalid", "command", "oracle command is invalid")
    if any(SECRET_ARGUMENT.search(part) for part in value["command"]):
        return _failure("secret_value_forbidden", "command", "secret-shaped command arguments are forbidden")
    if value["cwd"] != "." and not _safe_relative_path(value["cwd"]):
        return _failure("oracle_field_invalid", "cwd", "oracle cwd is unsafe")
    environment_names = value["environment_names"]
    if (
        not isinstance(environment_names, list)
        or not all(isinstance(name, str) for name in environment_names)
        or len(environment_names) != len(set(environment_names))
        or not all(_matches(ENVIRONMENT_NAME, name) for name in environment_names)
    ):
        return _failure("oracle_field_invalid", "environment_names", "environment names are invalid")
    if not isinstance(value["timeout_seconds"], int) or value["timeout_seconds"] <= 0:
        return _failure("oracle_field_invalid", "timeout_seconds", "oracle timeout is invalid")
    for field in ("expected_failure_kind", "failure_signature"):
        if not isinstance(value[field], str) or not value[field]:
            return _failure("oracle_field_invalid", field, f"{field} is invalid")
    if value["expected_failure_kind"] != EXPECTED_RED_FAILURE_KIND:
        return _failure(
            "oracle_field_invalid",
            "expected_failure_kind",
            f"expected_failure_kind must be {EXPECTED_RED_FAILURE_KIND}",
        )
    if require_observed and (
        not isinstance(value["observed_failure_kind"], str)
        or not value["observed_failure_kind"]
    ):
        return _failure(
            "oracle_field_invalid",
            "observed_failure_kind",
            "observed_failure_kind is invalid",
        )
    if GENERIC_FAILURE_SIGNATURE.fullmatch(value["failure_signature"].strip()):
        return _failure(
            "oracle_failure_signature_invalid",
            "failure_signature",
            "failure signature does not identify the approved missing behavior",
        )
    return _ok(value)


def validate_oracle_candidate(value: object) -> ModelResult:
    return _validate_oracle(value, require_observed=False)


def validate_oracle(value: object) -> ModelResult:
    return _validate_oracle(value, require_observed=True)


def seal_event(candidate: dict, previous_event: dict | None = None) -> ModelResult:
    raw_log = _first_forbidden_field(candidate, RAW_LOG_FIELDS)
    if raw_log is not None:
        return _failure("raw_log_forbidden", raw_log, "raw process logs are not durable evidence")
    secret = _first_secret_field(candidate)
    if secret is not None:
        return _failure("secret_value_forbidden", secret, "secret values are not durable evidence")
    if not _matches(ATTEMPT_ID, candidate.get("attempt_id")):
        return _failure("attempt_id_invalid", "attempt_id", "attempt id is invalid")
    if previous_event is not None and (
        previous_event.get("event_type") == "implementation_green"
        or (
            previous_event.get("event_type") == "stopped"
            and candidate.get("event_type") not in {"resumed", "rebound"}
        )
    ):
        return _failure("terminal_event_chain", "sequence", "terminal event cannot be extended")
    if candidate.get("event_type") in {"red", "green", "refactor"}:
        summary = _validate_test_summary(candidate.get("test_summary"))
        if not summary.ok:
            return summary
    return _ok(dict(candidate))


def validate_human_gate_event(binding: object, event: object) -> ModelResult:
    binding_result = validate_binding(binding)
    if not binding_result.ok:
        return binding_result
    if not isinstance(event, dict) or event.get("event_type") != "human_gate":
        return _failure("human_gate_event_invalid", None, "event is not a human gate decision")
    declaration = next(
        (gate for gate in binding["human_gates"] if gate["gate_id"] == event.get("gate_id")),
        None,
    )
    if declaration is None:
        return _failure("human_gate_undeclared", "gate_id", "human gate is not declared by the plan")
    if declaration["step_id"] != event.get("step_id"):
        return _failure("human_gate_step_mismatch", "step_id", "human gate step differs from its declaration")
    if event.get("result") not in declaration["allowed_results"] or not _matches(
        IDENTITY, event.get("target_identity")
    ):
        return _failure("human_gate_event_invalid", None, "human gate result or target identity is invalid")
    return _ok(event)


def validate_human_gate_boundary(
    binding: object,
    events: list[dict],
    *,
    step_id: str,
    timing: str,
    target_identities: dict[str, str],
) -> ModelResult:
    binding_result = validate_binding(binding)
    if not binding_result.ok:
        return binding_result
    if timing not in HUMAN_GATE_TIMINGS:
        return _failure("human_gate_timing_invalid", "timing", "human gate boundary timing is invalid")
    for event in events:
        if event.get("event_type") == "human_gate":
            validation = validate_human_gate_event(binding, event)
            if not validation.ok:
                return validation

    required = [
        gate
        for gate in binding["human_gates"]
        if gate["step_id"] == step_id
        and HUMAN_GATE_TIMINGS[gate["timing"]] <= HUMAN_GATE_TIMINGS[timing]
    ]
    for gate in required:
        current_identity = target_identities.get(gate["gate_id"])
        if not _matches(IDENTITY, current_identity):
            return _failure("human_gate_target_unavailable", "target_identity", "human gate target identity is unavailable")
        decisions = [
            event
            for event in events
            if event.get("event_type") == "human_gate"
            and event.get("gate_id") == gate["gate_id"]
            and event.get("step_id") == step_id
        ]
        if not decisions:
            return _failure("human_gate_missing", gate["gate_id"], "required human gate has no decision")
        decision = decisions[-1]
        if decision["target_identity"] != current_identity:
            return _failure("human_gate_target_changed", gate["gate_id"], "human gate approval is stale")
        if decision["result"] == "rejected":
            return _failure("human_gate_rejected", gate["gate_id"], "human gate was rejected")
    return _ok(required)


def latest_deliverable(events: list[dict], step_id: str) -> dict | None:
    """The newest artifact or external event of the step: the thing a human approves."""
    for event in reversed(events):
        if event.get("event_type") in {"artifact", "external"} and event.get("step_id") == step_id:
            return event
    return None


def deliverable_is_approved(events: list[dict], step_id: str) -> bool:
    """True when the step's newest artifact/external event has an approved verdict after it."""
    step_events = [event for event in events if event.get("step_id") == step_id]
    target = latest_deliverable(step_events, step_id)
    if target is None:
        return False
    target_identity = content_identity(target)
    after = step_events[step_events.index(target) + 1 :]
    return any(
        event.get("event_type") == "approval"
        and event.get("target_identity") == target_identity
        and event.get("result") == "approved"
        for event in after
    )


def _tdd_step_complete(step_events: list[dict]) -> bool:
    state = "red"
    for event in step_events:
        event_type = event["event_type"]
        if event_type == "red":
            # A resumed execution redoes an unfinished step from RED, so a fresh RED
            # may follow any phase; it restarts the cycle it interrupts.
            state = "green"
        elif event_type == "green":
            # The frozen oracle may be rerun; a repeated pass changes nothing.
            if state not in {"green", "refactor"}:
                return False
            state = "refactor"
        elif event_type == "refactor":
            # Refactoring happens in as many passes as the inspection warrants,
            # each recorded with its own oracle run.
            if state not in {"refactor", "commit"}:
                return False
            state = "commit"
        elif event_type == "commit":
            if state == "commit":
                state = "complete"
            elif state != "complete":
                return False
        elif event_type in {"check", "artifact", "external", "approval"}:
            return False
    return state == "complete"


def _validate_check_step_evidence(step_events: list[dict], step_id: str) -> ModelResult:
    """A check step completes on its own evidence: the checks passed, then the change was committed."""
    if any(event["event_type"] in {"red", "green", "refactor", "artifact", "external", "approval"} for event in step_events):
        return _failure("step_evidence_missing", step_id, f"evidence of another completion kind on a check step: {step_id}")
    positions = [index for index, event in enumerate(step_events) if event["event_type"] == "check"]
    if not positions:
        return _failure("step_evidence_missing", step_id, f"check evidence is missing: {step_id}")
    # A check confirms; it does not produce. A step that changed nothing has nothing to commit,
    # and only the change a check covered has to reach the history.
    if not step_events[positions[-1]].get("files"):
        return _ok(step_id)
    committed = any(
        event["event_type"] == "commit" and index > positions[-1] for index, event in enumerate(step_events)
    )
    if not committed:
        return _failure("step_evidence_missing", step_id, f"the checked change was not committed: {step_id}")
    return _ok(step_id)


def validate_step_evidence(events: list[dict], step_id: str, completion_kind: str) -> ModelResult:
    """Decide whether one step carries the evidence its completion kind demands."""
    step_events = [event for event in events if event.get("step_id") == step_id]
    if completion_kind == "test":
        if not _tdd_step_complete(step_events):
            return _failure("step_evidence_missing", step_id, f"incomplete TDD evidence: {step_id}")
        return _ok(step_id)
    if completion_kind == "check":
        return _validate_check_step_evidence(step_events, step_id)
    if completion_kind not in {"artifact", "external"}:
        return _failure("completion_kind_invalid", step_id, f"unknown completion kind: {completion_kind}")
    if any(event["event_type"] in {"red", "green", "refactor"} for event in step_events):
        return _failure("step_evidence_missing", step_id, f"test evidence on a {completion_kind} step: {step_id}")
    if not deliverable_is_approved(events, step_id):
        return _failure("step_evidence_missing", step_id, f"approved {completion_kind} evidence is missing: {step_id}")
    target = latest_deliverable(step_events, step_id)
    committed = any(
        event["event_type"] == "commit" and step_events.index(event) > step_events.index(target)
        for event in step_events
    )
    if completion_kind == "artifact" and not committed:
        return _failure("step_evidence_missing", step_id, f"artifact is approved but not committed: {step_id}")
    return _ok(step_id)


def _last_rebound(events: list[dict]) -> tuple[int, dict | None]:
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("event_type") == "rebound":
            return index, events[index]
    return -1, None


def effective_binding(binding: dict, events: list[dict]) -> dict:
    """The binding as the last rebound left it: plan, specs, scope and gates follow the revision."""
    _, rebound = _last_rebound(events)
    if rebound is None:
        return dict(binding)
    effective = dict(binding)
    for field in ("plan", "specs", "write_scope", "human_gates"):
        effective[field] = rebound[field]
    return effective


def effective_events(events: list[dict]) -> list[dict]:
    """Events as the rebounds read them: carried steps renumbered, superseded evidence dropped.

    Every rebound applies to what the rebounds before it already left, so evidence one revision
    dropped stays dropped even when a later revision carries a step of the same number."""
    effective: list[dict] = []
    for event in events:
        if event.get("event_type") == "rebound":
            renumbered = {
                entry["previous_step_id"]: entry["step_id"]
                for entry in event["step_map"]
                if entry["previous_step_id"] is not None
            }
            superseded = set(event["superseded_steps"])
            carried: list[dict] = []
            for earlier in effective:
                step_id = earlier.get("step_id")
                if step_id is None:
                    carried.append(earlier)
                elif step_id in superseded or step_id not in renumbered:
                    continue
                else:
                    carried.append(dict(earlier, step_id=renumbered[step_id]))
            effective = carried
        effective.append(event)
    return effective


def derive_result(events: list[dict]) -> dict:
    if not events:
        return {"state": "not_started", "event_count": 0}
    last = events[-1]
    result = {
        "state": "stopped",
        "attempt_id": last["attempt_id"],
        "last_sequence": last["sequence"],
        "event_count": len(events),
    }
    if last["event_type"] == "implementation_green":
        result["state"] = "implementation_green"
        result["commits"] = list(last["commits"])
    elif last["event_type"] == "stopped":
        result["reason"] = last["reason"]
        if "step_id" in last:
            result["step_id"] = last["step_id"]
    elif last["event_type"] == "permission_required":
        result["reason"] = "permission_required"
        result["step_id"] = last["step_id"]
    else:
        result["reason"] = "terminal_event_missing"
    return result
