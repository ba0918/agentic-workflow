#!/usr/bin/env python3
"""Pure validation and state derivation for Cycle execution evidence."""

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
EVENT_TYPES = {
    "worktree-bound": {"outcome"},
    "red": {"step_id", "oracle_identity", "outcome", "exit_code", "observation"},
    "green": {"step_id", "oracle_identity", "outcome", "exit_code", "observation"},
    "refactor": {"step_id", "oracle_identity", "outcome", "observation"},
    "commit": {"step_id", "commit_sha", "outcome"},
    "stopped": {"reason"},
    "implementation_green": {"commits"},
}
RAW_LOG_FIELDS = {"stdout", "stderr", "provider_log", "raw_log"}
SECRET_VALUE_FIELDS = {"environment", "environment_values", "secret", "password", "credential"}


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


def validate_binding(value: object) -> ModelResult:
    required = {
        "version",
        "attempt_id",
        "plan",
        "specs",
        "repository_identity",
        "base_head",
        "branch",
        "write_scope",
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
    executor = value["executor"]
    if not isinstance(executor, dict) or not {"executor", "backend", "session_id"}.issubset(executor):
        return _failure("executor_invalid", "executor", "executor provenance is invalid")
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


def validate_oracle(value: object) -> ModelResult:
    forbidden = _first_forbidden_field(value, SECRET_VALUE_FIELDS)
    if forbidden is not None:
        return _failure("secret_value_forbidden", forbidden, "only environment names may be recorded")
    required = {
        "version",
        "step_id",
        "clauses",
        "test_identity",
        "command",
        "cwd",
        "environment_names",
        "timeout_seconds",
        "expected_failure_kind",
        "observed_failure_kind",
        "failure_signature",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        return _failure("oracle_field_missing", None, "oracle fields are missing")
    if value["version"] != 1 or not isinstance(value["step_id"], str) or not value["step_id"]:
        return _failure("oracle_field_invalid", "step_id", "oracle step is invalid")
    if not isinstance(value["clauses"], list) or not value["clauses"]:
        return _failure("oracle_field_invalid", "clauses", "oracle clauses are invalid")
    if not _matches(IDENTITY, value["test_identity"]):
        return _failure("oracle_field_invalid", "test_identity", "test identity is invalid")
    if not isinstance(value["command"], list) or not value["command"] or not all(
        isinstance(part, str) and part for part in value["command"]
    ):
        return _failure("oracle_field_invalid", "command", "oracle command is invalid")
    if value["cwd"] != "." and not _safe_relative_path(value["cwd"]):
        return _failure("oracle_field_invalid", "cwd", "oracle cwd is unsafe")
    if not isinstance(value["environment_names"], list) or not all(
        isinstance(name, str) and name for name in value["environment_names"]
    ):
        return _failure("oracle_field_invalid", "environment_names", "environment names are invalid")
    if not isinstance(value["timeout_seconds"], int) or value["timeout_seconds"] <= 0:
        return _failure("oracle_field_invalid", "timeout_seconds", "oracle timeout is invalid")
    for field in ("expected_failure_kind", "observed_failure_kind", "failure_signature"):
        if not isinstance(value[field], str) or not value[field]:
            return _failure("oracle_field_invalid", field, f"{field} is invalid")
    return _ok(value)


def event_identity(event: dict) -> str:
    unsigned = {key: value for key, value in event.items() if key != "content_identity"}
    return content_identity(unsigned)


def seal_event(candidate: object, previous_event: dict | None = None) -> ModelResult:
    raw_log = _first_forbidden_field(candidate, RAW_LOG_FIELDS)
    if raw_log is not None:
        return _failure("raw_log_forbidden", raw_log, "raw process logs are not durable evidence")
    secret = _first_forbidden_field(candidate, SECRET_VALUE_FIELDS)
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
    if event_type == "commit" and not _matches(COMMIT_SHA, candidate["commit_sha"]):
        return _failure("event_field_invalid", "commit_sha", "commit SHA is invalid")
    if event_type == "implementation_green" and (
        not isinstance(candidate["commits"], list)
        or not candidate["commits"]
        or any(not _matches(COMMIT_SHA, commit) for commit in candidate["commits"])
    ):
        return _failure("event_field_invalid", "commits", "terminal commits are invalid")

    sealed = dict(candidate)
    sealed["content_identity"] = event_identity(sealed)
    return _ok(sealed)


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
    else:
        result["reason"] = "terminal_event_missing"
    return result
