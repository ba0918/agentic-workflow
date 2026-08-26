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

def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "" not in path.parts


def validate_write_path(relative_path: str, scopes: list[str]) -> RuntimeResult:
    if not safe_relative_path(relative_path):
        return failure("write_scope_violation", "write path is unsafe", relative_path)
    candidate = PurePosixPath(relative_path)
    for raw_scope in scopes:
        if not safe_relative_path(raw_scope):
            continue
        scope = PurePosixPath(raw_scope)
        if candidate == scope:
            return ok(relative_path)
        if scope.suffix == "" and candidate.parts[: len(scope.parts)] == scope.parts:
            return ok(relative_path)
    return failure("write_scope_violation", "write path is outside the approved scope", relative_path)


def validate_relative_path(relative_path: object) -> RuntimeResult:
    if not safe_relative_path(relative_path):
        return failure("unsafe_path", "path must be repository-relative without traversal", None)
    return ok(relative_path)


def raw_identity(text: str) -> str:
    return plan_artifact.content_identity(text)

def read_plan_file(project_root: Path, relative_path: str) -> RuntimeResult:
    """Read the plan the agent named, straight from the working tree.

    The path is checked for safety; the bytes are taken as they are. Their identity is what the
    execution binds to — the plan is a document a human approved and may go on correcting, so
    nothing here asks whether it still matches some earlier copy of itself.
    """
    if not validate_relative_path(relative_path).ok:
        return failure("unsafe_path", "plan path must be repository-relative without traversal")
    # A draft lives in the machine's scratch directory and is not a plan a human approved
    # (docs/spec/plan.md, "草稿と承認"); binding an execution to one would bind it to nothing.
    if PurePosixPath(relative_path).parts[:2] == (".agents", "tmp"):
        return failure("plan_registration_missing", f"{relative_path} is a draft, not an approved plan")
    path = project_root.joinpath(*PurePosixPath(relative_path).parts)
    if path.is_symlink() or not path.is_file():
        return failure("plan_registration_missing", f"no plan exists at {relative_path}")
    return ok(path.read_text(encoding="utf-8"))

def resolve_plan(
    project_root: Path,
    *,
    plan_path: str | None = None,
    plan_id: str | None = None,
    revision: int | None = None,
    receipt: dict[str, str] | None = None,
) -> RuntimeResult:
    """The plan the agent named, read for the two parts a machine reads.

    Its id and revision come from the agent that read the document, not from a parser or a
    locator (docs/spec/plan.md, "機械が決まった書き方で読む箇所は 2 つだけ").
    """
    if receipt is not None and plan_path is not None and receipt.get("path") != plan_path:
        return failure("plan_candidate_conflict", "explicit path and publication receipt disagree")
    if plan_path is not None:
        if not isinstance(plan_id, str) or not plan_id.strip():
            return failure("plan_declaration_missing", "name the plan id you read out of the plan")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            return failure("plan_declaration_missing", "name the plan revision you read out of the plan")
        loaded = read_plan_file(project_root, plan_path)
        if not loaded.ok:
            return loaded
        text = loaded.value
        identity = raw_identity(text)
        if receipt is not None and receipt.get("content_identity") != identity:
            return failure("plan_candidate_conflict", "explicit path and publication receipt disagree")
        registered = ResolvedPlan(
            plan_id=plan_id,
            path=plan_path,
            revision=revision,
            content_identity=identity,
            text=text,
            specs=(),
            write_scope=(),
        )
    else:
        try:
            located = plan_artifact.read_registered_plan(project_root, receipt.get("path") if receipt else None)
        except plan_artifact.PlanRegistrationMissing as error:
            return failure("plan_registration_missing", str(error))
        except plan_artifact.RegisteredPlanMismatch as error:
            return failure("plan_identity_drift", str(error))
        except plan_artifact.UnsafePlanPath as error:
            return failure("unsafe_path", str(error))
        except plan_artifact.PlanArtifactError as error:
            return failure("plan_locator_invalid", str(error))
        if receipt is not None and receipt.get("content_identity") != located.content_identity:
            return failure("plan_identity_drift", "publication receipt differs from the locator")
        registered = ResolvedPlan(
            plan_id=plan_id or located.plan_id,
            path=located.path,
            revision=revision if isinstance(revision, int) and not isinstance(revision, bool) else located.revision,
            content_identity=located.content_identity,
            text=located.text,
            specs=(),
            write_scope=(),
        )
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

    return ok(registered._replace(specs=specs, write_scope=write_scope))

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
