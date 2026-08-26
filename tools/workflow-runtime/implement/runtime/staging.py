"""Assess every commit path against safety rules and plan expectations."""
from pathlib import PurePosixPath
from typing import Mapping

from runtime.planning import safe_relative_path
from runtime.types import RuntimeResult, failure, ok

SECRET_NAMES = {".env", "credentials.json", "secrets.json"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
TEMP_SUFFIXES = (".log", ".tmp", ".swp", "~")
IGNORED_PARTS = {".agents", "node_modules", "__pycache__", ".pytest_cache"}

def _safety_problem(path: str) -> str | None:
    if not safe_relative_path(path):
        return "unsafe relative path"
    candidate = PurePosixPath(path)
    lowered = candidate.name.lower()
    if lowered in SECRET_NAMES or lowered.startswith(".env.") or lowered.endswith(SECRET_SUFFIXES):
        return "secret-bearing file"
    if lowered.endswith(TEMP_SUFFIXES):
        return "temporary or log file"
    if any(part in IGNORED_PARTS for part in candidate.parts):
        return "runtime or generated file"
    return None

def assess_paths(
    paths: list[str],
    *,
    expected_paths: list[str] | tuple[str, ...],
    reasons: Mapping[str, str] | None = None,
    dangerous_paths: Mapping[str, str] | None = None,
) -> RuntimeResult:
    reasons = reasons or {}
    dangerous_paths = dangerous_paths or {}
    expected = set(expected_paths)
    unplanned: list[dict[str, str]] = []
    for path in paths:
        problem = _safety_problem(path)
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
    return ok({"paths": sorted(set(paths)), "unplanned": sorted(unplanned, key=lambda item: item["path"])})
