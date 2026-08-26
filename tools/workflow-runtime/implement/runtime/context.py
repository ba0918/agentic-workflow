"""Evidence chain: context validation, event append, stop and permission records."""
import re
from pathlib import Path, PurePosixPath
from typing import Any

from runtime.deps import execution_model, plan_artifact
from runtime.types import RuntimeFailure, RuntimeResult, Attempt, ok, failure
from runtime.gitio import run_git
from runtime.storage import read_json, write_once
from runtime.planning import raw_identity
from runtime.repository import discover_repository


def changed_paths(worktree: Path) -> RuntimeResult:
    status = run_git(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return failure("git_status_failed", "Git status could not be observed", status.stderr.strip())
    paths: list[str] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            before, after = path.split(" -> ", 1)
            paths.extend((before, after))
        else:
            paths.append(path)
    return ok(tuple(paths))

def load_effective_binding(attempt: Attempt) -> RuntimeResult:
    """The binding as the last rebound left it; the chain must be valid to trust a rebound."""
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    # A binding that cannot be read fails the same comparison a drifted one does, so the
    # runtime needs no separate check that its own record is well formed.
    if (
        not isinstance(binding, dict)
        or binding.get("attempt_id") != attempt.attempt_id
        or binding.get("branch") != attempt.branch
    ):
        return failure("binding_identity_drift", "attempt and binding disagree")
    events = load_events(attempt)
    if not events.ok:
        return events
    return ok(execution_model.effective_binding(binding, events.value))

def validate_context(attempt: Attempt, *, step_id: str) -> RuntimeResult:
    effective = load_effective_binding(attempt)
    if not effective.ok:
        return effective
    binding = effective.value

    try:
        registered = plan_artifact.read_registered_plan(
            attempt.main_checkout,
            binding["plan"]["path"],
        )
    except plan_artifact.PlanArtifactError as error:
        return failure("plan_identity_drift", "registered plan is no longer valid", str(error))
    if (
        registered.plan_id != binding["plan"]["id"]
        or registered.revision != binding["plan"]["revision"]
        or registered.content_identity != binding["plan"]["content_identity"]
    ):
        return failure("plan_identity_drift", "registered plan differs from the binding")
    step_number = step_id.removeprefix("step-")
    if not step_number.isdigit() or re.search(
        rf"^### {re.escape(step_number)}\.", registered.text, re.MULTILINE
    ) is None:
        return failure("step_missing", "current step does not exist in the bound plan")

    repository = discover_repository(attempt.worktree)
    if not repository.ok:
        return failure("worktree_identity_drift", "bound worktree is not a valid linked worktree")
    if (
        repository.value.main_checkout != attempt.main_checkout.resolve()
        or repository.value.checkout != attempt.worktree.resolve()
        or repository.value.repository_identity != binding["repository_identity"]
    ):
        return failure("worktree_identity_drift", "worktree Git identity differs from the binding")
    branch = run_git(attempt.worktree, "branch", "--show-current")
    ancestor = run_git(
        attempt.worktree,
        "merge-base",
        "--is-ancestor",
        binding["base_head"],
        "HEAD",
    )
    if branch.returncode != 0 or branch.stdout.strip() != binding["branch"] or ancestor.returncode != 0:
        return failure("worktree_identity_drift", "worktree branch or base HEAD differs from the binding")

    for spec in binding["specs"]:
        path = attempt.worktree.joinpath(*PurePosixPath(spec["path"]).parts)
        if path.is_symlink() or not path.is_file():
            return failure("spec_identity_drift", f"bound spec is unavailable: {spec['path']}")
        if raw_identity(path.read_text(encoding="utf-8")) != spec["content_identity"]:
            return failure("spec_identity_drift", f"bound spec changed: {spec['path']}")

    changed = changed_paths(attempt.worktree)
    if not changed.ok:
        return changed
    # Changes outside the write scope are a fact for the human, never a stop: the staging
    # boundary keeps them out of commits and the terminal check lists them for approval.
    out_of_scope = [
        path
        for path in changed.value
        if not execution_model.validate_write_path(path, binding["write_scope"]).ok
    ]
    return ok(dict(binding, out_of_scope_changes=sorted(out_of_scope)))

def load_events(attempt: Attempt) -> RuntimeResult:
    events: list[dict] = []
    for path in sorted(attempt.evidence_path.glob("0*.json")):
        loaded = read_json(path)
        if not loaded.ok:
            return loaded
        events.append(loaded.value)
    return ok(events)

def append_event(attempt: Attempt, event_type: str, details: dict[str, Any]) -> RuntimeResult:
    loaded = load_events(attempt)
    if not loaded.ok:
        return loaded
    events = loaded.value
    next_sequence = len(events) + 1
    candidate = {
        "version": 1,
        "sequence": next_sequence,
        "event_type": event_type,
        "attempt_id": attempt.attempt_id,
        **details,
    }
    sealed = execution_model.seal_event(candidate, previous_event=events[-1] if events else None)
    if not sealed.ok:
        return failure(sealed.error.code, sealed.error.message)
    persisted = write_once(
        attempt.evidence_path / f"{next_sequence:06d}-{event_type}.json",
        execution_model.canonical_json(sealed.value),
    )
    if not persisted.ok:
        return persisted
    return ok(sealed.value)

def derive_attempt_result(attempt: Attempt) -> dict:
    loaded = load_events(attempt)
    if not loaded.ok:
        return {
            "state": "stopped",
            "reason": loaded.error.code,
            "attempt_id": attempt.attempt_id,
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "evidence_path": str(attempt.evidence_path),
        }
    result = execution_model.derive_result(loaded.value)
    result.update(
        {
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "evidence_path": str(attempt.evidence_path),
        }
    )
    commits = [event["commit_sha"] for event in loaded.value if event["event_type"] == "commit"]
    if commits and "commits" not in result:
        result["commits"] = commits
    return result

def stop_attempt(attempt: Attempt, error: RuntimeFailure, step_id: str) -> RuntimeResult:
    append_event(
        attempt,
        "stopped",
        {"reason": error.code, "step_id": step_id},
    )
    return RuntimeResult(None, error)

def permission_required(
    attempt: Attempt,
    error: RuntimeFailure,
    step_id: str,
    operation_identity: str,
) -> RuntimeResult:
    append_event(
        attempt,
        "permission_required",
        {
            "step_id": step_id,
            "operation_identity": operation_identity,
            "outcome": "permission_required",
        },
    )
    return RuntimeResult(None, error)


def raw_events(evidence_path: Path) -> list[dict]:
    events: list[dict] = []
    for path in sorted(evidence_path.glob("0*.json")):
        loaded = read_json(path)
        if loaded.ok and isinstance(loaded.value, dict):
            events.append(loaded.value)
    return events
