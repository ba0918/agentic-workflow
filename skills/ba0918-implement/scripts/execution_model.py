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
EVENT_TYPES = {
    "worktree-bound": {"outcome"},
    "red": {"step_id", "oracle_identity", "outcome", "exit_code", "observation", "test_summary"},
    "green": {"step_id", "oracle_identity", "outcome", "exit_code", "observation", "test_summary"},
    "refactor": {
        "step_id",
        "oracle_identity",
        "outcome",
        "exit_code",
        "observation",
        "test_summary",
    },
    "commit": {"step_id", "commit_sha", "outcome"},
    "human_gate": {"gate_id", "step_id", "target_identity", "result"},
    "permission_required": {"step_id", "operation_identity", "outcome"},
    "stopped": {"reason"},
    "implementation_green": {"commits"},
}
EVENT_OPTIONAL_FIELDS = {
    "worktree-bound": {"repository_identity", "base_head", "branch", "worktree_identity"},
    "stopped": {"step_id"},
}
RAW_LOG_FIELDS = {"stdout", "stderr", "provider_log", "raw_log"}
SECRET_VALUE_FIELDS = {"environment", "environment_values", "secret", "password", "credential"}
SECRET_FIELD = re.compile(r"(?i)(?:api[_-]?key|secret|token|password|credential)")
SECRET_ARGUMENT = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|credential)\s*[=:]\s*\S+"
)
GATE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STEP_ID = re.compile(r"step-[1-9][0-9]*")
CLAUSE_ID = re.compile(r"[A-Z][A-Z0-9]*-[0-9]{3}")
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
            "clauses",
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
        clauses = gate["clauses"]
        if not isinstance(clauses, list) or not clauses or len(clauses) != len(set(clauses)) or any(
            not _matches(CLAUSE_ID, clause) for clause in clauses
        ):
            return _failure("human_gate_binding_invalid", "human_gates.clauses", "human gate clauses are invalid")
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

    plan = value["plan"]
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

    specs = value["specs"]
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

    if not _matches(IDENTITY, value["repository_identity"]):
        return _failure("repository_identity_invalid", "repository_identity", "repository identity is invalid")
    if not _matches(COMMIT_SHA, value["base_head"]):
        return _failure("base_head_invalid", "base_head", "base HEAD is invalid")
    if not isinstance(value["branch"], str) or not value["branch"] or value["branch"].startswith("-"):
        return _failure("branch_invalid", "branch", "branch name is invalid")
    scopes = value["write_scope"]
    if not isinstance(scopes, list) or not scopes or any(not _safe_relative_path(item) for item in scopes):
        return _failure("write_scope_invalid", "write_scope", "write scope is invalid")
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
        "clauses",
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
    if not isinstance(value["clauses"], list) or not value["clauses"]:
        return _failure("oracle_field_invalid", "clauses", "oracle clauses are invalid")
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


def event_identity(event: dict) -> str:
    unsigned = {key: value for key, value in event.items() if key != "content_identity"}
    return content_identity(unsigned)


def seal_event(candidate: object, previous_event: dict | None = None) -> ModelResult:
    raw_log = _first_forbidden_field(candidate, RAW_LOG_FIELDS)
    if raw_log is not None:
        return _failure("raw_log_forbidden", raw_log, "raw process logs are not durable evidence")
    secret = _first_secret_field(candidate)
    if secret is not None:
        return _failure("secret_value_forbidden", secret, "secret values are not durable evidence")
    common = {
        "version",
        "sequence",
        "event_type",
        "attempt_id",
        "plan_identity",
        "spec_identities",
        "previous_identity",
    }
    if not isinstance(candidate, dict) or not common.issubset(candidate):
        return _failure("event_field_missing", None, "common event fields are missing")
    event_type = candidate["event_type"]
    if event_type not in EVENT_TYPES:
        return _failure("event_type_invalid", "event_type", "event type is invalid")
    missing = EVENT_TYPES[event_type] - set(candidate)
    if missing:
        return _failure("event_field_missing", sorted(missing)[0], "event-specific field is missing")
    allowed = common | EVENT_TYPES[event_type] | EVENT_OPTIONAL_FIELDS.get(event_type, set())
    if set(candidate) != allowed and not (
        event_type in EVENT_OPTIONAL_FIELDS and set(candidate).issubset(allowed)
    ):
        return _failure("event_fields_invalid", None, "event fields are unknown or unexpected")
    if candidate["version"] != 1:
        return _failure("event_version_invalid", "version", "unsupported event version")
    if not isinstance(candidate["sequence"], int) or candidate["sequence"] < 1:
        return _failure("event_sequence_invalid", "sequence", "event sequence is invalid")
    if not _matches(ATTEMPT_ID, candidate["attempt_id"]):
        return _failure("attempt_id_invalid", "attempt_id", "attempt id is invalid")
    if not _matches(IDENTITY, candidate["plan_identity"]):
        return _failure("event_identity_invalid", "plan_identity", "plan identity is invalid")
    specs = candidate["spec_identities"]
    if not isinstance(specs, dict) or not specs or any(
        not _safe_relative_path(path)
        or not _matches(IDENTITY, identity)
        for path, identity in specs.items()
    ):
        return _failure("event_identity_invalid", "spec_identities", "spec identities are invalid")

    if previous_event is None:
        if candidate["sequence"] != 1 or candidate["previous_identity"] is not None:
            return _failure("stale_event_chain", "sequence", "first event must start the chain")
    else:
        if previous_event["event_type"] in {"stopped", "implementation_green"}:
            return _failure(
                "terminal_event_chain",
                "previous_identity",
                "terminal event cannot be extended",
            )
        expected_previous = event_identity(previous_event)
        if (
            candidate["sequence"] != previous_event["sequence"] + 1
            or candidate["previous_identity"] != expected_previous
            or candidate["attempt_id"] != previous_event["attempt_id"]
            or candidate["plan_identity"] != previous_event["plan_identity"]
            or candidate["spec_identities"] != previous_event["spec_identities"]
        ):
            return _failure("stale_event_chain", "previous_identity", "event does not extend the current chain")

    if event_type in {"red", "green", "refactor"} and not _matches(
        IDENTITY, candidate["oracle_identity"]
    ):
        return _failure("event_identity_invalid", "oracle_identity", "oracle identity is invalid")
    if event_type in {"red", "green", "refactor"}:
        summary = _validate_test_summary(candidate["test_summary"])
        if not summary.ok:
            return summary
    if event_type == "commit" and not _matches(COMMIT_SHA, candidate["commit_sha"]):
        return _failure("event_field_invalid", "commit_sha", "commit SHA is invalid")
    if event_type == "human_gate" and (
        not _matches(GATE_ID, candidate["gate_id"])
        or not _matches(STEP_ID, candidate["step_id"])
        or not _matches(IDENTITY, candidate["target_identity"])
        or candidate["result"] not in HUMAN_GATE_RESULTS
    ):
        return _failure("event_field_invalid", "human_gate", "human gate event is invalid")
    if event_type == "permission_required" and (
        not _matches(STEP_ID, candidate["step_id"])
        or not _matches(IDENTITY, candidate["operation_identity"])
        or candidate["outcome"] != "permission_required"
    ):
        return _failure("event_field_invalid", "permission_required", "permission event is invalid")
    if event_type == "implementation_green" and (
        not isinstance(candidate["commits"], list)
        or not candidate["commits"]
        or any(not _matches(COMMIT_SHA, commit) for commit in candidate["commits"])
    ):
        return _failure("event_field_invalid", "commits", "terminal commits are invalid")

    sealed = dict(candidate)
    sealed["content_identity"] = event_identity(sealed)
    return _ok(sealed)


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


def compare_event_retry(existing: dict, candidate: dict) -> ModelResult:
    existing_identity = event_identity(existing)
    candidate_identity = event_identity(candidate)
    if (
        existing.get("content_identity") != existing_identity
        or candidate.get("content_identity") != candidate_identity
        or existing_identity != candidate_identity
    ):
        return _failure("event_identity_collision", "content_identity", "event retry differs from stored evidence")
    return _ok(existing)


def derive_result(events: list[dict]) -> dict:
    if not events:
        return {"state": "not_started", "event_count": 0}
    last = events[-1]
    result = {
        "state": "stopped",
        "attempt_id": last["attempt_id"],
        "plan_identity": last["plan_identity"],
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
