"""Result tuples, identity shapes and the vocabulary every runtime module speaks in."""
import re
from pathlib import Path
from typing import Any, NamedTuple

IDENTITY = re.compile(r"sha256:[0-9a-f]{64}")
ATTEMPT_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
COMMIT_SHA = re.compile(r"[0-9a-f]{40,64}")
# Only a behavior failure is an approved missing behavior; import, fixture, permission and
# network failures are never an expected RED, so the candidate may not predict them.
APPROVAL_RESULTS = ["approved", "rejected"]


def matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None



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
