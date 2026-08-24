"""Reading the registered plan: identity, gates, steps, completion kinds."""
from runtime.gitio import run_git, discover_repository
from runtime.types import Attempt
from pathlib import Path, PurePosixPath
from typing import Any

from runtime.deps import plan_artifact
from runtime.types import RuntimeResult, ResolvedPlan, ok, failure
from runtime.storage import read_json


def parse_plan(text: str) -> RuntimeResult:
    """Read the machine-read parts through the plan skill's reader; implement keeps no parser."""
    try:
        header = plan_artifact.read_plan_header(text)
        write_scope = plan_artifact.read_plan_scope(text)
        steps = plan_artifact.read_plan_steps(text)
        human_gates = tuple(human_gate_value(gate) for gate in plan_artifact.read_plan_human_gates(text))
    except plan_artifact.InvalidPlanFormat as error:
        return failure("plan_format_invalid", str(error))
    specs = tuple((spec.path, spec.content_identity) for spec in header.specifications)
    return ok((header.plan_id, header.revision, specs, write_scope, steps, human_gates))

def raw_identity(text: str) -> str:
    return plan_artifact.content_identity(text)

def human_gate_value(gate: Any) -> dict[str, Any]:
    target = {"kind": gate.target.kind}
    if gate.target.kind == "files":
        target["paths"] = list(gate.target.paths)
    else:
        target["content_identity"] = gate.target.content_identity
    return {
        "gate_id": gate.gate_id,
        "step_id": gate.step_id,
        "sections": list(gate.sections),
        "criterion": gate.criterion,
        "target": target,
        "timing": gate.timing,
        "allowed_results": list(gate.allowed_results),
    }

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
    header_id, header_revision, specs, write_scope, steps, human_gates = parsed.value
    if header_id != registered.plan_id:
        return failure("plan_id_drift", "plan header and locator disagree")
    if header_revision != registered.revision:
        return failure("plan_revision_drift", "plan revision header and locator disagree")

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
            human_gates=human_gates,
            steps=steps,
        )
    )

def step_completion_kinds(attempt: Attempt) -> RuntimeResult:
    binding = read_json(attempt.binding_path)
    if not binding.ok:
        return binding
    try:
        registered = plan_artifact.read_registered_plan(attempt.main_checkout, binding.value["plan"]["path"])
        steps = plan_artifact.read_plan_steps(registered.text)
    except plan_artifact.PlanArtifactError as error:
        return failure("plan_format_invalid", str(error))
    return ok({f"step-{step.number}": step.completion_kind for step in steps})

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
