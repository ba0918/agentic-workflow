"""Shared runtime values."""
from pathlib import Path
import re
from typing import Any, NamedTuple

RUN_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
COMMIT_SHA = re.compile(r"[0-9a-f]{40,64}")

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
    plan_key: str
    path: str
    approval_commit: str
    text: str
    specifications: tuple[Any, ...]
    expected_paths: tuple[str, ...]

class Run(NamedTuple):
    run_id: str
    plan_key: str
    root: Path
    evidence_path: Path
    binding_path: Path

def ok(value: Any = None) -> RuntimeResult:
    return RuntimeResult(value, None)

def failure(code: str, message: str, detail: str | None = None) -> RuntimeResult:
    return RuntimeResult(None, RuntimeFailure(code, message, detail))
