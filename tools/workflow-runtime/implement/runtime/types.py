"""Shared runtime values."""
from pathlib import Path
from dataclasses import dataclass
import re
from typing import Generic, NamedTuple, Never, TypeVar

RUN_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
COMMIT_SHA = re.compile(r"[0-9a-f]{40,64}")
JsonObject = dict[str, object]
ResultValue = TypeVar("ResultValue", covariant=True)
Value = TypeVar("Value")

class RuntimeFailure(NamedTuple):
    code: str
    message: str
    detail: str | None = None

class RuntimeResult(NamedTuple, Generic[ResultValue]):
    value: ResultValue | None
    error: RuntimeFailure | None

    @property
    def ok(self) -> bool:
        return self.error is None

    def required(self) -> ResultValue:
        if self.value is None:
            raise RuntimeError("runtime result has no value")
        return self.value

    def required_error(self) -> RuntimeFailure:
        if self.error is None:
            raise RuntimeError("runtime result has no failure")
        return self.error

@dataclass(frozen=True)
class ResolvedPlan:
    plan_key: str
    path: str
    approval_commit: str
    text: str
    specifications: tuple[object, ...]
    expected_paths: tuple[str, ...]
    specification_changes: tuple[object, ...] = ()
    steps: tuple[object, ...] = ()

class Run(NamedTuple):
    run_id: str
    plan_key: str
    root: Path
    evidence_path: Path
    binding_path: Path

def ok(value: Value) -> RuntimeResult[Value]:
    return RuntimeResult(value, None)

def failure(code: str, message: str, detail: str | None = None) -> RuntimeResult[Never]:
    return RuntimeResult(None, RuntimeFailure(code, message, detail))


def forward_failure(
    error: RuntimeFailure | None, fallback_code: str, fallback_message: str,
) -> RuntimeResult[Never]:
    if error is None:
        return failure(fallback_code, fallback_message)
    return failure(error.code, error.message, error.detail)


def object_value(value: object) -> JsonObject | None:
    mapping = value if isinstance(value, dict) else None
    if mapping is None:
        return None
    if any(not isinstance(key, str) for key in mapping):
        return None
    return {key: item for key, item in mapping.items() if isinstance(key, str)}


def object_values(value: object) -> list[JsonObject] | None:
    if not isinstance(value, list):
        return None
    values: list[JsonObject] = []
    for item in value:
        normalized = object_value(item)
        if normalized is None:
            return None
        values.append(normalized)
    return values


def string_values(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return [item for item in value if isinstance(item, str)]
