"""Create an implementation run bound to a Git-approved plan."""
from pathlib import Path
from datetime import datetime, timezone
import shutil
import subprocess

from runtime.storage import canonical_json, read_json, write_once
from runtime.types import RUN_ID, ResolvedPlan, Run, RuntimeResult, failure, ok

def bind_run(
    root: Path,
    plan: ResolvedPlan,
    *,
    run_id: str,
    delegated: bool,
    branch: str | None = None,
    worktree: str | None = None,
) -> RuntimeResult:
    if RUN_ID.fullmatch(run_id) is None or RUN_ID.fullmatch(plan.plan_key) is None:
        return failure("run_id_invalid", "run id is not path-safe")
    repository = root.resolve()
    normalized_steps = [
        {
            "id": step["id"] if isinstance(step, dict) else step.id,
            "completion": step["completion"] if isinstance(step, dict) else step.completion,
        }
        for step in plan.steps
    ]
    if any(
        not isinstance(step.get("id"), str)
        or step.get("completion") not in {"test", "check", "artifact", "external"}
        for step in normalized_steps
    ) or not normalized_steps or len({step["id"] for step in normalized_steps}) != len(normalized_steps):
        return failure("step_contract_invalid", "steps need unique ids and a supported completion kind")
    if (branch is None) != (worktree is None):
        return failure("worktree_binding_incomplete", "branch and worktree must be supplied together")
    resolved_worktree = Path(worktree).resolve() if worktree is not None else None
    if branch is not None and (
        not branch or branch.startswith("-") or ".." in branch
        or resolved_worktree is None or not resolved_worktree.is_dir()
    ):
        return failure("worktree_binding_invalid", "branch or worktree is unsafe")
    if resolved_worktree is not None:
        actual_branch = subprocess.run(
            ["git", "-C", str(resolved_worktree), "branch", "--show-current"],
            text=True, capture_output=True, check=False,
        )
        root_common = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--git-common-dir"],
            text=True, capture_output=True, check=False,
        )
        worktree_common = subprocess.run(
            ["git", "-C", str(resolved_worktree), "rev-parse", "--git-common-dir"],
            text=True, capture_output=True, check=False,
        )
        if (
            actual_branch.returncode != 0 or actual_branch.stdout.strip() != branch
            or root_common.returncode != 0 or worktree_common.returncode != 0
            or (repository / root_common.stdout.strip()).resolve()
            != (resolved_worktree / worktree_common.stdout.strip()).resolve()
        ):
            return failure("worktree_binding_invalid", "branch and worktree must name the same repository checkout")
    if resolved_worktree is not None:
        approval = subprocess.run(
            ["git", "-C", str(repository), "cat-file", "-e", f"{plan.approval_commit}^{{commit}}"],
            capture_output=True, check=False,
        )
        if approval.returncode != 0:
            return failure("approval_commit_invalid", "plan approval commit does not exist")
    evidence = repository / ".agents/evidence" / plan.plan_key / run_id
    for path in (repository / ".agents", repository / ".agents/evidence", evidence):
        if path.is_symlink():
            return failure("unsafe_path", f"symlink is not allowed: {path}")
    if evidence.exists():
        return failure("run_collision", "run evidence already exists")
    binding_path = evidence / "binding.json"
    binding = {
        "version": 2,
        "run_id": run_id,
        "plan_key": plan.plan_key,
        "plan_path": plan.path,
        "approval_commit": plan.approval_commit,
        "expected_paths": list(plan.expected_paths),
        "delegated": delegated,
        "steps": normalized_steps,
        "branch": branch,
        "worktree": str(resolved_worktree) if resolved_worktree is not None else None,
        "state": "active",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence.mkdir(parents=True)
    run = Run(run_id, plan.plan_key, repository, evidence, binding_path)
    try:
        write_once(binding_path, canonical_json(binding))
        if branch is not None and resolved_worktree is not None:
            from runtime.context import append_event
            bound = append_event(
                run, "worktree-bound", {"branch": branch, "worktree": str(resolved_worktree)},
                actor="cycle" if delegated else "implement",
            )
            if not bound.ok:
                shutil.rmtree(evidence)
                return bound
    except (OSError, FileExistsError) as error:
        shutil.rmtree(evidence, ignore_errors=True)
        return failure("run_binding_failed", "run binding could not be recorded", str(error))
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
    if binding.value.get("version") == 1:
        return failure("legacy_evidence_unsupported", "version 1 implementation evidence is unsupported")
    if binding.value.get("version") != 2:
        return failure("run_binding_invalid", "implementation binding version is invalid")
    if binding.value.get("plan_key") != plan_key or binding.value.get("run_id") != run_id:
        return failure("run_binding_invalid", "run path and binding differ")
    return ok(Run(run_id, plan_key, repository, evidence, binding_path))
