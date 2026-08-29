"""Document-following decisions and approved-plan validation."""
from pathlib import Path
import re
from typing import NamedTuple, Protocol

from runtime.deps import plan_artifact
from runtime.gitio import run_git
from runtime.types import COMMIT_SHA, JsonObject, Run, RuntimeResult, failure, ok


class Specification(Protocol):
    path: str
    sections: tuple[str, ...]


class PlanStep(Protocol):
    id: str
    completion: str
    checks: tuple[str, ...]
    human_gates: tuple[JsonObject, ...]


class PlanHeader(Protocol):
    specifications: tuple[Specification, ...]
    steps: tuple[PlanStep, ...]


class DocumentCommit(NamedTuple):
    header: PlanHeader
    scope: tuple[str, ...]


def document_context(
    binding: JsonObject, current_commit: str, changed_documents: list[str],
) -> RuntimeResult[JsonObject]:
    return ok({
        "approval_commit": binding["approval_commit"],
        "current_commit": current_commit,
        "changed_documents": sorted(changed_documents),
    })


def document_decision(
    *, current_commit: str, changed_documents: list[str], important: bool, reason: str,
) -> RuntimeResult[JsonObject]:
    if not reason.strip():
        return failure(
            "document_decision_reason_missing", "document meaning decision needs a reason"
        )
    if important:
        return failure(
            "rebound_or_new_run_required", reason, ", ".join(sorted(changed_documents))
        )
    return ok({
        "event_type": "recovering",
        "current_commit": current_commit,
        "changed_documents": sorted(changed_documents),
        "reason": reason,
    })


def stop_event(
    reason: str, *, changed_documents: list[str] | None = None,
) -> JsonObject:
    return {
        "event_type": "stopped",
        "reason": reason,
        "changed_documents": sorted(changed_documents or []),
    }


def validate_document_commit(
    run: Run, binding: JsonObject, commit: str,
) -> RuntimeResult[DocumentCommit]:
    if COMMIT_SHA.fullmatch(commit) is None or run_git(
        run.root, "cat-file", "-e", f"{commit}^{{commit}}"
    ).returncode != 0:
        return failure("document_commit_invalid", "document commit does not exist")
    plan_path = binding.get("plan_path")
    if not isinstance(plan_path, str):
        return failure(
            "document_commit_invalid", "plan is unavailable in the document commit"
        )
    plan = run_git(run.root, "show", f"{commit}:{plan_path}")
    if plan.returncode != 0:
        return failure(
            "document_commit_invalid", "plan is unavailable in the document commit"
        )
    try:
        header: PlanHeader = plan_artifact.read_plan_header(plan.stdout)
        scope: tuple[str, ...] = plan_artifact.read_plan_scope(plan.stdout)
    except plan_artifact.PlanArtifactError:
        return failure(
            "document_commit_invalid", "plan cannot be read from the document commit"
        )
    if not _specifications_available(run.root, commit, header.specifications):
        return failure(
            "document_commit_invalid",
            "target specification is unavailable in the document commit",
        )
    return ok(DocumentCommit(header, scope))


def plan_scope_unchanged(
    run: Run, binding: JsonObject, current_scope: tuple[str, ...],
) -> RuntimeResult[None]:
    """Following may move wording; a moved Scope changes what is judged and needs a rebound."""
    plan_path = binding.get("plan_path")
    approval_commit = binding.get("approval_commit")
    if not isinstance(plan_path, str) or not isinstance(approval_commit, str):
        return failure("document_commit_invalid", "plan is unavailable in the approval commit")
    approved = run_git(run.root, "show", f"{approval_commit}:{plan_path}")
    if approved.returncode != 0:
        return failure("document_commit_invalid", "plan is unavailable in the approval commit")
    try:
        approved_scope = plan_artifact.read_plan_scope(approved.stdout)
    except plan_artifact.PlanArtifactError:
        return failure("document_commit_invalid", "plan cannot be read from the approval commit")
    if approved_scope != current_scope:
        return failure(
            "rebound_or_new_run_required",
            "plan Scope changed after approval; rebound or start a new run",
            plan_path,
        )
    return ok(None)


def _specifications_available(
    root: Path, commit: str, specifications: tuple[Specification, ...],
) -> bool:
    for specification in specifications:
        content = run_git(root, "show", f"{commit}:{specification.path}")
        headings_unique = content.returncode == 0 and all(
            len(re.findall(rf"^#+\s+{re.escape(section)}\s*$", content.stdout, re.MULTILINE))
            == 1
            for section in specification.sections
        )
        if not headings_unique:
            return False
    return True
