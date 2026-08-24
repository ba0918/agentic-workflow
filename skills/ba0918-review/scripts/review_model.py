#!/usr/bin/env python3
"""Pure validation and derivation for review findings and review evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
import re
from typing import Any, NamedTuple


# The identity, path and secret helpers below mirror the implement skill's execution_model.py on
# purpose: each skill is distributed on its own, so review must not import another skill's
# scripts to validate its own evidence.
IDENTITY = re.compile(r"sha256:[0-9a-f]{64}")
REVIEW_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
COMMIT_SHA = re.compile(r"[0-9a-f]{40,64}")
# A full model id carries a generation; a bare alias such as "opus" cannot be pinned.
MODEL_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9.]+)+")

SEVERITIES = ["security", "critical", "warn", "info"]
ACTIONS = ["auto_fix", "fix_and_verify", "human_judgment", "record_only"]
STATES = ["open", "closed", "stale", "deferred"]
MODEL_SOURCES = ["explicit", "project", "user", "session"]
LEVELS = ["light", "standard"]
ORACLE_KINDS = ["command", "test"]
BOUNDED_TEXT = 500

FINDING_FIELDS = {
    "severity",
    "action",
    "spec_refs",
    "evidence",
    "oracle",
    "oracle_unavailable_reason",
    "root_cause_key",
    "state",
    "spec_identities",
    "profile",
}
FINDING_OPTIONAL_FIELDS = {"id", "oracle_failures"}

TRANSITIONS = {
    ("open", "closed", "oracle_passed"),
    ("open", "closed", "human_decision"),
    ("open", "closed", "human_rejection"),
    ("open", "stale", "spec_revised"),
    ("open", "deferred", "deferred"),
}

COMMON_EVENT_FIELDS = {
    "version",
    "sequence",
    "event_type",
    "review_id",
    "plan_identity",
    "spec_identities",
    "previous_identity",
}
EVENT_TYPES = {
    "review-bound": {"implement_event_identity"},
    "model-selected": {"model", "model_source"},
    "findings-frozen": {
        "findings",
        "findings_identity",
        "model",
        "model_source",
        "level",
        "profile_identities",
        "reviewed_paths",
    },
    "review-incomplete": {"reason"},
    "second-opinion": {"second_reviewer", "second_model"},
    "reverify": {"commits", "verdicts"},
    "findings-added": {"findings", "commits"},
    "decision": {"finding_id", "result"},
    "deferred": {"findings"},
    "findings_stale": {"observed_spec_identities", "verdicts"},
    "rereview-candidate": {"commits", "paths"},
    "warning": {"reason"},
}
EVENT_OPTIONAL_FIELDS = {"decision": {"reason"}}
TERMINAL_EVENT_TYPES = {"findings_stale"}
# Records frozen before the rename carry the event as "findings-fixed"; reading accepts both.
FROZEN_EVENT_TYPES = {"findings-frozen", "findings-fixed"}
RAW_LOG_FIELDS = {"stdout", "stderr", "provider_log", "raw_log"}
SECRET_VALUE_FIELDS = {"environment", "environment_values", "secret", "password", "credential"}
SECRET_FIELD = re.compile(r"(?i)(?:api[_-]?key|secret|token|password|credential)")


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


def _bounded_text(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= BOUNDED_TEXT


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
            if key in SECRET_VALUE_FIELDS or (SECRET_FIELD.search(key) and not isinstance(child, (dict, list))):
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


# ---------------------------------------------------------------- oracle and finding id


def _normalized_oracle(oracle: dict) -> dict:
    normalized = {"kind": oracle["kind"], "cwd": oracle.get("cwd", ".")}
    if oracle["kind"] == "command":
        normalized["command"] = " ".join(oracle["command"].split())
    else:
        normalized["test"] = oracle["test"].strip()
    return normalized


def _validate_oracle(value: object) -> ModelResult:
    if not isinstance(value, dict) or value.get("kind") not in ORACLE_KINDS:
        return _failure("oracle_invalid", "oracle", "oracle kind must be command or test")
    body = value.get("command") if value["kind"] == "command" else value.get("test")
    if not _bounded_text(body):
        return _failure("oracle_invalid", "oracle", "oracle body must be bounded text")
    cwd = value.get("cwd", ".")
    if not _safe_relative_path(cwd):
        return _failure("oracle_invalid", "oracle", "oracle cwd must stay inside the worktree")
    allowed = {"kind", "cwd", "command" if value["kind"] == "command" else "test"}
    if set(value) - allowed:
        return _failure("oracle_invalid", "oracle", "oracle has unknown fields")
    return _ok(_normalized_oracle(value))


def finding_id(oracle: dict) -> str:
    """The stable id of a finding: derived from how it is verified, not where it was seen."""
    checked = _validate_oracle(oracle)
    if not checked.ok:
        raise ValueError(checked.error.message)
    return "f-" + hashlib.sha256(canonical_json(checked.value)).hexdigest()[:16]


def _human_judgment_id(reason: str, evidence: dict) -> str:
    key = {"reason": " ".join(reason.split()), "files": sorted(evidence["files"])}
    return "h-" + hashlib.sha256(canonical_json(key)).hexdigest()[:16]


# ---------------------------------------------------------------- finding


def _validate_spec_refs(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(ref, dict)
            and set(ref) == {"path", "section"}
            and _safe_relative_path(ref["path"])
            and _bounded_text(ref["section"])
            for ref in value
        )
    )


def _validate_evidence(value: object) -> ModelResult:
    if not isinstance(value, dict) or set(value) != {"files", "lines", "summary"}:
        return _failure("evidence_invalid", "evidence", "evidence needs files, lines and summary")
    if not isinstance(value["files"], list) or not value["files"]:
        return _failure("evidence_invalid", "evidence", "evidence needs at least one file")
    if any(not _safe_relative_path(path) for path in value["files"]):
        return _failure("evidence_path_invalid", "evidence", "evidence paths must be repository-relative")
    if not isinstance(value["lines"], list) or any(
        not (isinstance(span, list) and len(span) == 2 and all(isinstance(n, int) and n > 0 for n in span))
        for span in value["lines"]
    ):
        return _failure("evidence_invalid", "evidence", "line spans must be [start, end]")
    if not _bounded_text(value["summary"]):
        return _failure("evidence_invalid", "evidence", "summary must be bounded text")
    return _ok()


def _validate_spec_identities(value: object) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(_safe_relative_path(path) and _matches(IDENTITY, identity) for path, identity in value.items())
    )


def validate_finding(value: object) -> ModelResult:
    """Validate one finding and return it with its derived id (the input is not mutated)."""
    if not isinstance(value, dict):
        return _failure("finding_invalid", None, "finding must be an object")
    missing = FINDING_FIELDS - set(value)
    if missing:
        return _failure("finding_field_missing", sorted(missing)[0], "finding field is missing")
    unknown = set(value) - FINDING_FIELDS - FINDING_OPTIONAL_FIELDS
    if unknown:
        return _failure("finding_fields_invalid", sorted(unknown)[0], "finding has unknown fields")
    raw_log = _first_forbidden_field(value, RAW_LOG_FIELDS)
    if raw_log is not None:
        return _failure("raw_log_forbidden", raw_log, "raw process logs are not finding evidence")
    for field, words in (("severity", SEVERITIES), ("action", ACTIONS), ("state", STATES)):
        if value[field] not in words:
            return _failure(f"{field}_invalid", field, f"{field} must be one of {words}")
    if value["severity"] == "info" and value["action"] != "record_only":
        return _failure("info_action_invalid", "action", "an info finding can only be recorded")
    if not _validate_spec_refs(value["spec_refs"]):
        return _failure("spec_refs_invalid", "spec_refs", "spec refs need path and section")
    evidence = _validate_evidence(value["evidence"])
    if not evidence.ok:
        return evidence
    if not _bounded_text(value["root_cause_key"]):
        return _failure("root_cause_key_invalid", "root_cause_key", "root cause key must be bounded text")
    if not _validate_spec_identities(value["spec_identities"]):
        return _failure("spec_identities_invalid", "spec_identities", "spec identities are invalid")
    if not _bounded_text(value["profile"]):
        return _failure("profile_invalid", "profile", "profile name must be bounded text")
    failures = value.get("oracle_failures", 0)
    if not isinstance(failures, int) or failures < 0:
        return _failure("oracle_failures_invalid", "oracle_failures", "oracle failure count is invalid")

    if value["action"] == "human_judgment":
        if value["oracle"] is not None:
            return _failure("oracle_unexpected", "oracle", "a human judgment finding carries no oracle")
        if not _bounded_text(value["oracle_unavailable_reason"]):
            return _failure(
                "oracle_reason_missing",
                "oracle_unavailable_reason",
                "a human judgment finding must say why no oracle can be written",
            )
        derived_id = _human_judgment_id(value["oracle_unavailable_reason"], value["evidence"])
    else:
        if value["oracle"] is None:
            return _failure("oracle_missing", "oracle", "every machine-checked finding needs an oracle")
        if value["oracle_unavailable_reason"] is not None:
            return _failure("oracle_reason_unexpected", "oracle_unavailable_reason", "reason belongs to human judgment only")
        oracle = _validate_oracle(value["oracle"])
        if not oracle.ok:
            return oracle
        derived_id = finding_id(value["oracle"])
    if "id" in value and value["id"] != derived_id:
        return _failure("finding_id_mismatch", "id", "finding id must be derived from its oracle")

    validated = dict(value)
    validated["id"] = derived_id
    validated.setdefault("oracle_failures", 0)
    return _ok(validated)


def findings_identity(findings: list[dict]) -> str:
    """Identity of a findings set; independent of the order findings were listed in."""
    ordered = sorted(findings, key=lambda finding: finding["id"])
    return content_identity(ordered)


def transition(finding: dict, to_state: str, *, cause: str) -> ModelResult:
    """Return a copy of the finding in the new state when the transition is allowed."""
    if to_state not in STATES:
        return _failure("state_invalid", "state", "unknown state")
    if (finding["state"], to_state, cause) not in TRANSITIONS:
        return _failure("transition_invalid", "state", f"{finding['state']} -> {to_state} by {cause} is not allowed")
    if cause == "oracle_passed" and finding["action"] == "human_judgment":
        return _failure("transition_invalid", "state", "a human judgment finding does not close on an oracle result")
    if cause == "human_decision" and finding["action"] != "human_judgment":
        return _failure("transition_invalid", "state", "only a human judgment finding closes on an acceptance")
    moved = dict(finding)
    moved["state"] = to_state
    return _ok(moved)


def current_findings(events: list[dict]) -> dict[str, dict]:
    """The set as of the latest event: frozen findings plus later-joined ones, states applied.

    Deferred findings never join the set, and a decision closes its finding whatever the
    result: a rejection is the human's word that the finding will not be fixed."""
    findings: dict[str, dict] = {}
    for event in events:
        event_type = event["event_type"]
        if event_type in FROZEN_EVENT_TYPES | {"findings-added"}:
            for finding in event["findings"]:
                # An id that is already in the set keeps its state: a later submission of the
                # same finding must not undo a verdict or a human decision.
                findings.setdefault(finding["id"], dict(finding))
        elif event_type in {"reverify", "findings_stale"}:
            for verdict in event["verdicts"]:
                finding = findings.get(verdict["finding_id"])
                if finding is None:
                    continue
                finding["state"] = verdict["state"]
                finding["oracle_failures"] = verdict.get("oracle_failures", finding.get("oracle_failures", 0))
                if verdict.get("escalated"):
                    finding["action"] = "human_judgment"
        elif event_type == "decision":
            finding = findings.get(event["finding_id"])
            if finding is not None:
                finding["state"] = "closed"
    return findings


def group_by_root_cause(findings: list[dict]) -> dict[str, list[str]]:
    """One fix unit per root cause; ids and oracles stay individual."""
    groups: dict[str, list[str]] = {}
    for finding in findings:
        groups.setdefault(finding["root_cause_key"], []).append(finding["id"])
    return {key: sorted(ids) for key, ids in groups.items()}


# ---------------------------------------------------------------- review events


def event_identity(event: dict) -> str:
    body = {key: value for key, value in event.items() if key != "content_identity"}
    return content_identity(body)


def _validate_event_body(candidate: dict) -> ModelResult:
    event_type = candidate["event_type"]
    if event_type == "review-bound" and not _matches(IDENTITY, candidate["implement_event_identity"]):
        return _failure("event_field_invalid", "implement_event_identity", "implement event identity is invalid")
    if event_type in {"model-selected", "findings-frozen"}:
        if not _matches(MODEL_ID, candidate["model"]):
            return _failure("model_id_invalid", "model", "model must be a full model id, not an alias")
        if candidate["model_source"] not in MODEL_SOURCES:
            return _failure("model_source_invalid", "model_source", f"model source must be one of {MODEL_SOURCES}")
    if event_type == "second-opinion":
        if not _bounded_text(candidate["second_reviewer"]):
            return _failure("event_field_invalid", "second_reviewer", "second reviewer must be bounded text")
        if not _matches(MODEL_ID, candidate["second_model"]):
            return _failure("model_id_invalid", "second_model", "model must be a full model id, not an alias")
    if event_type in {"findings-frozen", "findings-added", "deferred"}:
        findings = candidate["findings"]
        if not isinstance(findings, list):
            return _failure("event_field_invalid", "findings", "findings must be a list")
        for finding in findings:
            checked = validate_finding(finding)
            if not checked.ok:
                return checked
    if event_type == "findings-frozen":
        if candidate["findings_identity"] != findings_identity(candidate["findings"]):
            return _failure("event_field_invalid", "findings_identity", "findings identity does not match the findings")
        if candidate["level"] not in LEVELS:
            return _failure("level_invalid", "level", f"level must be one of {LEVELS}")
        if not _validate_spec_identities(candidate["profile_identities"]):
            return _failure("event_field_invalid", "profile_identities", "profile identities are invalid")
        if not isinstance(candidate["reviewed_paths"], list) or any(
            not _safe_relative_path(path) for path in candidate["reviewed_paths"]
        ):
            return _failure("event_field_invalid", "reviewed_paths", "reviewed paths must be repository-relative")
    if event_type in {"reverify", "findings-added", "rereview-candidate"}:
        commits = candidate["commits"]
        if not isinstance(commits, list) or any(not _matches(COMMIT_SHA, sha) for sha in commits):
            return _failure("event_field_invalid", "commits", "commit SHAs are invalid")
    if event_type in {"reverify", "findings_stale"}:
        verdicts = candidate["verdicts"]
        if not isinstance(verdicts, list) or any(
            not (isinstance(v, dict) and set(v) >= {"finding_id", "state"} and v["state"] in STATES)
            for v in verdicts
        ):
            return _failure("event_field_invalid", "verdicts", "verdicts need finding_id and state")
    if event_type == "decision":
        if not isinstance(candidate["finding_id"], str) or candidate["result"] not in ("accepted", "rejected"):
            return _failure("event_field_invalid", "decision", "decision needs finding_id and accepted/rejected")
        if "reason" in candidate and not _bounded_text(candidate["reason"]):
            return _failure("event_field_invalid", "reason", "a decision reason must be bounded text")
        if candidate["result"] == "rejected" and "reason" not in candidate:
            return _failure("decision_reason_missing", "reason", "a rejection must say why the finding is not fixed")
    if event_type == "findings_stale" and not _validate_spec_identities(candidate["observed_spec_identities"]):
        return _failure("event_field_invalid", "observed_spec_identities", "observed spec identities are invalid")
    if event_type == "rereview-candidate" and (
        not isinstance(candidate["paths"], list) or any(not _safe_relative_path(p) for p in candidate["paths"])
    ):
        return _failure("event_field_invalid", "paths", "paths must be repository-relative")
    if event_type in {"warning", "review-incomplete"} and not _bounded_text(candidate["reason"]):
        return _failure("event_field_invalid", "reason", "reason must be bounded text")
    return _ok()


def seal_review_event(candidate: object, previous_event: dict | None = None) -> ModelResult:
    """Validate a review event against its type and the chain, and stamp its identity."""
    raw_log = _first_forbidden_field(candidate, RAW_LOG_FIELDS)
    if raw_log is not None:
        return _failure("raw_log_forbidden", raw_log, "raw process logs are not durable evidence")
    secret_field = _first_secret_field(candidate)
    if secret_field is not None:
        return _failure("secret_value_forbidden", secret_field, "secret values are not durable evidence")
    if not isinstance(candidate, dict) or not COMMON_EVENT_FIELDS.issubset(candidate):
        return _failure("event_field_missing", None, "common event fields are missing")
    event_type = candidate["event_type"]
    if event_type not in EVENT_TYPES:
        return _failure("event_type_invalid", "event_type", "event type is invalid")
    missing = EVENT_TYPES[event_type] - set(candidate)
    if missing:
        return _failure("event_field_missing", sorted(missing)[0], "event-specific field is missing")
    allowed = COMMON_EVENT_FIELDS | EVENT_TYPES[event_type] | EVENT_OPTIONAL_FIELDS.get(event_type, set())
    if set(candidate) - allowed:
        return _failure("event_fields_invalid", None, "event fields are unknown or unexpected")
    if candidate["version"] != 1:
        return _failure("event_version_invalid", "version", "unsupported event version")
    if not isinstance(candidate["sequence"], int) or candidate["sequence"] < 1:
        return _failure("event_sequence_invalid", "sequence", "event sequence is invalid")
    if not _matches(REVIEW_ID, candidate["review_id"]):
        return _failure("review_id_invalid", "review_id", "review id is invalid")
    if not _matches(IDENTITY, candidate["plan_identity"]):
        return _failure("event_identity_invalid", "plan_identity", "plan identity is invalid")
    if not _validate_spec_identities(candidate["spec_identities"]):
        return _failure("event_identity_invalid", "spec_identities", "spec identities are invalid")

    if previous_event is None:
        if event_type != "review-bound" or candidate["sequence"] != 1 or candidate["previous_identity"] is not None:
            return _failure("stale_event_chain", "sequence", "first event must bind the review")
    else:
        if previous_event["event_type"] in TERMINAL_EVENT_TYPES:
            return _failure("terminal_event_chain", "previous_identity", "terminal event cannot be extended")
        if (
            candidate["sequence"] != previous_event["sequence"] + 1
            or candidate["previous_identity"] != event_identity(previous_event)
            or candidate["review_id"] != previous_event["review_id"]
            or candidate["plan_identity"] != previous_event["plan_identity"]
            or candidate["spec_identities"] != previous_event["spec_identities"]
        ):
            return _failure("stale_event_chain", "previous_identity", "event does not extend the current chain")

    body = _validate_event_body(candidate)
    if not body.ok:
        return body
    sealed = dict(candidate)
    sealed["content_identity"] = event_identity(sealed)
    return _ok(sealed)
