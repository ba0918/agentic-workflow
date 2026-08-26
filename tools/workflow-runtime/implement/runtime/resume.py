"""Unfinished executions: facts for the human, resume, and session reload."""
from runtime.context import changed_paths, raw_events
import re
from pathlib import Path, PurePosixPath
from typing import Any

from runtime.deps import execution_model, plan_artifact
from runtime.types import RuntimeResult, Attempt, ok, failure
from runtime.gitio import run_git
from runtime.storage import read_json, safe_agent_roots
from runtime.planning import parse_plan, raw_identity
from runtime.repository import discover_repository
from runtime.context import append_event, load_effective_binding, load_events


def _execution_directories(main_checkout: Path, plan_id: str) -> list[Path]:
    store = main_checkout / ".agents/artifacts/executions" / plan_id
    if not store.is_dir():
        return []
    return sorted(
        path for path in store.iterdir()
        if path.is_dir() and not path.is_symlink() and (path / "binding.json").is_file()
    )

def _last_event_type(evidence_path: Path) -> str | None:
    files = sorted(evidence_path.glob("0*.json"))
    if not files:
        return None
    loaded = read_json(files[-1])
    if not loaded.ok or not isinstance(loaded.value, dict):
        return None
    return loaded.value.get("event_type")

def _unfinished_executions(main_checkout: Path, plan_id: str) -> list[str]:
    return [
        path.name
        for path in _execution_directories(main_checkout, plan_id)
        if _last_event_type(path) != "implementation_green"
    ]

def _select_execution(main_checkout: Path) -> RuntimeResult:
    """Without explicit ids, only the single unfinished execution of the current plan is implied."""
    try:
        registered = plan_artifact.read_registered_plan(main_checkout, None)
    except plan_artifact.PlanArtifactError as error:
        return failure("plan_registration_missing", "no current plan identifies an execution", str(error))
    candidates = _unfinished_executions(main_checkout, registered.plan_id)
    if not candidates:
        candidates = [path.name for path in _execution_directories(main_checkout, registered.plan_id)]
    if not candidates:
        return failure("execution_missing", "the current plan has no execution")
    if len(candidates) > 1:
        return failure(
            "execution_ambiguous",
            "several unfinished executions exist; name one with --plan-id and --execution-id",
            ", ".join(candidates),
        )
    return ok((registered.plan_id, candidates[0]))

def _started_at(execution_id: str) -> str | None:
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})t(\d{2})(\d{2})(\d{2})-.*", execution_id)
    if match is None:
        return None
    year, month, day, hour, minute, second = match.groups()
    return f"{year}-{month}-{day}T{hour}:{minute}:{second}"


def _binding_fingerprints_match(main_checkout: Path, binding: dict) -> str | None:
    """Return None when the bound plan and specs still match the repository, else the reason."""
    try:
        registered = plan_artifact.read_registered_plan(main_checkout, binding["plan"]["path"])
    except plan_artifact.PlanArtifactError as error:
        return f"bound plan cannot be verified: {error}"
    if registered.content_identity != binding["plan"]["content_identity"]:
        return "bound plan differs from the registered plan"
    for spec in binding["specs"]:
        spec_path = main_checkout.joinpath(*PurePosixPath(spec["path"]).parts)
        if not spec_path.is_file() or raw_identity(spec_path.read_text(encoding="utf-8")) != spec["content_identity"]:
            return f"bound spec differs from the repository: {spec['path']}"
    return None

def _rebind_target(main_checkout: Path, binding: dict) -> dict[str, Any]:
    """Whether a drifted execution can be rebound: the current plan must be a revision of its plan."""
    try:
        current = plan_artifact.read_registered_plan(main_checkout, None)
    except plan_artifact.PlanArtifactError as error:
        return {"ok": False, "reason": f"no current plan to rebind to: {error}"}
    if current.plan_id != binding["plan"]["id"]:
        return {"ok": False, "reason": "the current plan is a different plan"}
    previous = main_checkout.joinpath(*PurePosixPath(binding["plan"]["path"]).parts)
    if previous.is_symlink() or not previous.is_file():
        return {"ok": False, "reason": f"the bound plan revision is no longer readable: {binding['plan']['path']}"}
    return {"ok": True, "reason": None}


def _branch_facts(main_checkout: Path, branch: str, base_head: str, recorded: set[str]) -> dict[str, Any]:
    """Extra commits are the history commits no commit event explains, wherever they sit."""
    exists = run_git(main_checkout, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    extra: list[dict[str, str]] = []
    if exists:
        log = run_git(main_checkout, "log", "--reverse", "--format=%H%x09%s", f"{base_head}..refs/heads/{branch}")
        if log.returncode == 0:
            for line in log.stdout.splitlines():
                sha, _, subject = line.partition("\t")
                if sha not in recorded:
                    extra.append({"sha": sha, "subject": subject})
    return {"name": branch, "exists": exists, "extra_commits": extra}


def _recorded_commits(events: list[dict]) -> set[str]:
    return {event.get("commit_sha") for event in events if event.get("event_type") == "commit"}

def _worktree_facts(main_checkout: Path, common_directory: Path, worktree: Path) -> dict[str, Any]:
    facts: dict[str, Any] = {"path": str(worktree), "exists": worktree.is_dir(), "registered": False, "changed_files": []}
    if not facts["exists"]:
        return facts
    observed = discover_repository(worktree)
    facts["registered"] = observed.ok and observed.value.common_directory == common_directory
    if facts["registered"]:
        changed = changed_paths(worktree)
        if changed.ok:
            facts["changed_files"] = sorted(changed.value)
    return facts

def residual_executions(project_root: Path, *, plan_id: str) -> RuntimeResult:
    """Describe unfinished executions of one plan without writing anything; the human decides."""
    repository = discover_repository(project_root)
    if not repository.ok:
        return repository
    main_checkout = repository.value.main_checkout
    if not plan_artifact.PLAN_ID.fullmatch(plan_id):
        return failure("execution_ids_invalid", "plan id is not path-safe")
    facts: list[dict[str, Any]] = []
    for evidence_path in _execution_directories(main_checkout, plan_id):
        events = raw_events(evidence_path)
        last = events[-1] if events else None
        if last is not None and last.get("event_type") == "implementation_green":
            continue
        binding_result = read_json(evidence_path / "binding.json")
        unreadable = {
            "execution_id": evidence_path.name,
            "started_at": _started_at(evidence_path.name),
            "resumable": {"ok": False, "reason": "binding.json is missing or unreadable"},
        }
        if not binding_result.ok:
            facts.append(unreadable)
            continue
        # This path shows a human what is lying around, so a binding nobody can read is one more
        # fact to show, not a reason to fail the listing. Its fields are read, never validated.
        try:
            binding = execution_model.effective_binding(binding_result.value, events)
            commits = [event for event in execution_model.effective_events(events) if event.get("event_type") == "commit"]
            mismatch = _binding_fingerprints_match(main_checkout, binding)
            facts.append(
                {
                    "execution_id": evidence_path.name,
                    "started_at": _started_at(evidence_path.name),
                    "completed_steps": len({event.get("step_id") for event in commits}),
                    "last_event": {
                        "event_type": last.get("event_type") if last else None,
                        "reason": last.get("reason") if last else None,
                    },
                    "branch": _branch_facts(main_checkout, binding["branch"], binding["base_head"], _recorded_commits(events)),
                    "worktree": _worktree_facts(main_checkout, repository.value.common_directory, Path(binding["worktree"])),
                    "resumable": {"ok": mismatch is None, "reason": mismatch},
                    "rebindable": _rebind_target(main_checkout, binding),
                }
            )
        except (AttributeError, KeyError, TypeError):
            facts.append(unreadable)
    return ok(facts)

def _next_step_after_evidence(events: list[dict], step_ids: list[str]) -> tuple[str | None, bool, list[str]]:
    """Derive the step to continue from: after the last committed step, redoing an unfinished RED."""
    committed = [event["step_id"] for event in events if event.get("event_type") == "commit"]
    completed = [step for step in step_ids if step in committed]
    remaining = [step for step in step_ids if step not in committed]
    if not remaining:
        return None, False, completed
    next_step = remaining[0]
    redo = any(
        event.get("event_type") in {"red", "green", "refactor"} and event.get("step_id") == next_step
        for event in events
    )
    return next_step, redo, completed

def resume_execution(project_root: Path, *, plan_id: str, attempt_id: str) -> RuntimeResult:
    """Continue an unfinished execution: record what is inherited, then name the next step."""
    loaded = load_current_attempt(project_root, plan_id=plan_id, attempt_id=attempt_id)
    if not loaded.ok:
        return loaded
    attempt = loaded.value
    events_result = load_events(attempt)
    if not events_result.ok:
        return events_result
    events = events_result.value
    if events and events[-1]["event_type"] == "implementation_green":
        return failure("execution_finished", "this execution already reached implementation_green")
    binding = execution_model.effective_binding(read_json(attempt.binding_path).value, events)
    mismatch = _binding_fingerprints_match(attempt.main_checkout, binding)
    if mismatch is not None:
        code = "spec_identity_drift" if "spec" in mismatch else "plan_identity_drift"
        return failure(code, mismatch)
    events = execution_model.effective_events(events)
    try:
        registered = plan_artifact.read_registered_plan(attempt.main_checkout, binding["plan"]["path"])
        step_ids = [f"step-{step.number}" for step in plan_artifact.read_plan_steps(registered.text)]
    except plan_artifact.PlanArtifactError as error:
        return failure("plan_format_invalid", str(error))
    branch = _branch_facts(attempt.main_checkout, attempt.branch, binding["base_head"], _recorded_commits(events))
    head = run_git(attempt.main_checkout, "rev-parse", f"refs/heads/{attempt.branch}").stdout.strip()
    changed = changed_paths(attempt.worktree)
    if not changed.ok:
        return changed
    next_step, redo, completed = _next_step_after_evidence(events, step_ids)
    recorded = append_event(
        attempt,
        "resumed",
        {
            "head": head,
            "extra_commits": [commit["sha"] for commit in branch["extra_commits"]],
            "uncommitted_changes": bool(changed.value),
            "next_step": next_step,
            "redo": redo,
        },
    )
    if not recorded.ok:
        return recorded
    return ok(
        {
            "execution_id": attempt.attempt_id,
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "next_step": next_step,
            "redo": redo,
            "completed_steps": completed,
            "all_steps_committed": next_step is None,
        }
    )

def _step_text_identity(step: Any) -> str:
    """Identity of a step's wording — heading and body, never its number."""
    lines = [line.rstrip() for line in f"{step.title}\n{step.text}".strip().splitlines()]
    return raw_identity("\n".join(lines))


def _plan_step_map(previous_steps: tuple, revised_steps: tuple, completed: set[str]) -> tuple[list[dict], list[str]]:
    """Match revised steps to previous ones by wording; unmatched previous steps are superseded."""
    unmatched = {f"step-{step.number}": _step_text_identity(step) for step in previous_steps}
    step_map: list[dict[str, Any]] = []
    for step in revised_steps:
        identity = _step_text_identity(step)
        previous_id = next((step_id for step_id, other in unmatched.items() if other == identity), None)
        if previous_id is None:
            step_map.append({"step_id": f"step-{step.number}", "previous_step_id": None, "disposition": "new"})
            continue
        del unmatched[previous_id]
        step_map.append(
            {
                "step_id": f"step-{step.number}",
                "previous_step_id": previous_id,
                "disposition": "carry" if previous_id in completed else "continue",
            }
        )
    return step_map, list(unmatched)


def _rebind_plan(project_root: Path, *, plan_id: str, attempt_id: str, plan_path: str | None) -> RuntimeResult:
    """Everything a rebound needs, computed without writing: the human reads it before recording."""
    loaded = load_current_attempt(project_root, plan_id=plan_id, attempt_id=attempt_id)
    if not loaded.ok:
        return loaded
    attempt = loaded.value
    events_result = load_events(attempt)
    if not events_result.ok:
        return events_result
    events = events_result.value
    if events and events[-1]["event_type"] == "implementation_green":
        return failure("execution_finished", "this execution already reached implementation_green")
    binding = execution_model.effective_binding(read_json(attempt.binding_path).value, events)
    try:
        target = plan_artifact.read_registered_plan(attempt.main_checkout, plan_path)
    except plan_artifact.PlanArtifactError as error:
        return failure("rebind_target_invalid", "the revised plan is not registered", str(error))
    if target.plan_id != attempt.plan_id:
        return failure("rebind_target_invalid", "the registered plan is a different plan", target.plan_id)
    previous_path = attempt.main_checkout.joinpath(*PurePosixPath(binding["plan"]["path"]).parts)
    if previous_path.is_symlink() or not previous_path.is_file():
        return failure("rebind_source_unavailable", "the bound plan revision is no longer readable", binding["plan"]["path"])
    previous_text = previous_path.read_text(encoding="utf-8")
    if raw_identity(previous_text) != binding["plan"]["content_identity"]:
        return failure("rebind_source_unavailable", "the bound plan revision no longer has its bound content", binding["plan"]["path"])
    previous_plan = parse_plan(previous_text)
    if not previous_plan.ok:
        return previous_plan
    revised_plan = parse_plan(target.text)
    if not revised_plan.ok:
        return revised_plan
    _, revision, specs, write_scope, revised_steps, human_gates = revised_plan.value
    for spec_path, identity in specs:
        spec_file = attempt.main_checkout.joinpath(*PurePosixPath(spec_path).parts)
        if not spec_file.is_file() or raw_identity(spec_file.read_text(encoding="utf-8")) != identity:
            return failure("spec_identity_drift", "revised plan cites a specification that differs from the repository", spec_path)
    effective = execution_model.effective_events(events)
    completed = {event["step_id"] for event in effective if event.get("event_type") == "commit"}
    step_map, superseded = _plan_step_map(previous_plan.value[4], revised_steps, completed)
    rebound = {
        "plan": {
            "id": target.plan_id,
            "path": target.path,
            "revision": revision,
            "content_identity": target.content_identity,
        },
        "specs": [{"path": spec_path, "content_identity": identity} for spec_path, identity in specs],
        "write_scope": list(write_scope),
        "human_gates": list(human_gates),
        "step_map": step_map,
        "superseded_steps": superseded,
    }
    projected = execution_model.effective_events(events + [dict(rebound, event_type="rebound")])
    step_ids = [f"step-{step.number}" for step in revised_steps]
    next_step, redo, carried = _next_step_after_evidence(projected, step_ids)
    return ok((attempt, events, binding, rebound, {"next_step": next_step, "redo": redo, "completed_steps": carried}))


def rebind_preview(project_root: Path, *, plan_id: str, attempt_id: str, plan_path: str | None = None) -> RuntimeResult:
    """Show how the revised plan maps onto the execution; writes nothing."""
    planned = _rebind_plan(project_root, plan_id=plan_id, attempt_id=attempt_id, plan_path=plan_path)
    if not planned.ok:
        return planned
    attempt, events, binding, rebound, continuation = planned.value
    branch = _branch_facts(attempt.main_checkout, attempt.branch, binding["base_head"], _recorded_commits(execution_model.effective_events(events)))
    return ok({**rebound, **continuation, "previous_plan": binding["plan"], "extra_commits": branch["extra_commits"]})


def rebind_execution(
    project_root: Path,
    *,
    plan_id: str,
    attempt_id: str,
    plan_path: str | None = None,
    expected_plan_identity: str | None = None,
) -> RuntimeResult:
    """Record the rebound the human confirmed and name the step to continue from.

    The human confirms a table, not a plan id. Between reading it and confirming, another
    revision may be published, so the identity they were shown must be named here: recording a
    rebound onto a revision nobody read would make the record and the decision two different
    things."""
    if expected_plan_identity is None:
        return failure("rebind_preview_missing", "name the plan identity the human was shown")
    planned = _rebind_plan(project_root, plan_id=plan_id, attempt_id=attempt_id, plan_path=plan_path)
    if not planned.ok:
        return planned
    attempt, events, binding, rebound, continuation = planned.value
    if rebound["plan"]["content_identity"] != expected_plan_identity:
        return failure(
            "rebind_target_moved",
            "the registered plan changed after the human read the mapping",
            rebound["plan"]["content_identity"],
        )
    branch = _branch_facts(attempt.main_checkout, attempt.branch, binding["base_head"], _recorded_commits(execution_model.effective_events(events)))
    head = run_git(attempt.main_checkout, "rev-parse", f"refs/heads/{attempt.branch}").stdout.strip()
    changed = changed_paths(attempt.worktree)
    if not changed.ok:
        return changed
    recorded = append_event(
        attempt,
        "rebound",
        {
            **rebound,
            "head": head,
            "extra_commits": [commit["sha"] for commit in branch["extra_commits"]],
            "uncommitted_changes": bool(changed.value),
        },
    )
    if not recorded.ok:
        return recorded
    return ok(
        {
            "execution_id": attempt.attempt_id,
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "plan": rebound["plan"],
            **continuation,
            "all_steps_committed": continuation["next_step"] is None,
        }
    )


def load_current_attempt(
    project_root: Path,
    *,
    plan_id: str | None = None,
    attempt_id: str | None = None,
) -> RuntimeResult:
    safe = safe_agent_roots(project_root)
    if not safe.ok:
        return safe
    repository = discover_repository(project_root)
    if not repository.ok:
        return repository
    main_checkout = repository.value.main_checkout
    if (plan_id is None) != (attempt_id is None):
        return failure("execution_ids_incomplete", "plan id and execution id must be given together")
    if plan_id is None:
        selected = _select_execution(main_checkout)
        if not selected.ok:
            return selected
        plan_id, attempt_id = selected.value
    if not execution_model.ATTEMPT_ID.fullmatch(attempt_id) or not plan_artifact.PLAN_ID.fullmatch(plan_id):
        return failure("execution_ids_invalid", "plan id or execution id is not path-safe")
    evidence_path = main_checkout / ".agents/artifacts/executions" / plan_id / attempt_id
    tmp_path = main_checkout / ".agents/tmp/executions" / attempt_id
    binding_path = evidence_path / "binding.json"
    if not binding_path.is_file():
        return failure("binding_missing", f"no binding.json exists for execution {attempt_id}", str(binding_path))
    binding_result = read_json(binding_path)
    if not binding_result.ok:
        return failure("binding_invalid", "binding.json cannot be read", binding_result.error.message)
    binding = binding_result.value
    if (
        not isinstance(binding, dict)
        or binding.get("attempt_id") != attempt_id
        or not isinstance(binding.get("plan"), dict)
        or binding["plan"].get("id") != plan_id
    ):
        return failure("binding_identity_drift", "binding.json does not describe this execution")

    # Reading an execution never depends on the plan or specs still matching: a revised plan
    # stops the execution from moving on (context), not from being seen or stopped.
    branch = binding["branch"]
    if run_git(main_checkout, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode != 0:
        return failure("branch_missing", f"execution branch does not exist: {branch}")
    worktree = Path(binding["worktree"])
    if not worktree.is_dir():
        return failure("worktree_missing", f"execution worktree does not exist: {worktree}")
    observed = discover_repository(worktree)
    if not observed.ok or observed.value.common_directory != repository.value.common_directory:
        return failure("worktree_identity_drift", "execution worktree is not a linked worktree of this repository")
    return ok(
        Attempt(
            attempt_id=attempt_id,
            plan_id=plan_id,
            branch=branch,
            worktree=worktree.resolve(),
            binding_path=binding_path,
            evidence_path=evidence_path,
            tmp_path=tmp_path,
            main_checkout=main_checkout,
        )
    )
