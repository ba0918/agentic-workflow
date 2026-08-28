"""Derive implementation completion and commit-history validity."""
from pathlib import Path
from typing import Never

from runtime.deps import git_status, implementation_evidence
from runtime.gitio import run_git
from runtime.safety import content_safety
from runtime.staging import assess_paths
from runtime.types import (
    JsonObject, RuntimeFailure, RuntimeResult, failure, object_value, object_values, ok,
    string_values,
)


def validate_commit_ancestry(
    checkout: Path, binding: JsonObject, commit: str,
) -> RuntimeResult[None]:
    approval_commit = binding.get("approval_commit")
    branch = binding.get("branch")
    if not isinstance(approval_commit, str) or not isinstance(branch, str):
        return failure(
            "worktree_binding_invalid", "implementation worktree binding is invalid"
        )
    if commit == approval_commit or run_git(
        checkout, "merge-base", "--is-ancestor", approval_commit, commit
    ).returncode != 0:
        return failure(
            "commit_before_approval", "implementation commit must follow the approval commit"
        )
    branch_head = run_git(
        checkout, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}"
    )
    if branch_head.returncode != 0 or run_git(
        checkout, "merge-base", "--is-ancestor", commit, branch_head.stdout.strip()
    ).returncode != 0:
        return failure(
            "commit_not_on_branch",
            "implementation commit must be an ancestor of the bound branch tip",
        )
    return ok(None)


def _segment_commits(
    checkout: Path, segments_value: object,
) -> RuntimeResult[list[str]]:
    segments = object_values(segments_value)
    if not segments:
        return failure(
            "commit_bijection_invalid", "implementation revision segments are invalid"
        )
    first_approval = segments[0].get("approval_commit")
    if not isinstance(first_approval, str):
        return failure(
            "commit_bijection_invalid", "implementation revision segments are invalid"
        )
    history_result = run_git(
        checkout, "rev-list", "--reverse", f"{first_approval}..HEAD"
    )
    if history_result.returncode != 0:
        return failure(
            "git_inspection_failed", "implementation revision range could not be inspected"
        )
    boundaries = {
        approval for segment in segments
        if isinstance((approval := segment.get("approval_commit")), str)
    }
    history = [
        commit for commit in filter(None, history_result.stdout.splitlines())
        if commit not in boundaries - {first_approval}
    ]
    commits: list[str] = []
    for segment in segments:
        values = string_values(segment.get("commits"))
        if values is None:
            return failure(
                "commit_bijection_invalid", "implementation revision segments are invalid"
            )
        commits.extend(values)
    if history != commits:
        return failure(
            "commit_bijection_invalid",
            "implementation revision range and commit evidence differ",
        )
    return ok(history)


def _dirty_paths(checkout: Path) -> RuntimeResult[list[str]]:
    status = run_git(
        checkout, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    if status.returncode != 0:
        return failure(
            "git_inspection_failed", "worktree status could not be inspected"
        )
    try:
        return ok(
            git_status.parse_porcelain_v1_z(
                status.stdout, excluded_prefixes=(".agents/",)
            )
        )
    except ValueError:
        return failure(
            "git_inspection_failed", "worktree status could not be parsed"
        )


def _worktree_error(
    checkout: Path, binding: JsonObject, events: list[JsonObject], dirty_paths: list[str],
) -> RuntimeResult[list[str]]:
    expected = string_values(binding.get("expected_paths")) or []
    planned_dirty = sorted(set(dirty_paths) & set(expected))
    if planned_dirty:
        return failure(
            "planned_changes_uncommitted",
            "planned paths still have uncommitted changes",
            planned_dirty[0],
        )
    outside_dirty = sorted(set(dirty_paths) - set(expected))
    outside_error = _outside_error(checkout, outside_dirty)
    if outside_error is not None:
        return failure(outside_error.code, outside_error.message, outside_error.detail)
    branch = binding.get("branch")
    current_branch = run_git(checkout, "branch", "--show-current")
    if current_branch.returncode != 0 or current_branch.stdout.strip() != branch:
        return failure(
            "worktree_binding_invalid", "worktree branch differs from the run binding"
        )
    commit_error = _recorded_commit_error(checkout, events)
    if commit_error is not None:
        return failure(commit_error.code, commit_error.message, commit_error.detail)
    return ok(outside_dirty)


def _outside_error(checkout: Path, outside_dirty: list[str]) -> RuntimeFailure | None:
    outside_safety = assess_paths(outside_dirty, expected_paths=outside_dirty)
    if not outside_safety.ok:
        error = outside_safety.error
        if error is None:
            return RuntimeFailure("dangerous_path", "outside-scope paths are unsafe")
        return error
    outside_content = content_safety(checkout, outside_dirty, working_tree=True)
    if not outside_content.ok:
        error = outside_content.error
        if error is None:
            return RuntimeFailure("secret_content", "outside-scope content is unsafe")
        return error
    return None


def _recorded_commit_error(
    checkout: Path, events: list[JsonObject],
) -> RuntimeFailure | None:
    for event in events:
        commit = event.get("commit")
        if event.get("event_type") == "commit" and (
            not isinstance(commit, str)
            or run_git(checkout, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0
        ):
            return RuntimeFailure(
                "commit_invalid", f"recorded commit does not exist: {commit}"
            )
    return None


def _derived_completion(
    binding: JsonObject, events: list[JsonObject],
) -> RuntimeResult[JsonObject]:
    if not events or events[0].get("event_type") != "worktree-bound":
        return failure(
            "completion_invalid", "worktree binding evidence is missing"
        )
    derived = implementation_evidence.derive_implementation(binding, events)
    if not derived.ok or derived.value is None:
        error = derived.error
        code = error.code if error is not None else "completion_invalid"
        message = error.message if error is not None else "implementation evidence is invalid"
        return failure(code, message)
    value = derived.value
    steps = object_values(value.get("steps"))
    if not steps:
        return failure("completion_invalid", "implementation has no step contracts")
    resume_step = value.get("resume_step")
    if resume_step is not None:
        return failure("completion_invalid", f"step is incomplete: {resume_step}")
    if events[-1].get("event_type") == "stopped":
        return failure(
            "completion_invalid", "stopped run must be resumed or rebound"
        )
    return ok(value)


def _checkout_completion(
    binding: JsonObject, events: list[JsonObject],
) -> RuntimeResult[tuple[Path, list[str]]]:
    checkout_value = binding.get("worktree")
    checkout = Path(checkout_value) if isinstance(checkout_value, str) else Path()
    if not checkout.is_dir():
        return failure(
            "worktree_binding_invalid", "implementation worktree is unavailable"
        )
    dirty = _dirty_paths(checkout)
    if not dirty.ok:
        dirty_error = dirty.error
        if dirty_error is None:
            return failure("git_inspection_failed", "worktree status could not be inspected")
        return failure(dirty_error.code, dirty_error.message, dirty_error.detail)
    outside = _worktree_error(checkout, binding, events, dirty.required())
    if not outside.ok:
        outside_error = outside.error
        if outside_error is None:
            return failure("completion_invalid", "worktree cannot complete")
        return failure(outside_error.code, outside_error.message, outside_error.detail)
    return ok((checkout, outside.required()))


def _history_completion(
    checkout: Path, events: list[JsonObject], value: JsonObject,
) -> RuntimeResult[None]:
    history = _segment_commits(checkout, value.get("segments"))
    if not history.ok:
        history_error = history.error
        if history_error is None:
            return failure("commit_bijection_invalid", "implementation history is invalid")
        return failure(history_error.code, history_error.message, history_error.detail)
    recorded = [
        commit for event in events
        if event.get("event_type") == "commit"
        and isinstance((commit := event.get("commit")), str)
    ]
    if len(recorded) != len(set(recorded)):
        return failure(
            "commit_assignment_invalid", "one implementation commit is assigned more than once"
        )
    if set(history.required()) != set(recorded):
        return failure(
            "commit_bijection_invalid", "implementation history and commit evidence differ"
        )
    return ok(None)


def _final_verification_completion(
    events: list[JsonObject], value: JsonObject,
) -> RuntimeResult[None]:
    steps = object_values(value.get("steps")) or []
    final_step = steps[-1] if steps else None
    if final_step is None or final_step.get("completion") != "check":
        return ok(None)
    final_step_id = final_step.get("id")
    final_check_index = next(
        (
            index for index in range(len(events) - 1, -1, -1)
            if (event := events[index]).get("event_type") == "check"
            and event.get("step") == final_step_id
        ),
        None,
    )
    if final_check_index is None:
        return failure(
            "final_verification_stale", "final implementation check is missing"
        )
    final_check = events[final_check_index]
    later_events = events[final_check_index + 1:]
    commits = [
        event for event in later_events
        if event.get("event_type") == "commit"
    ]
    revision_changed = any(
        event.get("event_type") in {"recovering", "rebound"}
        for event in later_events
    )
    commit_safety = object_value(commits[0].get("safety")) if len(commits) == 1 else None
    commit_paths = (
        string_values(commit_safety.get("paths"))
        if commit_safety is not None else None
    )
    matching_step_commit = (
        len(commits) == 1
        and commits[0].get("step") == final_step_id
        and string_values(final_check.get("changed_paths")) == commit_paths
    )
    if revision_changed or commits and not matching_step_commit:
        return failure(
            "final_verification_stale",
            "final check must be the last broad verification of implementation changes",
        )
    return ok(None)


def completion_fields(
    binding: JsonObject, events: list[JsonObject],
) -> RuntimeResult[JsonObject]:
    derived = _derived_completion(binding, events)
    if not derived.ok:
        return _forward_failure(
            derived.error, "completion_invalid", "implementation evidence is invalid"
        )
    checkout = _checkout_completion(binding, events)
    if not checkout.ok:
        return _forward_failure(
            checkout.error, "completion_invalid", "worktree cannot complete"
        )
    checkout_path, outside_dirty = checkout.required()
    history = _history_completion(checkout_path, events, derived.required())
    if not history.ok:
        return _forward_failure(
            history.error, "commit_bijection_invalid", "implementation history is invalid"
        )
    verification = _final_verification_completion(events, derived.required())
    if not verification.ok:
        return _forward_failure(
            verification.error,
            "final_verification_stale",
            "final implementation verification is stale",
        )
    completed_steps = string_values(derived.required().get("completed_steps")) or []
    return ok({
        "completed_steps": completed_steps,
        "uncommitted_outside_scope": outside_dirty,
    })


def _forward_failure(
    error: RuntimeFailure | None, fallback_code: str, fallback_message: str,
) -> RuntimeResult[Never]:
    if error is None:
        return failure(fallback_code, fallback_message)
    return failure(error.code, error.message, error.detail)
