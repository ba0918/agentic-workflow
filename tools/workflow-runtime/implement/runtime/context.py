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

def validate_context(attempt: Attempt, *, step_id: str) -> RuntimeResult:
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    validation = execution_model.validate_binding(binding)
    if not validation.ok:
        return failure(validation.error.code, validation.error.message)
    if binding["attempt_id"] != attempt.attempt_id or binding["branch"] != attempt.branch:
        return failure("binding_identity_drift", "attempt and binding disagree")

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
    for path in changed.value:
        scope = execution_model.validate_write_path(path, binding["write_scope"])
        if not scope.ok:
            return failure(scope.error.code, scope.error.message, path)
    return ok(binding)

def load_events(attempt: Attempt) -> RuntimeResult:
    events: list[dict] = []
    for path in sorted(attempt.evidence_path.glob("0*.json")):
        loaded = read_json(path)
        if not loaded.ok:
            return loaded
        event = loaded.value
        previous = events[-1] if events else None
        unsigned = {key: value for key, value in event.items() if key != "content_identity"}
        sealed = execution_model.seal_event(unsigned, previous_event=previous)
        if not sealed.ok or sealed.value != event:
            return failure("stale_event_chain", "durable event chain is invalid", path.name)
        events.append(event)
    return ok(events)

def append_event(
    attempt: Attempt,
    event_type: str,
    details: dict[str, Any],
    *,
    sequence: int | None = None,
) -> RuntimeResult:
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    loaded = load_events(attempt)
    if not loaded.ok:
        return loaded
    events = loaded.value
    next_sequence = sequence if sequence is not None else len(events) + 1
    previous = next((event for event in events if event["sequence"] == next_sequence - 1), None)
    if next_sequence == 1:
        previous = None
    candidate = {
        "version": 1,
        "sequence": next_sequence,
        "event_type": event_type,
        "attempt_id": attempt.attempt_id,
        "plan_identity": binding["plan"]["content_identity"],
        "spec_identities": {
            item["path"]: item["content_identity"] for item in binding["specs"]
        },
        "previous_identity": previous["content_identity"] if previous is not None else None,
        **details,
    }
    sealed = execution_model.seal_event(candidate, previous_event=previous)
    if not sealed.ok:
        return failure(sealed.error.code, sealed.error.message)
    existing_paths = list(attempt.evidence_path.glob(f"{next_sequence:06d}-*.json"))
    if existing_paths:
        if len(existing_paths) != 1:
            return failure("event_identity_collision", "multiple events occupy the same sequence")
        existing = read_json(existing_paths[0])
        if not existing.ok:
            return existing
        compared = execution_model.compare_event_retry(existing.value, sealed.value)
        if not compared.ok:
            return failure(compared.error.code, compared.error.message)
        return ok(existing.value)
    target = attempt.evidence_path / f"{next_sequence:06d}-{event_type}.json"
    persisted = write_once(target, execution_model.canonical_json(sealed.value))
    if not persisted.ok:
        if persisted.error.code == "write_collision":
            return failure("event_identity_collision", "event sequence was acquired concurrently")
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
