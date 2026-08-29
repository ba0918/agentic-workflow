"""Filesystem and changed-path safety checks."""
from pathlib import Path
from typing import Mapping

from runtime.staging import assess_paths
from runtime.types import JsonObject, Run, RuntimeResult, failure, ok


def worktree(binding: JsonObject, run: Run) -> Path:
    value = binding.get("worktree")
    return Path(value) if isinstance(value, str) and value else run.root


def assess_safety(
    binding: JsonObject,
    paths: list[str],
    reasons: Mapping[str, str] | None = None,
) -> RuntimeResult[JsonObject]:
    expected = binding.get("expected_paths")
    expected_paths = [path for path in expected if isinstance(path, str)] if isinstance(
        expected, list
    ) else []
    assessed = assess_paths(paths, expected_paths=expected_paths, reasons=reasons or {})
    if not assessed.ok:
        return assessed
    value = assessed.required()
    return ok({"paths": value["paths"], "unplanned": value["unplanned"]})


def test_bytes(checkout: Path, paths: list[str]) -> RuntimeResult[dict[str, bytes]]:
    values: dict[str, bytes] = {}
    for relative in paths:
        target = checkout / relative
        if target.is_symlink() or not target.is_file():
            return failure(
                "frozen_red_unavailable", f"test or fixture is unavailable: {relative}"
            )
        values[relative] = target.read_bytes()
    return ok(values)
