"""Create and load implementation runs bound to approved plans."""
from datetime import datetime, timezone
import inspect
from pathlib import Path
import shutil
from typing import NamedTuple, Protocol, runtime_checkable

from runtime.gitio import run_git
from runtime.storage import canonical_json, read_json, write_once
from runtime.types import (
    RUN_ID, JsonObject, ResolvedPlan, Run, RuntimeResult, failure, ok,
)


@runtime_checkable
class StepValue(Protocol):
    id: str
    completion: str
    checks: tuple[str, ...]


class BindingData(NamedTuple):
    repository: Path
    plan: ResolvedPlan
    run_id: str
    delegated: bool
    branch: str | None
    checkout: Path | None
    steps: list[JsonObject]
    evidence: Path


class BindOptions(NamedTuple):
    run_id: str
    delegated: bool
    branch: str | None
    worktree: str | None


def _step(value: object) -> JsonObject | None:
    if isinstance(value, dict):
        identifier = value.get("id")
        completion = value.get("completion")
        checks_value = value.get("checks", ())
    elif isinstance(value, StepValue):
        identifier = value.id
        completion = value.completion
        checks_value = value.checks
    else:
        return None
    if not isinstance(identifier, str) or not isinstance(completion, str):
        return None
    if not isinstance(checks_value, (list, tuple)) or not all(
        isinstance(command, str) for command in checks_value
    ):
        return None
    return {"id": identifier, "completion": completion, "checks": list(checks_value)}


def _normalized_steps(plan: ResolvedPlan) -> RuntimeResult[list[JsonObject]]:
    normalized = [_step(value) for value in plan.steps]
    if any(value is None for value in normalized):
        return failure(
            "step_contract_invalid", "steps need unique ids and a supported completion kind"
        )
    steps = [value for value in normalized if value is not None]
    identifiers = [value.get("id") for value in steps]
    supported = all(
        step.get("completion") in {"test", "check", "artifact", "external"}
        and _checks_match_completion(step)
        for step in steps
    )
    if not steps or len(identifiers) != len(set(identifiers)) or not supported:
        return failure(
            "step_contract_invalid", "steps need unique ids and a supported completion kind"
        )
    return ok(steps)


def _checks_match_completion(step: JsonObject) -> bool:
    checks = step.get("checks")
    if not isinstance(checks, list):
        return False
    if step.get("completion") != "check":
        return not checks
    return bool(checks) and all(isinstance(command, str) and command for command in checks)


def _checkout(
    repository: Path, branch: str | None, worktree_value: str | None,
) -> RuntimeResult[Path | None]:
    if (branch is None) != (worktree_value is None):
        return failure(
            "worktree_binding_incomplete", "branch and worktree must be supplied together"
        )
    checkout = Path(worktree_value).resolve() if worktree_value is not None else None
    unsafe = branch is not None and (
        not branch
        or branch.startswith("-")
        or ".." in branch
        or checkout is None
        or not checkout.is_dir()
    )
    if unsafe:
        return failure("worktree_binding_invalid", "branch or worktree is unsafe")
    if checkout is not None and branch is not None and not _same_checkout(
        repository, checkout, branch
    ):
        return failure(
            "worktree_binding_invalid",
            "branch and worktree must name the same repository checkout",
        )
    return ok(checkout)


def _same_checkout(repository: Path, checkout: Path, branch: str) -> bool:
    actual_branch = run_git(checkout, "branch", "--show-current")
    root_common = run_git(repository, "rev-parse", "--git-common-dir")
    checkout_common = run_git(checkout, "rev-parse", "--git-common-dir")
    commands_succeeded = all(
        result.returncode == 0 for result in (actual_branch, root_common, checkout_common)
    )
    if not commands_succeeded or actual_branch.stdout.strip() != branch:
        return False
    return (repository / root_common.stdout.strip()).resolve() == (
        checkout / checkout_common.stdout.strip()
    ).resolve()


def _binding(data: BindingData) -> JsonObject:
    return {
        "version": 2,
        "run_id": data.run_id,
        "plan_key": data.plan.plan_key,
        "plan_path": data.plan.path,
        "approval_commit": data.plan.approval_commit,
        "expected_paths": list(data.plan.expected_paths),
        "delegated": data.delegated,
        "steps": data.steps,
        "branch": data.branch,
        "worktree": str(data.checkout) if data.checkout is not None else None,
        "state": "active",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def _binding_paths(repository: Path, plan_key: str, run_id: str) -> RuntimeResult[Path]:
    evidence = repository / ".agents/evidence" / plan_key / run_id
    for path in (repository / ".agents", repository / ".agents/evidence", evidence):
        if path.is_symlink():
            return failure("unsafe_path", f"symlink is not allowed: {path}")
    if evidence.exists():
        return failure("run_collision", "run evidence already exists")
    return ok(evidence)


def _bind_run(
    root: Path, plan: ResolvedPlan, options: BindOptions,
) -> RuntimeResult[Run]:
    if RUN_ID.fullmatch(options.run_id) is None or RUN_ID.fullmatch(plan.plan_key) is None:
        return failure("run_id_invalid", "run id is not path-safe")
    repository = root.resolve()
    steps = _normalized_steps(plan)
    checkout = _checkout(repository, options.branch, options.worktree)
    evidence = _binding_paths(repository, plan.plan_key, options.run_id)
    for checked in (steps, checkout, evidence):
        if not checked.ok:
            return failure(
                checked.error.code if checked.error is not None else "run_binding_failed",
                checked.error.message if checked.error is not None else "run binding failed",
                checked.error.detail if checked.error is not None else None,
            )
    checkout_path = checkout.value
    if checkout_path is not None and run_git(
        repository, "cat-file", "-e", f"{plan.approval_commit}^{{commit}}"
    ).returncode != 0:
        return failure(
            "approval_commit_invalid", "plan approval commit does not exist"
        )
    return _write_binding(BindingData(
        repository, plan, options.run_id, options.delegated, options.branch, checkout_path,
        steps.required(), evidence.required(),
    ))


class BindRun:
    __signature__ = inspect.Signature(
        parameters=(
            inspect.Parameter("root", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Path),
            inspect.Parameter(
                "plan", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ResolvedPlan
            ),
            inspect.Parameter(
                "run_id", inspect.Parameter.KEYWORD_ONLY, annotation=str
            ),
            inspect.Parameter(
                "delegated", inspect.Parameter.KEYWORD_ONLY, annotation=bool
            ),
            inspect.Parameter(
                "branch", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=str | None
            ),
            inspect.Parameter(
                "worktree", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=str | None
            ),
        ),
        return_annotation=RuntimeResult[Run],
    )

    def __call__(
        self,
        root: Path,
        plan: ResolvedPlan,
        *,
        run_id: str,
        delegated: bool,
        **checkout: str | None,
    ) -> RuntimeResult[Run]:
        unexpected = set(checkout) - {"branch", "worktree"}
        if unexpected:
            name = sorted(unexpected)[0]
            raise TypeError(f"bind_run() got an unexpected keyword argument '{name}'")
        return _bind_run(root, plan, BindOptions(
            run_id, delegated, checkout.get("branch"), checkout.get("worktree")
        ))


bind_run = BindRun()


def _write_binding(data: BindingData) -> RuntimeResult[Run]:
    binding_path = data.evidence / "binding.json"
    binding = _binding(data)
    data.evidence.mkdir(parents=True)
    run = Run(
        data.run_id, data.plan.plan_key, data.repository, data.evidence, binding_path
    )
    try:
        write_once(binding_path, canonical_json(binding))
        if data.branch is not None and data.checkout is not None:
            from runtime.context import append_event
            bound = append_event(
                run,
                "worktree-bound",
                {"branch": data.branch, "worktree": str(data.checkout)},
                actor="cycle" if data.delegated else "implement",
            )
            if not bound.ok:
                shutil.rmtree(data.evidence)
                return failure(
                    bound.error.code if bound.error is not None else "run_binding_failed",
                    bound.error.message if bound.error is not None else "run binding failed",
                    bound.error.detail if bound.error is not None else None,
                )
    except (OSError, FileExistsError) as error:
        shutil.rmtree(data.evidence, ignore_errors=True)
        return failure(
            "run_binding_failed", "run binding could not be recorded", str(error)
        )
    return ok(run)


def load_run(root: Path, plan_key: str, run_id: str) -> RuntimeResult[Run]:
    if RUN_ID.fullmatch(plan_key) is None or RUN_ID.fullmatch(run_id) is None:
        return failure("run_id_invalid", "plan key and run id must be path-safe")
    repository = root.resolve()
    evidence = repository / ".agents/evidence" / plan_key / run_id
    binding_path = evidence / "binding.json"
    binding = read_json(binding_path)
    if not binding.ok:
        return failure(
            binding.error.code if binding.error is not None else "evidence_unavailable",
            binding.error.message if binding.error is not None else "binding is unavailable",
            binding.error.detail if binding.error is not None else None,
        )
    value = binding.required()
    if value.get("version") == 1:
        return failure(
            "legacy_evidence_unsupported", "version 1 implementation evidence is unsupported"
        )
    if value.get("version") != 2:
        return failure(
            "run_binding_invalid", "implementation binding version is invalid"
        )
    if value.get("plan_key") != plan_key or value.get("run_id") != run_id:
        return failure("run_binding_invalid", "run path and binding differ")
    return ok(Run(run_id, plan_key, repository, evidence, binding_path))
