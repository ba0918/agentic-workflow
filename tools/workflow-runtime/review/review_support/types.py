"""Typed values shared by review runtime components."""
from __future__ import annotations

import re
from typing import Generic, NamedTuple, TypeVar


JsonObject = dict[str, object]
ValueT = TypeVar("ValueT")

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
COMMIT = re.compile(r"[0-9a-f]{40,64}")
PROFILES = {"default", "document", "skill"}


class RuntimeFailure(NamedTuple):
    """Stable review runtime error."""

    code: str
    message: str


class RuntimeResult(NamedTuple, Generic[ValueT]):
    """A result whose success and failure payloads are mutually exclusive."""

    value: ValueT | None
    error: RuntimeFailure | None

    @property
    def ok(self) -> bool:
        """Return whether the operation succeeded."""

        return self.error is None

    def required(self) -> ValueT:
        """Return a success payload after its state has been checked."""

        assert self.value is not None
        return self.value

    def required_error(self) -> RuntimeFailure:
        """Return a failure payload after its state has been checked."""

        assert self.error is not None
        return self.error


def ok(value: ValueT | None = None) -> RuntimeResult[ValueT]:
    """Build a successful result."""

    return RuntimeResult(value, None)


def failure(code: str, message: str) -> RuntimeResult[object]:
    """Build a failed result."""

    return RuntimeResult(None, RuntimeFailure(code, message))


def object_value(value: object) -> JsonObject | None:
    """Normalize a string-keyed JSON object."""

    if isinstance(value, dict):
        normalized = {str(key): item for key, item in value.items() if isinstance(key, str)}
        if len(normalized) == len(value):
            return normalized
    return None


def object_values(value: object) -> list[JsonObject] | None:
    """Normalize a JSON list containing only objects."""

    if isinstance(value, list):
        normalized = [object_value(item) for item in value]
        if all(item is not None for item in normalized):
            return [item for item in normalized if item is not None]
    return None


def string_values(value: object) -> list[str] | None:
    """Normalize a JSON list containing only strings."""

    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return [item for item in value if isinstance(item, str)]
