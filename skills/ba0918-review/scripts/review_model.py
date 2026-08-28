"""Pure review-finding rules."""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
import re
from typing import NamedTuple


JsonObject = dict[str, object]
SEVERITIES = {"security", "critical", "warn", "info"}
ACTIONS = {"auto_fix", "fix_and_verify", "human_judgment", "record_only"}
STATES = {"open", "closed"}
ALLOWED_EVENTS = {
    "review-bound",
    "second-review-recorded",
    "initial-full-review-started",
    "initial-findings-recorded",
    "targeted-review-started",
    "targeted-review-result",
    "human-finding-decided",
    "findings-added",
    "progress-assessed",
    "findings_stale",
    "findings-rebound",
    "final-full-review-started",
    "final-findings-recorded",
}


class Failure(NamedTuple):
    code: str
    message: str


class Result(NamedTuple):
    value: JsonObject | None
    error: Failure | None

    @property
    def ok(self) -> bool:
        return self.error is None


def ok(value: JsonObject | None = None) -> Result:
    return Result(value, None)


def failure(code: str, message: str) -> Result:
    return Result(None, Failure(code, message))


def _object(value: object) -> JsonObject | None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return None
    return {str(key): item for key, item in value.items()}


def _objects(value: object) -> list[JsonObject] | None:
    if not isinstance(value, list):
        return None
    normalized = [_object(item) for item in value]
    if any(item is None for item in normalized):
        return None
    return [item for item in normalized if item is not None]


def _text(value: JsonObject, field_name: str) -> str | None:
    candidate = value.get(field_name)
    return candidate if isinstance(candidate, str) and candidate.strip() else None


def _oracle_key(finding: JsonObject) -> JsonObject:
    evidence = _object(finding.get("evidence")) or {}
    return {
        "oracle": finding.get("oracle"),
        "oracle_unavailable_reason": finding.get("oracle_unavailable_reason"),
        "path": evidence.get("path"),
        "observation": evidence.get("observation"),
        "specification": finding.get("specification"),
        "root_cause": finding.get("root_cause"),
    }


def finding_id(finding: JsonObject) -> str:
    body = json.dumps(
        _oracle_key(finding),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "finding-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _finding_field_error(finding: JsonObject) -> Failure | None:
    specification = _object(finding.get("specification"))
    evidence = _object(finding.get("evidence"))
    commit = _text(finding, "spec_commit")
    fields_present = (
        specification is not None
        and _text(specification, "path") is not None
        and _text(specification, "section") is not None
        and evidence is not None
        and _text(evidence, "path") is not None
        and _text(evidence, "observation") is not None
        and _text(finding, "root_cause") is not None
        and _text(finding, "profile") is not None
        and commit is not None
        and re.fullmatch(r"[0-9a-f]{40,64}", commit) is not None
    )
    if fields_present:
        return None
    return Failure(
        "finding_field_missing",
        "finding needs specification, evidence, root cause, specification version, and profile",
    )


def _finding_oracle_error(finding: JsonObject) -> Failure | None:
    action = finding.get("action")
    severity = finding.get("severity")
    if action == "human_judgment" and _text(finding, "oracle_unavailable_reason") is None:
        return Failure("finding_oracle_missing", "human judgment needs an unavailable-oracle reason")
    if action != "human_judgment" and severity != "info" and _text(finding, "oracle") is None:
        return Failure("finding_oracle_missing", "fixable finding needs an oracle")
    if action != "human_judgment" and severity != "info" and finding.get("oracle_status") != "failing":
        return Failure(
            "finding_oracle_not_failing",
            "fixable finding oracle must be observed failing before admission",
        )
    return None


def _finding_action_error(finding: JsonObject) -> Failure | None:
    if finding.get("severity") == "info" and finding.get("action") != "record_only":
        return Failure("finding_action_invalid", "info findings are record-only")
    return _finding_oracle_error(finding)


def validate_finding(finding: object) -> Result:
    normalized = _object(finding)
    if normalized is None:
        return failure("finding_invalid", "finding must be an object")
    for field_name, allowed, code, message in (
        ("severity", SEVERITIES, "finding_severity_invalid", "finding severity is invalid"),
        ("action", ACTIONS, "finding_action_invalid", "finding action is invalid"),
        ("state", STATES, "finding_state_invalid", "finding state must be open or closed"),
    ):
        if normalized.get(field_name) not in allowed:
            return failure(code, message)
    field_error = _finding_field_error(normalized)
    if field_error is not None:
        return failure(field_error.code, field_error.message)
    action_error = _finding_action_error(normalized)
    if action_error is not None:
        return failure(action_error.code, action_error.message)
    if normalized.get("id") != finding_id(normalized):
        return failure("finding_id_invalid", "finding id does not match its verification contract")
    return ok(normalized)


class _ReviewState:
    def __init__(self) -> None:
        self.findings: dict[str, JsonObject] = {}
        self.initial_context: str | None = None
        self.initial_done = False
        self.final_context: str | None = None
        self.final_done = False
        self.targeted_pending: set[str] = set()
        self.targeted_seen = False
        self.stale = False
        self.second_seen = False
        self.active_spec_commit: str | None = None

    def apply(self, event: JsonObject) -> Failure | None:
        event_type = _text(event, "event_type")
        if self.stale and event_type != "findings-rebound":
            return Failure("review_transition_invalid", "stale review accepts only rebound")
        handlers: dict[str, Callable[[JsonObject], Failure | None]] = {
            "second-review-recorded": self._second_review,
            "initial-full-review-started": self._initial_start,
            "initial-findings-recorded": self._findings_result,
            "targeted-review-started": self._targeted_start,
            "targeted-review-result": self._targeted_result,
            "human-finding-decided": self._human_decision,
            "findings-added": self._add_findings,
            "progress-assessed": self._progress,
            "findings_stale": self._mark_stale,
            "findings-rebound": self._rebound,
            "final-full-review-started": self._final_start,
            "final-findings-recorded": self._findings_result,
        }
        if event_type == "review-bound":
            return Failure("review_transition_invalid", "review can bind only once")
        handler = handlers.get(event_type or "")
        return handler(event) if handler is not None else Failure(
            "review_event_invalid", "review event schema is invalid"
        )

    def _second_review(self, event: JsonObject) -> Failure | None:
        status = event.get("status")
        invalid = (
            self.second_seen
            or status not in {"completed", "unavailable"}
            or status == "completed" and _text(event, "actual_model") is None
            or status == "unavailable" and "actual_model" in event
        )
        if invalid:
            return Failure("review_event_invalid", "second review event is invalid")
        self.second_seen = True
        return None

    def _initial_start(self, event: JsonObject) -> Failure | None:
        context = _text(event, "reviewer_context")
        if self.initial_context is not None or context is None:
            return Failure("review_transition_invalid", "initial review can start only once")
        self.initial_context = context
        return None

    def _findings_result(self, event: JsonObject) -> Failure | None:
        event_type = _text(event, "event_type") or ""
        is_initial = event_type.startswith("initial")
        expected_context = self.initial_context if is_initial else self.final_context
        findings = _objects(event.get("findings"))
        safety = _object(event.get("safety"))
        already_done = self.initial_done if is_initial else self.final_done
        if not self._valid_result_metadata(event, expected_context, findings, safety, already_done):
            return Failure("review_event_invalid", "review findings result is invalid")
        if findings is None:
            return Failure("review_event_invalid", "review findings result is invalid")
        finding_error = self._store_findings(findings)
        if finding_error is not None:
            return finding_error
        if is_initial:
            self.initial_done = True
        else:
            self.final_done = True
        return None

    @staticmethod
    def _valid_result_metadata(
        event: JsonObject,
        expected_context: str | None,
        findings: list[JsonObject] | None,
        safety: JsonObject | None,
        already_done: bool,
    ) -> bool:
        if expected_context is None or event.get("reviewer_context") != expected_context:
            return False
        if _text(event, "actual_model") is None or findings is None or safety is None or already_done:
            return False
        return (
            safety.get("completed") is True
            and safety.get("unresolved") == []
            and _text(safety, "summary") is not None
        )

    def _store_findings(self, findings: list[JsonObject]) -> Failure | None:
        for item in findings:
            checked = validate_finding(item)
            finding_key = _text(item, "id")
            if not checked.ok or finding_key is None:
                return Failure("review_event_invalid", "review finding is invalid")
            if finding_key in self.findings:
                return Failure("review_event_invalid", "review finding id is duplicated")
            self.findings[finding_key] = item
            self.active_spec_commit = self.active_spec_commit or _text(item, "spec_commit")
        return None

    def _targeted_start(self, event: JsonObject) -> Failure | None:
        finding_ids = event.get("finding_ids")
        open_ids = {
            key for key, item in self.findings.items() if item.get("state") == "open"
        }
        if (
            not self.initial_done
            or self.targeted_pending
            or not isinstance(finding_ids, list)
            or not finding_ids
            or set(finding_ids) != open_ids
        ):
            return Failure(
                "review_transition_invalid",
                "targeted review must bind all current open findings",
            )
        self.targeted_pending = {
            finding_key for finding_key in finding_ids if isinstance(finding_key, str)
        }
        self.targeted_seen = True
        return None

    def _targeted_result(self, event: JsonObject) -> Failure | None:
        finding_key = _text(event, "finding_id")
        execution = _object(event.get("execution"))
        exit_code = event.get("oracle_exit_code")
        if not self._valid_targeted_result(event, execution, finding_key, exit_code):
            return Failure("review_transition_invalid", "targeted result has no matching start")
        if finding_key is None:
            return Failure("review_transition_invalid", "targeted result has no matching start")
        self.targeted_pending.remove(finding_key)
        if exit_code == 0:
            self.findings[finding_key]["state"] = "closed"
        return None

    def _valid_targeted_result(
        self,
        event: JsonObject,
        execution: JsonObject | None,
        finding_key: str | None,
        exit_code: object,
    ) -> bool:
        return (
            finding_key in self.targeted_pending
            and isinstance(exit_code, int)
            and isinstance(event.get("fix_commits"), list)
            and execution is not None
            and _text(execution, "operation") is not None
            and execution.get("working_directory") == "."
            and execution.get("exit_code") == exit_code
            and _text(execution, "summary") is not None
        )

    def _human_decision(self, event: JsonObject) -> Failure | None:
        finding_key = _text(event, "finding_id")
        finding = self.findings.get(finding_key or "")
        if finding is None or finding.get("state") != "open" or _text(event, "reason") is None:
            return Failure("review_transition_invalid", "human decision needs an open finding")
        finding["state"] = "closed"
        self.targeted_pending.discard(finding_key or "")
        return None

    def _add_findings(self, event: JsonObject) -> Failure | None:
        findings = _objects(event.get("findings"))
        observations = _objects(event.get("terminal_observations"))
        if not self.initial_done or findings is None or observations is None:
            return Failure("review_event_invalid", "added findings are invalid")
        for item in [*findings, *observations]:
            finding_key = _text(item, "id")
            if not validate_finding(item).ok or finding_key in self.findings:
                return Failure(
                    "review_event_invalid",
                    "added finding is invalid or duplicated",
                )
        for item in findings:
            finding_key = _text(item, "id")
            if finding_key is not None:
                self.findings[finding_key] = item
        return None

    def _progress(self, event: JsonObject) -> Failure | None:
        if not self.targeted_seen or self.targeted_pending or not isinstance(event.get("progressed"), bool):
            return Failure("review_transition_invalid", "progress needs complete targeted results")
        return None

    def _mark_stale(self, event: JsonObject) -> Failure | None:
        if not self.initial_done or _text(event, "reason") is None:
            return Failure("review_transition_invalid", "only an active review can become stale")
        self.stale = True
        return None

    def _rebound(self, event: JsonObject) -> Failure | None:
        spec_commit = _text(event, "spec_commit")
        if (
            not self.stale
            or _text(event, "reason") is None
            or spec_commit is None
            or re.fullmatch(r"[0-9a-f]{40,64}", spec_commit) is None
        ):
            return Failure("review_transition_invalid", "only stale findings can rebound")
        self.stale = False
        self.active_spec_commit = spec_commit
        self.findings = {
            finding_key: {**item, "spec_commit": spec_commit}
            for finding_key, item in self.findings.items()
        }
        return None

    def _final_start(self, event: JsonObject) -> Failure | None:
        context = _text(event, "reviewer_context")
        invalid = (
            not self.initial_done
            or self.final_context is not None
            or bool(self.targeted_pending)
            or any(item.get("state") == "open" for item in self.findings.values())
            or context is None
            or context == self.initial_context
        )
        if invalid:
            return Failure(
                "review_transition_invalid",
                "final review needs completed initial convergence and fresh context",
            )
        self.final_context = context
        return None

    def result(self) -> JsonObject:
        return {
            "findings": list(self.findings.values()),
            "stale": self.stale,
            "initial_started": self.initial_context is not None,
            "initial_context": self.initial_context,
            "initial_done": self.initial_done,
            "final_started": self.final_context is not None,
            "final_context": self.final_context,
            "final_done": self.final_done,
            "targeted_pending": sorted(self.targeted_pending),
            "targeted_seen": self.targeted_seen,
            "active_spec_commit": self.active_spec_commit,
        }


def reduce_review(events: object) -> Result:
    normalized = _objects(events)
    if normalized is None:
        return failure("review_event_invalid", "review events must be a list")
    state = _ReviewState()
    for expected, event in enumerate(normalized, 1):
        event_type = _text(event, "event_type")
        if (
            event.get("version") != 2
            or event.get("sequence") != expected
            or event_type not in ALLOWED_EVENTS
        ):
            return failure("review_event_invalid", "review event schema is invalid")
        if expected == 1:
            if event_type != "review-bound" or _text(event, "model") is None:
                return failure("review_transition_invalid", "review-bound must be the first event")
            continue
        transition_error = state.apply(event)
        if transition_error is not None:
            return failure(transition_error.code, transition_error.message)
    return ok(state.result())


def review_complete(events: list[JsonObject], findings: list[JsonObject]) -> bool:
    del findings
    reduced = reduce_review(events)
    state = reduced.value
    if not reduced.ok or state is None:
        return False
    targeted_positions = [
        index
        for index, event in enumerate(events)
        if event.get("event_type") == "targeted-review-started"
    ]
    targeted_progress_recorded = not targeted_positions or any(
        event.get("event_type") == "progress-assessed"
        for event in events[targeted_positions[-1] + 1 :]
    )
    reduced_findings = _objects(state.get("findings")) or []
    return bool(
        state.get("final_done") is True
        and state.get("stale") is False
        and state.get("targeted_pending") == []
        and targeted_progress_recorded
        and all(finding.get("state") == "closed" for finding in reduced_findings)
    )


def _severity_count(findings: list[JsonObject], severity: str) -> int:
    return sum(
        finding.get("state") == "open" and finding.get("severity") == severity
        for finding in findings
    )


def open_counts(findings: list[JsonObject]) -> tuple[int, int, int]:
    return (
        _severity_count(findings, "security"),
        _severity_count(findings, "critical"),
        _severity_count(findings, "warn"),
    )


def made_progress(before: list[JsonObject], after: list[JsonObject]) -> bool:
    return open_counts(after) < open_counts(before)


def next_review_stage(events: list[JsonObject], findings: list[JsonObject]) -> str:
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


def admit_new_findings(
    candidates: list[JsonObject],
    related_ids: set[str],
) -> tuple[list[JsonObject], list[JsonObject]]:
    admitted: list[JsonObject] = []
    observations: list[JsonObject] = []
    for candidate in candidates:
        if candidate.get("id") in related_ids or candidate.get("severity") in {
            "security",
            "critical",
        }:
            admitted.append(candidate)
        else:
            observations.append(candidate)
    return admitted, observations
