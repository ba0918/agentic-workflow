"""Repository discovery and the bound branch-plus-worktree bootstrap."""
from pathlib import Path

from typing import Callable

from runtime.deps import execution_model
from runtime.types import RuntimeResult, ResolvedPlan, Attempt, ok, failure
from runtime.gitio import run_git, discover_repository
from runtime.storage import write_once, safe_agent_roots, classify_write_error



def preflight(main_checkout: Path, common_directory: Path) -> RuntimeResult:
    probes = [
        main_checkout / ".agents/artifacts/executions/.preflight",
        main_checkout / ".agents/tmp/executions/.preflight",
        common_directory / ".implement-preflight",
    ]
    for probe in probes:
        result = write_once(probe, b"preflight\n")
        if not result.ok:
            return result
        probe.unlink()
    return ok()

def execution_branch(execution_id: str) -> str:
    return f"implement/{execution_id}"

def bootstrap_attempt(
    project_root: Path,
    resolved_plan: ResolvedPlan | None,
    *,
    worktree_path: Path,
    attempt_id_factory: Callable[[], str],
    executor: dict[str, str],
) -> RuntimeResult:
    safe_roots = safe_agent_roots(project_root)
    if not safe_roots.ok:
        return safe_roots
    repository = discover_repository(project_root)
    if not repository.ok:
        return repository
    main_checkout = repository.value.main_checkout
    if resolved_plan is None:
        return failure("plan_registration_missing", "a validated plan is required")
    if worktree_path.exists() or worktree_path.is_symlink():
        return failure("worktree_collision", "requested worktree path already exists")

    preflighted = preflight(main_checkout, repository.value.common_directory)
    if not preflighted.ok:
        return preflighted
    attempt_id = attempt_id_factory()
    if not execution_model.ATTEMPT_ID.fullmatch(attempt_id):
        return failure("attempt_id_invalid", "generated attempt id is not path-safe")
    branch = execution_branch(attempt_id)
    evidence_path = (
        main_checkout
        / ".agents/artifacts/executions"
        / resolved_plan.plan_id
        / attempt_id
    )
    tmp_path = main_checkout / ".agents/tmp/executions" / attempt_id
    if any(path.exists() or path.is_symlink() for path in (evidence_path, tmp_path)):
        return failure("attempt_collision", "generated attempt id is already in use")

    try:
        evidence_path.mkdir(parents=True, exist_ok=False)
        tmp_path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return failure("attempt_collision", "generated attempt id collided during bootstrap")
    except OSError as error:
        return failure(classify_write_error(error), "attempt directories could not be created", str(error))

    binding = {
        "version": 1,
        "attempt_id": attempt_id,
        "plan": {
            "id": resolved_plan.plan_id,
            "path": resolved_plan.path,
            "revision": resolved_plan.revision,
            "content_identity": resolved_plan.content_identity,
        },
        "specs": [
            {"path": path, "content_identity": identity}
            for path, identity in resolved_plan.specs
        ],
        "repository_identity": repository.value.repository_identity,
        "base_head": repository.value.base_head,
        "branch": branch,
        "worktree": str(worktree_path.resolve(strict=False)),
        "write_scope": list(resolved_plan.write_scope),
        "human_gates": list(resolved_plan.human_gates),
        "executor": executor,
    }
    binding_validation = execution_model.validate_binding(binding)
    if not binding_validation.ok:
        return failure(binding_validation.error.code, binding_validation.error.message)
    binding_path = evidence_path / "binding.json"
    binding_result = write_once(binding_path, execution_model.canonical_json(binding))
    if not binding_result.ok:
        return binding_result

    created = run_git(
        main_checkout,
        "worktree",
        "add",
        "-b",
        branch,
        str(worktree_path),
        repository.value.base_head,
    )
    if created.returncode != 0:
        return failure("worktree_create_failed", "Git could not create the linked worktree", created.stderr.strip())
    observed = discover_repository(worktree_path)
    if (
        not observed.ok
        or observed.value.common_directory != repository.value.common_directory
        or observed.value.base_head != repository.value.base_head
        or observed.value.checkout != worktree_path.resolve()
    ):
        return failure("worktree_identity_drift", "created worktree does not match its binding")
    observed_branch = run_git(worktree_path, "branch", "--show-current")
    if observed_branch.returncode != 0 or observed_branch.stdout.strip() != branch:
        return failure("worktree_identity_drift", "created worktree branch does not match its binding")

    event = execution_model.seal_event(
        {
            "version": 1,
            "sequence": 1,
            "event_type": "worktree-bound",
            "attempt_id": attempt_id,
            "plan_identity": resolved_plan.content_identity,
            "spec_identities": dict(resolved_plan.specs),
            "previous_identity": None,
            "outcome": "bound",
            "repository_identity": repository.value.repository_identity,
            "base_head": repository.value.base_head,
            "branch": branch,
            "worktree_identity": execution_model.content_identity(
                {"path": str(worktree_path.resolve()), "common_directory": str(repository.value.common_directory)}
            ),
        }
    )
    if not event.ok:
        return failure(event.error.code, event.error.message)
    event_result = write_once(
        evidence_path / "000001-worktree-bound.json",
        execution_model.canonical_json(event.value),
    )
    if not event_result.ok:
        return event_result
    return ok(
        Attempt(
            attempt_id=attempt_id,
            plan_id=resolved_plan.plan_id,
            branch=branch,
            worktree=worktree_path.resolve(),
            binding_path=binding_path,
            evidence_path=evidence_path,
            tmp_path=tmp_path,
            main_checkout=main_checkout,
        )
    )
