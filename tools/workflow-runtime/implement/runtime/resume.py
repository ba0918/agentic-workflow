"""Discover, summarize, resume, and logically retire implementation runs."""
from pathlib import Path

from runtime.context import append_event, load_events
from runtime.deps import git_status
from runtime.events import derive_implementation
from runtime.gitio import run_git
from runtime.repository import load_run
from runtime.storage import read_json
from runtime.types import (
    JsonObject, Run, RuntimeResult, failure, forward_failure, object_values, ok,
    string_values,
)


def _worktree_registration(root: Path, branch: str, worktree: str) -> bool:
    listed = run_git(root, "worktree", "list", "--porcelain")
    if listed.returncode != 0:
        return False
    expected_branch = f"branch refs/heads/{branch}"
    return any(
        f"worktree {worktree}" in block.splitlines()
        and expected_branch in block.splitlines()
        for block in listed.stdout.strip().split("\n\n")
    )


def _uncommitted_paths(worktree: Path) -> list[str]:
    status = run_git(
        worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    if status.returncode != 0:
        return []
    try:
        return git_status.parse_porcelain_v1_z(
            status.stdout, excluded_prefixes=(".agents/",)
        )
    except ValueError:
        return []


def _explained_commits(event_values: list[JsonObject]) -> set[object]:
    explained = {
        event.get("commit") for event in event_values if event.get("event_type") == "commit"
    }
    explained.update(
        event.get("approval_commit") or event.get("current_commit")
        for event in event_values
        if event.get("event_type") in {"rebound", "recovering"}
    )
    return explained


def _unexplained_commits(
    root: Path,
    approval_commit: str,
    tip: str,
    event_values: list[JsonObject],
) -> RuntimeResult[list[JsonObject]]:
    history = run_git(root, "rev-list", "--reverse", f"{approval_commit}..{tip}")
    if history.returncode != 0:
        return failure(
            "resume_git_state_invalid", "implementation branch history is unavailable"
        )
    explained = _explained_commits(event_values)
    commits: list[JsonObject] = []
    for commit in filter(None, history.stdout.splitlines()):
        if commit in explained:
            continue
        subject = run_git(root, "show", "-s", "--format=%s", commit).stdout.strip()
        commits.append({"sha": commit, "subject": subject})
    return ok(commits)


def _git_facts(
    root: Path, binding: JsonObject, event_values: list[JsonObject],
) -> RuntimeResult[JsonObject]:
    branch = binding.get("branch")
    worktree_value = binding.get("worktree")
    if not isinstance(branch, str) or not isinstance(worktree_value, str):
        return ok({
            "branch": {
                "name": branch, "exists": False, "tip": None, "unexplained_commits": [],
            },
            "worktree": {
                "path": worktree_value, "registered": False, "uncommitted_paths": [],
            },
        })
    tip_result = run_git(root, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    tip = tip_result.stdout.strip()
    exists = tip_result.returncode == 0
    unexplained: list[JsonObject] = []
    if exists:
        approval_commit = binding.get("approval_commit")
        if not isinstance(approval_commit, str):
            return failure(
                "resume_git_state_invalid", "implementation approval commit is unavailable"
            )
        commits = _unexplained_commits(root, approval_commit, tip, event_values)
        if not commits.ok:
            return forward_failure(
                commits.error, "resume_git_state_invalid", "branch history is unavailable"
            )
        unexplained = commits.required()
    worktree = Path(worktree_value)
    registered = worktree.is_dir() and _worktree_registration(
        root, branch, str(worktree.resolve())
    )
    return ok({
        "branch": {
            "name": branch,
            "exists": exists,
            "tip": tip if exists else None,
            "unexplained_commits": unexplained,
        },
        "worktree": {
            "path": str(worktree.resolve()),
            "registered": registered,
            "uncommitted_paths": _uncommitted_paths(worktree) if registered else [],
        },
    })


def summary(run: Run) -> RuntimeResult[JsonObject]:
    binding = read_json(run.binding_path)
    event_values = load_events(run)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not event_values.ok:
        return forward_failure(event_values.error, "evidence_unavailable", "events are unavailable")
    derived = derive_implementation(binding.required(), event_values.required())
    if not derived.ok:
        return forward_failure(
            derived.error, "implementation_evidence_invalid", "implementation evidence is invalid"
        )
    facts = _git_facts(run.root, binding.required(), event_values.required())
    if not facts.ok:
        return forward_failure(facts.error, "resume_git_state_invalid", "Git state is invalid")
    last = event_values.required()[-1] if event_values.required() else {}
    steps = object_values(derived.required().get("steps")) or []
    completed = string_values(derived.required().get("completed_steps")) or []
    remaining = [
        identifier for step in steps
        if isinstance((identifier := step.get("id")), str) and identifier not in completed
    ]
    return ok({
        "plan": {"key": run.plan_key, "path": binding.required().get("plan_path")},
        "run_id": run.run_id,
        "started_at": binding.required().get("started_at"),
        "started_at_status": (
            "recorded" if binding.required().get("started_at") else "unavailable"
        ),
        "last_event": {
            "event_type": last.get("event_type"),
            "reason": last.get("reason") or last.get("summary"),
        },
        "completed_steps": completed,
        "remaining_steps": remaining,
        **facts.required(),
    })


def discover_unfinished(root: Path, plan_key: str) -> RuntimeResult[list[JsonObject]]:
    store = root.resolve() / ".agents/evidence" / plan_key
    if not store.is_dir():
        return ok([])
    summaries: list[JsonObject] = []
    for directory in sorted(store.iterdir()):
        candidate = _unfinished_summary(root, plan_key, directory.name)
        if not candidate.ok:
            return forward_failure(
                candidate.error, "implementation_evidence_invalid", "run cannot be summarized"
            )
        if candidate.value is not None:
            summaries.append(candidate.value)
    return ok(summaries)


def _unfinished_summary(
    root: Path, plan_key: str, run_id: str,
) -> RuntimeResult[JsonObject | None]:
    loaded = load_run(root, plan_key, run_id)
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "run is unavailable")
    run_summary = summary(loaded.required())
    binding = read_json(loaded.required().binding_path)
    event_values = load_events(loaded.required())
    if not run_summary.ok:
        return forward_failure(run_summary.error, "evidence_invalid", "run summary is invalid")
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not event_values.ok:
        return forward_failure(event_values.error, "evidence_unavailable", "events are unavailable")
    derived = derive_implementation(binding.required(), event_values.required())
    if not derived.ok:
        return forward_failure(
            derived.error, "implementation_evidence_invalid", "implementation evidence is invalid"
        )
    complete = any(
        event.get("event_type") == "implementation_green" for event in event_values.required()
    )
    return ok(
        None if complete or derived.required().get("resume_candidate_retired") else run_summary.required()
    )


def _summary_object(value: JsonObject, field_name: str) -> JsonObject | None:
    candidate = value.get(field_name)
    if not isinstance(candidate, dict) or not all(isinstance(key, str) for key in candidate):
        return None
    return {str(key): item for key, item in candidate.items()}


def resume_run(root: Path, *, plan_key: str, run_id: str) -> RuntimeResult[JsonObject]:
    loaded = load_run(root, plan_key, run_id)
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "run is unavailable")
    run_summary = summary(loaded.required())
    if not run_summary.ok:
        return forward_failure(run_summary.error, "evidence_invalid", "run summary is invalid")
    branch = _summary_object(run_summary.required(), "branch")
    worktree = _summary_object(run_summary.required(), "worktree")
    if branch is None or worktree is None or not branch.get("exists") or not worktree.get(
        "registered"
    ):
        return failure(
            "resume_git_state_invalid", "bound branch and worktree must exist before resuming"
        )
    return _record_resume(loaded.required(), branch, worktree)


def _record_resume(
    run: Run, branch: JsonObject, worktree: JsonObject,
) -> RuntimeResult[JsonObject]:
    binding = read_json(run.binding_path)
    event_values = load_events(run)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not event_values.ok:
        return forward_failure(event_values.error, "evidence_unavailable", "events are unavailable")
    derived = derive_implementation(binding.required(), event_values.required())
    if not derived.ok:
        return forward_failure(
            derived.error, "implementation_evidence_invalid", "implementation evidence is invalid"
        )
    unexplained = object_values(branch.get("unexplained_commits")) or []
    uncommitted = string_values(worktree.get("uncommitted_paths")) or []
    actor = "cycle" if binding.required().get("delegated") else "implement"
    resumed = append_event(run, "resumed", {
        "branch_head": branch.get("tip"),
        "unexplained_commits": [item.get("sha") for item in unexplained],
        "uncommitted_paths": uncommitted,
    }, actor=actor)
    if not resumed.ok:
        return forward_failure(resumed.error, "resume_invalid", "run could not be resumed")
    return ok({
        "run": run,
        "resume_step": derived.required().get("resume_step"),
        "event": resumed.required(),
    })


def retire_run(
    root: Path, *, plan_key: str, run_id: str, reason: str,
) -> RuntimeResult[JsonObject]:
    if not reason.strip():
        return failure(
            "retirement_reason_missing", "logical run retirement needs a reason"
        )
    loaded = load_run(root, plan_key, run_id)
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "run is unavailable")
    binding = read_json(loaded.required().binding_path)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    actor = "cycle" if binding.required().get("delegated") else "implement"
    return append_event(
        loaded.required(), "resume-candidate-retired", {"reason": reason}, actor=actor
    )
