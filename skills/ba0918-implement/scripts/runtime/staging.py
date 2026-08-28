"""Assess every commit path against safety rules and plan expectations."""
from pathlib import Path
import sys
from typing import Mapping

from runtime.types import JsonObject, RuntimeResult, failure, ok

for candidate in (Path(__file__).resolve().parents[2] / "shared", Path(__file__).resolve().parents[1]):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
from path_safety import safety_problem


def _unplanned_path(item: JsonObject) -> str:
    path = item.get("path")
    return path if isinstance(path, str) else ""

def assess_paths(
    paths: list[str],
    *,
    expected_paths: list[str] | tuple[str, ...],
    reasons: Mapping[str, str] | None = None,
    dangerous_paths: Mapping[str, str] | None = None,
) -> RuntimeResult[JsonObject]:
    reasons = reasons or {}
    dangerous_paths = dangerous_paths or {}
    expected = set(expected_paths)
    unplanned: list[JsonObject] = []
    for path in paths:
        problem = safety_problem(path)
        if problem is not None:
            return failure("dangerous_path", problem, path)
        if path in dangerous_paths:
            return failure("human_judgment_required", dangerous_paths[path], path)
    unplanned_paths = set(paths) - expected
    extra_reasons = set(reasons) - unplanned_paths
    if extra_reasons:
        return failure("unplanned_reason_extra", "a reason was supplied for a path that is not unplanned", sorted(extra_reasons)[0])
    for path in paths:
        if path not in expected:
            reason = reasons.get(path, "").strip()
            if not reason:
                return failure("unplanned_reason_missing", "a safe unplanned path needs a reason", path)
            unplanned.append({"path": path, "reason": reason})
    return ok({"paths": sorted(set(paths)), "unplanned": sorted(unplanned, key=_unplanned_path)})
