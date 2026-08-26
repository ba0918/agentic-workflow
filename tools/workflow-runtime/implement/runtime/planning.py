"""Reading the registered plan: identity, gates, steps, completion kinds."""
from runtime.gitio import run_git, discover_repository
from runtime.types import Attempt
from pathlib import Path, PurePosixPath
from typing import Any

from runtime.deps import plan_artifact
from runtime.types import RuntimeResult, ResolvedPlan, ok, failure
from runtime.storage import read_json


def parse_plan(text: str) -> RuntimeResult:
    """The two parts of a plan a machine reads: the specifications it stands on, and the files it
    may touch. Both are compared against the world outside the document, so both need a fixed
    shape. The steps, their completion kinds and the human decisions are read by the agent."""
    try:
        header = plan_artifact.read_plan_header(text)
        write_scope = plan_artifact.read_plan_scope(text)
    except plan_artifact.InvalidPlanFormat as error:
        return failure("plan_format_invalid", str(error))
    specs = tuple((spec.path, spec.content_identity) for spec in header.specifications)
    return ok((specs, write_scope))

def raw_identity(text: str) -> str:
    return plan_artifact.content_identity(text)

def resolve_plan(
    project_root: Path,
    *,
    explicit_path: str | None = None,
    receipt: dict[str, str] | None = None,
) -> RuntimeResult:
    if receipt is not None and explicit_path is not None and receipt.get("path") != explicit_path:
        return failure("plan_candidate_conflict", "explicit path and publication receipt disagree")
    selected_path = explicit_path
    if selected_path is None and receipt is not None:
        selected_path = receipt.get("path")
    try:
        registered = plan_artifact.read_registered_plan(project_root, selected_path)
    except plan_artifact.PlanRegistrationMissing as error:
        return failure("plan_registration_missing", str(error))
    except plan_artifact.RegisteredPlanMismatch as error:
        return failure("plan_identity_drift", str(error))
    except plan_artifact.UnsafePlanPath as error:
        return failure("unsafe_path", str(error))
    except plan_artifact.PlanArtifactError as error:
        return failure("plan_locator_invalid", str(error))

    if receipt is not None:
        if receipt.get("content_identity") != registered.content_identity:
            if explicit_path is not None:
                return failure(
                    "plan_candidate_conflict",
                    "explicit path and publication receipt disagree",
                )
            return failure("plan_identity_drift", "publication receipt differs from the locator")
    parsed = parse_plan(registered.text)
    if not parsed.ok:
        return parsed
    specs, write_scope = parsed.value

    repository = discover_repository(project_root)
    if not repository.ok:
        return repository
    for spec_path, expected_identity in specs:
        path = repository.value.main_checkout.joinpath(*PurePosixPath(spec_path).parts)
        if path.is_symlink() or not path.is_file():
            return failure("spec_unavailable", f"approved spec is unavailable: {spec_path}")
        current_identity = raw_identity(path.read_text(encoding="utf-8"))
        if current_identity != expected_identity:
            return failure("spec_identity_drift", f"approved spec bytes changed: {spec_path}")
        committed = run_git(repository.value.main_checkout, "show", f"{repository.value.base_head}:{spec_path}")
        if committed.returncode != 0 or raw_identity(committed.stdout) != expected_identity:
            return failure("spec_identity_drift", f"approved spec is not present at base HEAD: {spec_path}")

    return ok(
        ResolvedPlan(
            plan_id=registered.plan_id,
            path=registered.path,
            revision=registered.revision,
            content_identity=registered.content_identity,
            text=registered.text,
            specs=specs,
            write_scope=write_scope,
        )
    )

def declared_steps(attempt: Attempt) -> RuntimeResult:
    """The steps the agent declared when the execution was bound, after any rebound.

    Declared once and read from the record ever after: reading them from the plan text on every
    call would put a parser back where this design removed one.
    """
    # context imports this module, so the effective binding is fetched at call time rather than
    # at module load: importing it at the top would close an import cycle.
    from runtime.context import load_effective_binding

    binding = load_effective_binding(attempt)
    if not binding.ok:
        return binding
    steps = binding.value.get("steps")
    if not isinstance(steps, list) or not steps:
        return failure("steps_undeclared", "the execution was bound without any declared step")
    return ok(steps)

def step_completion_kinds(attempt: Attempt) -> RuntimeResult:
    steps = declared_steps(attempt)
    if not steps.ok:
        return steps
    return ok({step["step_id"]: step["completion"] for step in steps.value})

def step_ids(attempt: Attempt) -> RuntimeResult:
    steps = declared_steps(attempt)
    if not steps.ok:
        return steps
    return ok([step["step_id"] for step in steps.value])

def step_checks(attempt: Attempt, step_id: str) -> RuntimeResult:
    """The check commands declared for the step, in the order they were named."""
    steps = declared_steps(attempt)
    if not steps.ok:
        return steps
    declared = {step["step_id"]: list(step.get("checks") or []) for step in steps.value}
    if step_id not in declared:
        return failure("step_unknown", f"the plan has no step {step_id}")
    return ok(declared[step_id])

def require_completion_kind(attempt: Attempt, step_id: str, expected: str) -> RuntimeResult:
    kinds = step_completion_kinds(attempt)
    if not kinds.ok:
        return kinds
    actual = kinds.value.get(step_id)
    if actual is None:
        return failure("step_unknown", f"the plan has no step {step_id}")
    if actual != expected:
        return failure(
            "completion_kind_mismatch",
            f"{step_id} is shown by '{actual}', not '{expected}'",
        )
    return ok(actual)
