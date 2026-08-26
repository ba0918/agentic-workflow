"""Resolve a Git-approved plan and its machine-readable expectations."""
from pathlib import Path, PurePosixPath

from runtime.deps import plan_artifact
from runtime.types import ResolvedPlan, RuntimeResult, failure, ok

def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "" not in path.parts

def validate_relative_path(relative_path: object) -> RuntimeResult:
    if not safe_relative_path(relative_path):
        return failure("unsafe_path", "path must be repository-relative without traversal")
    return ok(relative_path)

def plan_candidates(project_root: Path) -> list[str]:
    store = project_root / "docs/plans"
    if not store.is_dir() or store.is_symlink():
        return []
    return sorted(
        f"docs/plans/{path.name}" for path in store.iterdir()
        if path.is_file() and not path.is_symlink() and path.suffix == ".md"
    )

def locate_plan(project_root: Path, plan_path: str | None = None) -> RuntimeResult:
    if plan_path is not None:
        return ok(plan_path)
    candidates = plan_candidates(project_root)
    if not candidates:
        return failure("plan_candidate_missing", "no unfinished plan exists")
    if len(candidates) > 1:
        return failure("plan_candidate_ambiguous", "several plans exist; name one explicitly", ", ".join(candidates))
    return ok(candidates[0])

def resolve_plan(project_root: Path, *, plan_path: str | None = None) -> RuntimeResult:
    located = locate_plan(project_root, plan_path)
    if not located.ok:
        return located
    try:
        approved = plan_artifact.read_plan(project_root, located.value)
    except plan_artifact.PlanArtifactError as error:
        return failure("plan_invalid", str(error))
    return ok(ResolvedPlan(
        PurePosixPath(approved.path).stem,
        approved.path,
        approved.approval_commit,
        approved.text,
        approved.specifications,
        approved.scope,
    ))
