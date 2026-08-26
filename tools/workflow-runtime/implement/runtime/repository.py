"""Create an implementation run bound to a Git-approved plan."""
from pathlib import Path

from runtime.storage import canonical_json, read_json, write_once
from runtime.types import RUN_ID, ResolvedPlan, Run, RuntimeResult, failure, ok

def bind_run(
    root: Path,
    plan: ResolvedPlan,
    *,
    run_id: str,
    delegated: bool,
    steps: list[str | dict] | None = None,
    branch: str | None = None,
    worktree: str | None = None,
) -> RuntimeResult:
    if RUN_ID.fullmatch(run_id) is None:
        return failure("run_id_invalid", "run id is not path-safe")
    repository = root.resolve()
    evidence = repository / ".agents/evidence" / plan.plan_key / run_id
    for path in (repository / ".agents", repository / ".agents/evidence", evidence):
        if path.is_symlink():
            return failure("unsafe_path", f"symlink is not allowed: {path}")
    if evidence.exists():
        return failure("run_collision", "run evidence already exists")
    evidence.mkdir(parents=True)
    binding_path = evidence / "binding.json"
    normalized_steps = [
        {"id": step, "completion": "test"} if isinstance(step, str) else dict(step)
        for step in (steps or [])
    ]
    if any(
        not isinstance(step.get("id"), str)
        or step.get("completion") not in {"test", "check", "artifact", "external"}
        for step in normalized_steps
    ) or len({step["id"] for step in normalized_steps}) != len(normalized_steps):
        return failure("step_contract_invalid", "steps need unique ids and a supported completion kind")
    if (branch is None) != (worktree is None):
        return failure("worktree_binding_incomplete", "branch and worktree must be supplied together")
    binding = {
        "version": 1,
        "run_id": run_id,
        "plan_key": plan.plan_key,
        "plan_path": plan.path,
        "approval_commit": plan.approval_commit,
        "expected_paths": list(plan.expected_paths),
        "delegated": delegated,
        "steps": normalized_steps,
        "branch": branch,
        "worktree": str(Path(worktree).resolve()) if worktree is not None else None,
        "state": "active",
    }
    write_once(binding_path, canonical_json(binding))
    run = Run(run_id, plan.plan_key, repository, evidence, binding_path)
    if branch is not None and worktree is not None:
        from runtime.context import append_event
        bound = append_event(
            run, "worktree-bound", {"branch": branch, "worktree": str(Path(worktree).resolve())},
            actor="cycle" if delegated else "implement",
        )
        if not bound.ok:
            return bound
    return ok(run)

def load_run(root: Path, plan_key: str, run_id: str) -> RuntimeResult:
    if RUN_ID.fullmatch(plan_key) is None or RUN_ID.fullmatch(run_id) is None:
        return failure("run_id_invalid", "plan key and run id must be path-safe")
    repository = root.resolve()
    evidence = repository / ".agents/evidence" / plan_key / run_id
    binding_path = evidence / "binding.json"
    binding = read_json(binding_path)
    if not binding.ok:
        return binding
    if binding.value.get("plan_key") != plan_key or binding.value.get("run_id") != run_id:
        return failure("run_binding_invalid", "run path and binding differ")
    return ok(Run(run_id, plan_key, repository, evidence, binding_path))
