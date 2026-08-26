"""Pure review-finding rules."""
import hashlib
import json
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
    if finding.get("severity") == "info" and finding.get("action") != "record_only":
        return failure("finding_action_invalid", "info findings are record-only")
    if finding.get("action") == "human_judgment":
        if not str(finding.get("oracle_unavailable_reason", "")).strip():
            return failure("finding_oracle_missing", "human judgment needs an unavailable-oracle reason")
    elif finding.get("severity") != "info" and not str(finding.get("oracle", "")).strip():
        return failure("finding_oracle_missing", "fixable finding needs an oracle")
    if finding.get("id") != finding_id(finding):
        return failure("finding_id_invalid", "finding id does not match its verification contract")
    return ok(dict(finding))

def can_append_after(event: dict) -> bool:
    return event.get("event_type") != "review-completed"

def review_complete(events: list[dict], findings: list[dict]) -> bool:
    if events and events[-1].get("event_type") == "findings_stale":
        return False
    return any(event.get("event_type") == "final-full-review" for event in events) and all(
        finding.get("state") == "closed" for finding in findings
    )
