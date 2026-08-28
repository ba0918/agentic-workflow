"""Review finding transitions and convergence rules."""
from __future__ import annotations

import inspect
from pathlib import Path
import re

import review_model
from review_support.events import append_event, current_findings, findings_stale, load_events
from review_support.finding_validation import (
    validate_finding_for_binding as _validate_finding_for_binding,
)
from review_support.repository import commit, git
from review_support.types import (
    JsonObject,
    RuntimeResult,
    failure,
    object_value,
    object_values,
    ok,
    string_values,
)
from review_support.validation import bounded_text, review_execution


def validate_finding_for_binding(
    root: Path,
    binding: JsonObject,
    item: object,
    *,
    spec_commit: str | None = None,
) -> RuntimeResult[JsonObject]:
    """Preserve the public finding validator while delegating its pure rules."""

    return _validate_finding_for_binding(
        binding,
        item,
        spec_commit=spec_commit,
        commit_exists=lambda value: commit(root, value).ok,
    )


def _review_state(events: list[JsonObject]) -> JsonObject:
    reduced = review_model.reduce_review(events)
    assert reduced.ok and reduced.value is not None
    return reduced.value


def record_second_review(
    root: Path,
    binding: JsonObject,
    *,
    status: str,
    actual_model: str | None,
    summary: str,
) -> RuntimeResult[JsonObject]:
    """Record the optional second reviewer exactly once."""

    options = object_value(binding.get("review_options")) or {}
    if not options.get("second_reviewer"):
        return RuntimeResult(None, failure("second_reviewer_not_requested", "second review was not explicitly requested").error)
    checked_summary = bounded_text(summary)
    checked_model = bounded_text(actual_model) if actual_model is not None else None
    completed_invalid = status == "completed" and (checked_model is None or not checked_model.ok)
    unavailable_invalid = status == "unavailable" and actual_model is not None
    if status not in {"completed", "unavailable"} or not checked_summary.ok:
        return RuntimeResult(None, failure("second_review_invalid", "second review result needs status, model, and summary").error)
    if completed_invalid or unavailable_invalid:
        return RuntimeResult(None, failure("second_review_invalid", "second review result needs status, model, and summary").error)
    events = load_events(root, binding)
    if not events.ok:
        return RuntimeResult(None, events.error)
    if any(event.get("event_type") == "second-review-recorded" for event in events.required()):
        return RuntimeResult(None, failure("second_review_already_recorded", "second reviewer runs only once").error)
    fields: JsonObject = {
        "status": status,
        "reviewer": options["second_reviewer"],
        "requested_model": options.get("second_model"),
        "summary": checked_summary.required(),
    }
    if checked_model is not None:
        fields["actual_model"] = checked_model.required()
    return append_event(root, binding, "second-review-recorded", fields)


def _targeted_review(
    root: Path,
    binding: JsonObject,
    state: JsonObject,
    reviewer_context: str,
) -> RuntimeResult[JsonObject]:
    findings = object_values(state.get("findings")) or []
    if state.get("targeted_pending"):
        return RuntimeResult(None, failure("stage_results_required", "targeted review must update findings before another stage").error)
    return append_event(root, binding, "targeted-review-started", {
        "reviewer_context": reviewer_context,
        "finding_ids": sorted(
            str(item["id"])
            for item in findings
            if item.get("state") == "open"
        ),
    })


def _final_stage(
    root: Path,
    binding: JsonObject,
    events: list[JsonObject],
    state: JsonObject,
    reviewer_context: str,
) -> RuntimeResult[JsonObject]:
    targeted = [
        index
        for index, event in enumerate(events)
        if event.get("event_type") == "targeted-review-started"
    ]
    assessed = not targeted or any(
        event.get("event_type") == "progress-assessed"
        for event in events[targeted[-1] + 1 :]
    )
    if not assessed:
        return RuntimeResult(None, failure("progress_assessment_required", "targeted convergence needs lexicographic progress evidence").error)
    if reviewer_context == state.get("initial_context"):
        return RuntimeResult(None, failure("fresh_context_required", "final full review needs a different context").error)
    return append_event(
        root,
        binding,
        "final-full-review-started",
        {"reviewer_context": reviewer_context},
    )


def _stage_after_initial(
    root: Path,
    binding: JsonObject,
    events: list[JsonObject],
    state: JsonObject,
    context: str,
) -> RuntimeResult[JsonObject]:
    findings = object_values(state.get("findings")) or []
    if any(item.get("state") == "open" for item in findings):
        return _targeted_review(root, binding, state, context)
    if not state.get("final_started"):
        return _final_stage(root, binding, events, state, context)
    if not state.get("final_done"):
        return RuntimeResult(None, failure("stage_results_required", "final full review results must be recorded").error)
    if any(item.get("state") == "open" for item in current_findings(events)):
        return _targeted_review(root, binding, state, context)
    return ok({"event_type": "ready-to-complete"})


def _stage_blocker(
    events: list[JsonObject],
    state: JsonObject,
) -> RuntimeResult[object] | None:
    if not events or events[0].get("event_type") != "review-bound":
        return failure("review_not_bound", "review input must be bound first")
    if state.get("stale"):
        return failure("findings_stale", "review findings need a human-approved rebound")
    return None


def begin_stage(
    root: Path,
    binding: JsonObject,
    *,
    reviewer_context: str,
) -> RuntimeResult[JsonObject]:
    """Begin the next required full or targeted review stage."""

    checked_context = bounded_text(reviewer_context)
    if not checked_context.ok:
        return RuntimeResult(None, failure("review_context_invalid", "reviewer context must be safe bounded text").error)
    events_result = load_events(root, binding)
    if not events_result.ok:
        return RuntimeResult(None, events_result.error)
    events = events_result.required()
    state = _review_state(events)
    blocked = _stage_blocker(events, state)
    if blocked is not None:
        return RuntimeResult(None, blocked.error)
    context = checked_context.required()
    if not state.get("initial_started"):
        return append_event(root, binding, "initial-full-review-started", {"reviewer_context": context})
    if not state.get("initial_done"):
        return RuntimeResult(None, failure("stage_results_required", "initial full review results must be recorded").error)
    return _stage_after_initial(root, binding, events, state, context)


def _validated_stage_payload(
    stage: object,
    findings: object,
    safety: object,
    actual_model: object,
) -> RuntimeResult[tuple[str, list[JsonObject], JsonObject, str, str]]:
    finding_values = object_values(findings)
    safety_value = object_value(safety)
    checked_model = bounded_text(actual_model)
    checked_summary = bounded_text(safety_value.get("summary") if safety_value is not None else None)
    valid_safety = (
        stage in {"initial", "final"}
        and finding_values is not None
        and safety_value is not None
        and safety_value.get("completed") is True
        and safety_value.get("unresolved") == []
    )
    if not valid_safety or not checked_summary.ok or not checked_model.ok:
        code = "bounded_text_invalid" if not checked_summary.ok or not checked_model.ok else "safety_check_required"
        return RuntimeResult(None, failure(code, "initial and final review require safe bounded model and safety results").error)
    assert isinstance(stage, str)
    assert finding_values is not None
    assert safety_value is not None
    return ok((stage, finding_values, safety_value, checked_model.required(), checked_summary.required()))


def _validate_stage_findings(
    root: Path,
    binding: JsonObject,
    findings: list[JsonObject],
    spec_commit: str,
) -> RuntimeResult[None]:
    identifiers: set[str] = set()
    for item in findings:
        checked = validate_finding_for_binding(root, binding, item, spec_commit=spec_commit)
        if not checked.ok:
            return RuntimeResult(None, checked.error)
        identifier = str(item["id"])
        if identifier in identifiers:
            return RuntimeResult(None, failure("finding_duplicate", "finding ids must be unique").error)
        severity = item.get("severity")
        state = item.get("state")
        if (severity == "info" and state != "closed") or (severity != "info" and state != "open"):
            return RuntimeResult(None, failure("finding_state_invalid", "new fixable findings are open and info observations are closed").error)
        identifiers.add(identifier)
    return ok()


class RecordFindings:
    """Callable adapter preserving the full-review result facade."""

    __signature__ = inspect.Signature(
        parameters=(
            inspect.Parameter("root", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("binding", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("stage", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("findings", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("safety", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("reviewer_context", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("actual_model", inspect.Parameter.KEYWORD_ONLY, default=None),
        )
    )

    def __call__(
        self,
        root: Path,
        binding: JsonObject,
        **options: object,
    ) -> RuntimeResult[JsonObject]:
        allowed = {"stage", "findings", "safety", "reviewer_context", "actual_model"}
        if set(options) - allowed:
            unexpected = sorted(set(options) - allowed)[0]
            raise TypeError(f"unexpected keyword argument: {unexpected}")
        if options.get("actual_model") is None:
            return RuntimeResult(None, failure("actual_model_required", "review stage result needs the actual reviewer model").error)
        payload = _validated_stage_payload(
            options.get("stage"),
            options.get("findings"),
            options.get("safety"),
            options.get("actual_model"),
        )
        if not payload.ok:
            return RuntimeResult(None, payload.error)
        reviewer_context = options.get("reviewer_context")
        if not isinstance(reviewer_context, str):
            raise TypeError("missing required keyword-only argument: reviewer_context")
        return _record_findings(root, binding, payload.required(), reviewer_context)


record_findings = RecordFindings()


def _stage_result_type(
    events: list[JsonObject],
    stage: str,
    reviewer_context: str,
) -> RuntimeResult[str]:
    start_type = f"{stage}-full-review-started"
    result_type = f"{stage}-findings-recorded"
    start = next((event for event in reversed(events) if event.get("event_type") == start_type), None)
    if start is None or start.get("reviewer_context") != reviewer_context:
        return RuntimeResult(None, failure("review_context_mismatch", "finding results must match their review context").error)
    if any(event.get("event_type") == result_type for event in events):
        return RuntimeResult(None, failure("findings_already_recorded", "stage findings are append-only").error)
    return ok(result_type)


def _record_findings(
    root: Path,
    binding: JsonObject,
    payload: tuple[str, list[JsonObject], JsonObject, str, str],
    reviewer_context: str,
) -> RuntimeResult[JsonObject]:
    stage, findings, _safety, actual_model, summary = payload
    loaded = load_events(root, binding)
    if not loaded.ok:
        return RuntimeResult(None, loaded.error)
    events = loaded.required()
    if findings_stale(events):
        return RuntimeResult(None, failure("findings_stale", "stale findings allow only a human-approved rebound").error)
    result_type = _stage_result_type(events, stage, reviewer_context)
    if not result_type.ok:
        return RuntimeResult(None, result_type.error)
    state_commit = _review_state(events).get("active_spec_commit")
    active_commit = state_commit if isinstance(state_commit, str) else str(
        binding.get("spec_commit") or binding.get("approval_commit") or ""
    )
    checked = _validate_stage_findings(root, binding, findings, active_commit)
    if not checked.ok:
        return RuntimeResult(None, checked.error)
    return append_event(root, binding, result_type.required(), {
        "findings": findings,
        "safety": {"completed": True, "summary": summary, "unresolved": []},
        "reviewer_context": reviewer_context,
        "actual_model": actual_model,
    })


def _commit_has_trailer(root: Path, commit_id: str, finding_id: str) -> bool:
    resolved = commit(root, commit_id)
    if not resolved.ok:
        return False
    message = git(root, "show", "-s", "--format=%B", resolved.required()).stdout
    return re.search(rf"(?m)^Finding:\s*{re.escape(finding_id)}\s*$", message) is not None


def _bound_trailer_commits(
    root: Path,
    binding: JsonObject,
    finding_id: str,
    selected_fix_head: str | None = None,
) -> RuntimeResult[list[str]]:
    review_input = object_value(binding.get("input")) or {}
    base = review_input.get("base") or binding.get("approval_commit")
    branch = review_input.get("branch") or binding.get("branch")
    original_head = review_input.get("head") or binding.get("head")
    head = f"refs/heads/{branch}" if branch else selected_fix_head or original_head
    if not base or not head:
        return RuntimeResult(None, failure("fix_commit_unlinked", "review input has no bounded commit range").error)
    if not branch and selected_fix_head:
        resolved = commit(root, selected_fix_head)
        descends = resolved.ok and original_head and git(
            root,
            "merge-base",
            "--is-ancestor",
            str(original_head),
            resolved.required(),
        ).returncode == 0
        if not descends:
            return RuntimeResult(None, failure("fix_commit_unlinked", "selected fix head must descend from the reviewed head").error)
        base = original_head
        head = resolved.required()
    history = git(root, "rev-list", "--reverse", f"{base}..{head}")
    if history.returncode != 0:
        return RuntimeResult(None, failure("fix_commit_unlinked", "review commit range is unavailable").error)
    return ok([
        commit_id
        for commit_id in history.stdout.splitlines()
        if _commit_has_trailer(root, commit_id, finding_id)
    ])


def _targeted_index(events: list[JsonObject], finding_id: str) -> int | None:
    positions = [
        index
        for index, event in enumerate(events)
        if event.get("event_type") == "targeted-review-started"
        and finding_id in (string_values(event.get("finding_ids")) or [])
    ]
    return positions[-1] if positions else None


def _targeted_result_exists(events: list[JsonObject], finding_id: str, start: int) -> bool:
    return any(
        event.get("event_type") == "targeted-review-result"
        and event.get("finding_id") == finding_id
        for event in events[start + 1 :]
    )


def _open_finding(events: list[JsonObject], finding_id: str) -> JsonObject | None:
    return next(
        (
            candidate
            for candidate in current_findings(events)
            if candidate.get("id") == finding_id and candidate.get("state") == "open"
        ),
        None,
    )


def _close_finding(
    root: Path,
    binding: JsonObject,
    finding_id: str,
    options: JsonObject,
) -> RuntimeResult[JsonObject]:
    oracle_exit_code = options.get("oracle_exit_code")
    fix_commits = string_values(options.get("fix_commits")) or []
    operation = options.get("operation")
    summary = options.get("result_summary")
    if not isinstance(oracle_exit_code, int) or not isinstance(operation, str) or not isinstance(summary, str):
        raise TypeError("close_finding requires oracle result options")
    execution = review_execution(operation, oracle_exit_code, summary)
    if not execution.ok:
        return RuntimeResult(None, execution.error)
    closing = _closing_state(root, binding, finding_id)
    if not closing.ok:
        return RuntimeResult(None, closing.error)
    if oracle_exit_code != 0:
        return RuntimeResult(None, failure("finding_oracle_failed", "finding oracle still fails").error)
    linked = _bound_trailer_commits(
        root,
        binding,
        finding_id,
        fix_commits[-1] if fix_commits else None,
    )
    if not linked.ok or not fix_commits or linked.required() != fix_commits:
        return RuntimeResult(None, failure("fix_commit_unlinked", "every fix commit must exist and carry the finding trailer").error)
    return append_event(root, binding, "targeted-review-result", {
        "finding_id": finding_id,
        "oracle_exit_code": oracle_exit_code,
        "fix_commits": fix_commits,
        "execution": execution.required(),
    })


def _closing_state(
    root: Path,
    binding: JsonObject,
    finding_id: str,
) -> RuntimeResult[list[JsonObject]]:
    loaded = load_events(root, binding)
    if not loaded.ok:
        return RuntimeResult(None, loaded.error)
    events = loaded.required()
    if _open_finding(events, finding_id) is None:
        return RuntimeResult(None, failure("finding_not_open", "only an open admitted finding can close").error)
    targeted = _targeted_index(events, finding_id)
    if targeted is None:
        return RuntimeResult(None, failure("targeted_review_required", "finding can close only after its targeted review starts").error)
    if _targeted_result_exists(events, finding_id, targeted):
        return RuntimeResult(None, failure("targeted_result_exists", "targeted review already recorded this finding result").error)
    return ok(events)


class CloseFinding:
    """Callable adapter preserving finding closure parameters."""

    __signature__ = inspect.Signature(
        parameters=(
            inspect.Parameter("root", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("binding", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("finding_id", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("oracle_exit_code", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("fix_commits", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("operation", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("result_summary", inspect.Parameter.KEYWORD_ONLY),
        )
    )

    def __call__(
        self,
        root: Path,
        binding: JsonObject,
        finding_id: str,
        **options: object,
    ) -> RuntimeResult[JsonObject]:
        allowed = {"oracle_exit_code", "fix_commits", "operation", "result_summary"}
        if set(options) != allowed:
            raise TypeError("close_finding requires all keyword-only arguments")
        return _close_finding(root, binding, finding_id, dict(options))


close_finding = CloseFinding()


def record_human_decision(
    root: Path,
    binding: JsonObject,
    finding_id: str,
    *,
    decision: str,
    reason: str,
) -> RuntimeResult[JsonObject]:
    """Record a human finding disposition without inferring it."""

    events = load_events(root, binding)
    if not events.ok:
        return RuntimeResult(None, events.error)
    values = events.required()
    if findings_stale(values):
        return RuntimeResult(None, failure("findings_stale", "stale findings allow only a human-approved rebound").error)
    if _open_finding(values, finding_id) is None:
        return RuntimeResult(None, failure("finding_not_open", "only an open admitted finding can receive a human decision").error)
    checked_decision = bounded_text(decision)
    checked_reason = bounded_text(reason)
    if not checked_decision.ok or not checked_reason.ok:
        return RuntimeResult(None, failure("human_decision_invalid", "human decision and reason must be non-empty").error)
    return append_event(root, binding, "human-finding-decided", {
        "finding_id": finding_id,
        "decision": checked_decision.required(),
        "reason": checked_reason.required(),
    })


def _record_failed_target(
    root: Path,
    binding: JsonObject,
    finding_id: str,
    options: JsonObject,
) -> RuntimeResult[JsonObject]:
    oracle_exit_code = options.get("oracle_exit_code")
    fix_commits = string_values(options.get("fix_commits")) or []
    operation = options.get("operation")
    summary = options.get("result_summary")
    if not isinstance(oracle_exit_code, int) or not isinstance(operation, str) or not isinstance(summary, str):
        raise TypeError("record_targeted_result requires oracle result options")
    execution = review_execution(operation, oracle_exit_code, summary)
    if not execution.ok:
        return RuntimeResult(None, execution.error)
    loaded = load_events(root, binding)
    if not loaded.ok:
        return RuntimeResult(None, loaded.error)
    events = loaded.required()
    targeted = _targeted_index(events, finding_id)
    if targeted is None:
        return RuntimeResult(None, failure("targeted_review_required", "finding result needs a corresponding targeted review").error)
    if _targeted_result_exists(events, finding_id, targeted):
        return RuntimeResult(None, failure("targeted_result_exists", "targeted review already recorded this finding result").error)
    if any(not _commit_has_trailer(root, commit_id, finding_id) for commit_id in fix_commits):
        return RuntimeResult(None, failure("fix_commit_unlinked", "every fix commit must exist and carry the finding trailer").error)
    return append_event(root, binding, "targeted-review-result", {
        "finding_id": finding_id,
        "oracle_exit_code": oracle_exit_code,
        "fix_commits": fix_commits,
        "execution": execution.required(),
    })


class RecordTargetedResult:
    """Callable adapter preserving targeted result parameters."""

    __signature__ = CloseFinding.__signature__

    def __call__(
        self,
        root: Path,
        binding: JsonObject,
        finding_id: str,
        **options: object,
    ) -> RuntimeResult[JsonObject]:
        allowed = {"oracle_exit_code", "fix_commits", "operation", "result_summary"}
        if set(options) != allowed:
            raise TypeError("record_targeted_result requires all keyword-only arguments")
        normalized = dict(options)
        if normalized.get("oracle_exit_code") == 0:
            return _close_finding(root, binding, finding_id, normalized)
        return _record_failed_target(root, binding, finding_id, normalized)


record_targeted_result = RecordTargetedResult()


def add_findings(
    root: Path,
    binding: JsonObject,
    *,
    candidates: list[JsonObject],
    related_ids: set[str],
) -> RuntimeResult[JsonObject]:
    """Admit newly discovered findings during convergence."""

    events = load_events(root, binding)
    if not events.ok:
        return RuntimeResult(None, events.error)
    values = events.required()
    existing_ids = {str(item["id"]) for item in current_findings(values)}
    state_commit = _review_state(values).get("active_spec_commit")
    active_spec_commit = (
        state_commit
        if isinstance(state_commit, str)
        else str(binding.get("spec_commit") or binding.get("approval_commit") or "")
    )
    for item in candidates:
        checked = validate_finding_for_binding(root, binding, item, spec_commit=active_spec_commit)
        if not checked.ok:
            return RuntimeResult(None, checked.error)
    admitted, observations = review_model.admit_new_findings(candidates, related_ids)
    if any(str(item["id"]) in existing_ids for item in admitted):
        return RuntimeResult(None, failure("finding_duplicate", "an admitted finding id already exists").error)
    return append_event(root, binding, "findings-added", {
        "findings": admitted,
        "terminal_observations": observations,
    })


def record_progress(root: Path, binding: JsonObject) -> RuntimeResult[JsonObject]:
    """Record lexicographic convergence after one targeted stage."""

    events = load_events(root, binding)
    if not events.ok:
        return RuntimeResult(None, events.error)
    values = events.required()
    positions = [
        index
        for index, event in enumerate(values)
        if event.get("event_type") == "targeted-review-started"
    ]
    if not positions:
        return RuntimeResult(None, failure("targeted_review_required", "progress needs a targeted review event range").error)
    latest = positions[-1]
    fields = _progress_fields(values, latest)
    if fields is None:
        return RuntimeResult(None, failure("targeted_results_required", "progress needs every targeted finding result").error)
    return append_event(root, binding, "progress-assessed", fields)


def _progress_fields(events: list[JsonObject], latest: int) -> JsonObject | None:
    finding_ids = set(string_values(events[latest].get("finding_ids")) or [])
    result_ids = {
        str(event.get("finding_id"))
        for event in events[latest + 1 :]
        if event.get("event_type") in {"targeted-review-result", "human-finding-decided"}
    }
    if finding_ids - result_ids:
        return None
    before = current_findings(events[:latest])
    after = current_findings(events)
    progressed = review_model.made_progress(before, after)
    stalled = 0
    for event in reversed(events):
        if event.get("event_type") == "progress-assessed":
            if event.get("progressed") is True:
                break
            stalled += 1
    actions = ("diagnose", "change_method", "human_judgment")
    next_action = "continue" if progressed else actions[min(stalled, len(actions) - 1)]
    before_counts = review_model.open_counts(before)
    after_counts = review_model.open_counts(after)
    return {
        "before": before_counts,
        "after": after_counts,
        "progressed": progressed,
        "next_action": next_action,
    }


def mark_stale(
    root: Path,
    binding: JsonObject,
    *,
    reason: str,
) -> RuntimeResult[JsonObject]:
    """Mark findings stale after a consequential specification change."""

    if not reason.strip():
        return RuntimeResult(None, failure("stale_reason_required", "findings_stale needs a consequential change reason").error)
    return append_event(root, binding, "findings_stale", {"reason": reason})


def rebound_findings(
    root: Path,
    binding: JsonObject,
    *,
    spec_commit: str,
    reason: str,
) -> RuntimeResult[JsonObject]:
    """Rebind stale findings to a human-approved specification commit."""

    events = load_events(root, binding)
    if not events.ok or not events.value or events.value[-1].get("event_type") != "findings_stale":
        return RuntimeResult(None, failure("findings_not_stale", "only stale findings can rebound").error)
    resolved = commit(root, spec_commit)
    if not resolved.ok or not reason.strip():
        return RuntimeResult(None, failure("rebound_invalid", "rebound needs an existing specification commit and reason").error)
    return append_event(root, binding, "findings-rebound", {
        "spec_commit": resolved.required(),
        "reason": reason,
    })


def complete_review(root: Path, binding: JsonObject) -> RuntimeResult[JsonObject]:
    """Prove the review reached its existing terminal state."""

    events = load_events(root, binding)
    if not events.ok:
        return RuntimeResult(None, events.error)
    values = events.required()
    state = _review_state(values)
    failures = (
        (bool(state.get("stale")), "findings_stale", "stale findings cannot complete"),
        (not state.get("final_started"), "final_review_required", "final full review has not started"),
        (not state.get("final_done"), "final_results_required", "final full review results are missing"),
        (
            any(item.get("state") == "open" for item in object_values(state.get("findings")) or []),
            "findings_open",
            "all admitted findings must close",
        ),
    )
    rejected = next((item for item in failures if item[0]), None)
    if rejected is not None:
        return RuntimeResult(None, failure(rejected[1], rejected[2]).error)
    targeted = [
        index
        for index, event in enumerate(values)
        if event.get("event_type") == "targeted-review-started"
    ]
    assessed = not targeted or any(
        event.get("event_type") == "progress-assessed"
        for event in values[targeted[-1] + 1 :]
    )
    if not assessed:
        return RuntimeResult(None, failure("progress_assessment_required", "targeted convergence needs lexicographic progress evidence").error)
    return ok({"event_type": "review-complete", "verdict": "pass"})
