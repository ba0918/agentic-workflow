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

def reduce_review(events: object) -> Result:
    if not isinstance(events, list):
        return failure("review_event_invalid", "review events must be a list")
    findings: dict[str, dict] = {}
    initial_context: str | None = None
    initial_done = False
    final_context: str | None = None
    final_done = False
    targeted_pending: set[str] = set()
    targeted_seen = False
    stale = False
    second_seen = False
    active_spec_commit: str | None = None
    allowed = {
        "review-bound", "second-review-recorded", "initial-full-review-started",
        "initial-findings-recorded", "targeted-review-started", "targeted-review-result",
        "human-finding-decided", "findings-added", "progress-assessed", "findings_stale",
        "findings-rebound", "final-full-review-started", "final-findings-recorded",
    }
    for expected, event in enumerate(events, 1):
        if (
            not isinstance(event, dict) or event.get("version") != 2
            or event.get("sequence") != expected or event.get("event_type") not in allowed
        ):
            return failure("review_event_invalid", "review event schema is invalid")
        kind = event["event_type"]
        if expected == 1:
            if kind != "review-bound" or not str(event.get("model", "")).strip():
                return failure("review_transition_invalid", "review-bound must be the first event")
            continue
        if kind == "review-bound":
            return failure("review_transition_invalid", "review can bind only once")
        if stale and kind != "findings-rebound":
            return failure("review_transition_invalid", "stale review accepts only rebound")
        if kind == "second-review-recorded":
            status = event.get("status")
            if (
                second_seen or status not in {"completed", "unavailable"}
                or (status == "completed" and not str(event.get("actual_model", "")).strip())
                or (status == "unavailable" and "actual_model" in event)
            ):
                return failure("review_event_invalid", "second review event is invalid")
            second_seen = True
        elif kind == "initial-full-review-started":
            if initial_context is not None or not str(event.get("reviewer_context", "")).strip():
                return failure("review_transition_invalid", "initial review can start only once")
            initial_context = event["reviewer_context"]
        elif kind in {"initial-findings-recorded", "final-findings-recorded"}:
            is_initial = kind.startswith("initial")
            expected_context = initial_context if is_initial else final_context
            if (
                expected_context is None or event.get("reviewer_context") != expected_context
                or not str(event.get("actual_model", "")).strip()
                or not isinstance(event.get("safety"), dict)
                or event["safety"].get("completed") is not True
                or event["safety"].get("unresolved") != []
                or not str(event["safety"].get("summary", "")).strip()
                or not isinstance(event.get("findings"), list)
                or (initial_done if is_initial else final_done)
            ):
                return failure("review_event_invalid", "review findings result is invalid")
            for item in event["findings"]:
                checked = validate_finding(item)
                if not checked.ok:
                    return failure("review_event_invalid", "review finding is invalid")
                if item["id"] in findings:
                    return failure("review_event_invalid", "review finding id is duplicated")
                findings[item["id"]] = dict(item)
                active_spec_commit = active_spec_commit or item["spec_commit"]
            if is_initial:
                initial_done = True
            else:
                final_done = True
        elif kind == "targeted-review-started":
            ids = event.get("finding_ids")
            open_ids = {key for key, item in findings.items() if item.get("state") == "open"}
            if not initial_done or targeted_pending or not isinstance(ids, list) or not ids or set(ids) != open_ids:
                return failure("review_transition_invalid", "targeted review must bind all current open findings")
            targeted_pending = set(ids)
            targeted_seen = True
        elif kind == "targeted-review-result":
            finding_id = event.get("finding_id")
            if finding_id not in targeted_pending or not isinstance(event.get("oracle_exit_code"), int) or not isinstance(event.get("fix_commits"), list):
                return failure("review_transition_invalid", "targeted result has no matching start")
            targeted_pending.remove(finding_id)
            if event["oracle_exit_code"] == 0:
                findings[finding_id]["state"] = "closed"
        elif kind == "human-finding-decided":
            finding_id = event.get("finding_id")
            if finding_id not in findings or findings[finding_id].get("state") != "open" or not str(event.get("reason", "")).strip():
                return failure("review_transition_invalid", "human decision needs an open finding")
            findings[finding_id]["state"] = "closed"
            targeted_pending.discard(finding_id)
        elif kind == "findings-added":
            if not initial_done or not isinstance(event.get("findings"), list) or not isinstance(event.get("terminal_observations"), list):
                return failure("review_event_invalid", "added findings are invalid")
            for item in event["findings"] + event["terminal_observations"]:
                checked = validate_finding(item)
                if not checked.ok or item["id"] in findings:
                    return failure("review_event_invalid", "added finding is invalid or duplicated")
            for item in event["findings"]:
                findings[item["id"]] = dict(item)
        elif kind == "progress-assessed":
            if not targeted_seen or targeted_pending or not isinstance(event.get("progressed"), bool):
                return failure("review_transition_invalid", "progress needs complete targeted results")
        elif kind == "findings_stale":
            if not initial_done or not str(event.get("reason", "")).strip():
                return failure("review_transition_invalid", "only an active review can become stale")
            stale = True
        elif kind == "findings-rebound":
            if not stale or not str(event.get("reason", "")).strip() or re.fullmatch(r"[0-9a-f]{40,64}", str(event.get("spec_commit", ""))) is None:
                return failure("review_transition_invalid", "only stale findings can rebound")
            stale = False
            active_spec_commit = event["spec_commit"]
            findings = {
                finding_id: {**item, "spec_commit": active_spec_commit}
                for finding_id, item in findings.items()
            }
        elif kind == "final-full-review-started":
            if (
                not initial_done or final_context is not None or targeted_pending
                or any(item.get("state") == "open" for item in findings.values())
                or not str(event.get("reviewer_context", "")).strip()
                or event.get("reviewer_context") == initial_context
            ):
                return failure("review_transition_invalid", "final review needs completed initial convergence and fresh context")
            final_context = event["reviewer_context"]
    return ok({
        "findings": list(findings.values()), "stale": stale,
        "initial_started": initial_context is not None, "initial_context": initial_context,
        "initial_done": initial_done, "final_started": final_context is not None,
        "final_context": final_context, "final_done": final_done,
        "targeted_pending": sorted(targeted_pending), "targeted_seen": targeted_seen,
        "active_spec_commit": active_spec_commit,
    })

def can_append_after(event: dict) -> bool:
    return True

def review_complete(events: list[dict], findings: list[dict]) -> bool:
    reduced = reduce_review(events)
    return bool(
        reduced.ok and reduced.value["final_done"] and not reduced.value["stale"]
        and not reduced.value["targeted_pending"]
        and all(finding.get("state") == "closed" for finding in reduced.value["findings"])
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
