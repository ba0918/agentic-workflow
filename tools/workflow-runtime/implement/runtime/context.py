"""Facts observed while an implementation run is active."""
from runtime.types import RuntimeResult, ok

def document_context(binding: dict, current_commit: str, changed_documents: list[str]) -> RuntimeResult:
    return ok({
        "approval_commit": binding["approval_commit"],
        "current_commit": current_commit,
        "changed_documents": sorted(changed_documents),
    })
