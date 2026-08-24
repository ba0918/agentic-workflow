"""Result and identity tuples every runtime module speaks in."""
from pathlib import Path
from typing import Any, NamedTuple


class RuntimeFailure(NamedTuple):
    code: str
    message: str
    detail: str | None = None

class RuntimeResult(NamedTuple):
    value: Any | None
    error: RuntimeFailure | None

    @property
    def ok(self) -> bool:
        return self.error is None

class ResolvedPlan(NamedTuple):
    plan_id: str
    path: str
    revision: int
    content_identity: str
    text: str
    specs: tuple[tuple[str, str], ...]
    write_scope: tuple[str, ...]
    human_gates: tuple[dict[str, Any], ...]
    steps: tuple[Any, ...]

class RepositoryInfo(NamedTuple):
    main_checkout: Path
    common_directory: Path
    checkout: Path
    base_head: str
    repository_identity: str

class Attempt(NamedTuple):
    attempt_id: str
    plan_id: str
    branch: str
    worktree: Path
    binding_path: Path
    evidence_path: Path
    tmp_path: Path
    main_checkout: Path

def ok(value: Any = None) -> RuntimeResult:
    return RuntimeResult(value, None)

def failure(code: str, message: str, detail: str | None = None) -> RuntimeResult:
    return RuntimeResult(None, RuntimeFailure(code, message, detail))
