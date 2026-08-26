"""Pure review-finding rules."""
import hashlib
import json
import re
from typing import Any, NamedTuple

SEVERITIES = {"security", "critical", "warn", "info"}
ACTIONS = {"auto_fix", "fix_and_verify", "human_judgment", "record_only"}
STATES = {"open", "closed"}

class Failure(NamedTuple):
    code: str
    message: str

class Result(NamedTuple):
    value: Any | None
    error: Failure | None
    @property
    def ok(self) -> bool:
        return self.error is None

def ok(value: Any = None) -> Result:
    return Result(value, None)

def failure(code: str, message: str) -> Result:
    return Result(None, Failure(code, message))

def _oracle_key(finding: dict) -> dict:
    evidence = finding.get("evidence") or {}
    return {
        "oracle": finding.get("oracle"),
        "oracle_unavailable_reason": finding.get("oracle_unavailable_reason"),
        "path": evidence.get("path"),
        "observation": evidence.get("observation"),
        "specification": finding.get("specification"),
        "root_cause": finding.get("root_cause"),
    }

def finding_id(finding: dict) -> str:
    body = json.dumps(_oracle_key(finding), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "finding-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]

def validate_finding(finding: object) -> Result:
    if not isinstance(finding, dict):
        return failure("finding_invalid", "finding must be an object")
    if finding.get("severity") not in SEVERITIES:
        return failure("finding_severity_invalid", "finding severity is invalid")
    if finding.get("action") not in ACTIONS:
        return failure("finding_action_invalid", "finding action is invalid")
    if finding.get("state") not in STATES:
        return failure("finding_state_invalid", "finding state must be open or closed")
    specification = finding.get("specification")
    evidence = finding.get("evidence")
    required_text = ("root_cause", "profile")
    if (
        not isinstance(specification, dict)
        or not str(specification.get("path", "")).strip()
        or not str(specification.get("section", "")).strip()
        or not isinstance(evidence, dict)
        or not str(evidence.get("path", "")).strip()
        or not str(evidence.get("observation", "")).strip()
        or any(not str(finding.get(field, "")).strip() for field in required_text)
        or re.fullmatch(r"[0-9a-f]{40,64}", str(finding.get("spec_commit", ""))) is None
    ):
        return failure("finding_field_missing", "finding needs specification, evidence, root cause, specification version, and profile")
    if finding.get("severity") == "info" and finding.get("action") != "record_only":
        return failure("finding_action_invalid", "info findings are record-only")
    if finding.get("action") == "human_judgment":
        if not str(finding.get("oracle_unavailable_reason", "")).strip():
            return failure("finding_oracle_missing", "human judgment needs an unavailable-oracle reason")
    elif finding.get("severity") != "info" and not str(finding.get("oracle", "")).strip():
        return failure("finding_oracle_missing", "fixable finding needs an oracle")
    elif finding.get("severity") != "info" and finding.get("oracle_status") != "failing":
        return failure("finding_oracle_not_failing", "fixable finding oracle must be observed failing before admission")
    if finding.get("id") != finding_id(finding):
        return failure("finding_id_invalid", "finding id does not match its verification contract")
    return ok(dict(finding))

def can_append_after(event: dict) -> bool:
    return event.get("event_type") != "review-completed"

def review_complete(events: list[dict], findings: list[dict]) -> bool:
    if events and events[-1].get("event_type") == "findings_stale":
        return False
    return bool(events) and events[-1].get("event_type") == "review-completed" and all(
        finding.get("state") == "closed" for finding in findings
    )

def open_counts(findings: list[dict]) -> tuple[int, int, int]:
    return tuple(
        sum(finding.get("state") == "open" and finding.get("severity") == severity for finding in findings)
        for severity in ("security", "critical", "warn")
    )

def made_progress(before: list[dict], after: list[dict]) -> bool:
    return open_counts(after) < open_counts(before)

def next_review_stage(events: list[dict], findings: list[dict]) -> str:
    kinds = {event.get("event_type") for event in events}
    if "initial-full-review-started" not in kinds:
        return "initial-full"
    if "initial-findings-recorded" not in kinds:
        return "initial-results"
    if any(finding.get("state") == "open" for finding in findings):
        return "targeted"
    if "final-full-review-started" not in kinds:
        return "final-full"
    if "final-findings-recorded" not in kinds:
        return "final-results"
    return "ready-to-complete"

def admit_new_findings(candidates: list[dict], related_ids: set[str]) -> tuple[list[dict], list[dict]]:
    admitted: list[dict] = []
    observations: list[dict] = []
    for finding in candidates:
        if finding.get("id") in related_ids or finding.get("severity") in {"security", "critical"}:
            admitted.append(finding)
        else:
            observations.append(finding)
    return admitted, observations
