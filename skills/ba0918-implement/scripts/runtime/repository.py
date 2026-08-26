"""Create an implementation run bound to a Git-approved plan."""
from pathlib import Path

from runtime.storage import canonical_json, write_once
from runtime.types import RUN_ID, ResolvedPlan, Run, RuntimeResult, failure, ok

def bind_run(
    root: Path,
    plan: ResolvedPlan,
    *,
    run_id: str,
    delegated: bool,
    steps: list[str] | None = None,
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
    binding = {
        "version": 1,
        "run_id": run_id,
        "plan_key": plan.plan_key,
        "plan_path": plan.path,
        "approval_commit": plan.approval_commit,
        "expected_paths": list(plan.expected_paths),
        "delegated": delegated,
        "steps": list(steps or []),
        "state": "active",
    }
    write_once(binding_path, canonical_json(binding))
    return ok(Run(run_id, plan.plan_key, repository, evidence, binding_path))
