"""Canonical repository-relative path safety rules."""
from pathlib import PurePosixPath

SECRET_NAMES = {".env", "credentials.json", "secrets.json"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
TEMP_SUFFIXES = (".log", ".tmp", ".swp", "~")
IGNORED_PARTS = {".agents", "node_modules", "__pycache__", ".pytest_cache"}

def safety_problem(path: str) -> str | None:
    candidate = PurePosixPath(path)
    if not path or candidate.is_absolute() or ".." in candidate.parts:
        return "unsafe relative path"
    lowered = candidate.name.lower()
    if lowered in SECRET_NAMES or lowered.startswith(".env.") or lowered.endswith(SECRET_SUFFIXES):
        return "secret-bearing file"
    if lowered.endswith(TEMP_SUFFIXES):
        return "temporary or log file"
    if any(part in IGNORED_PARTS for part in candidate.parts):
        return "runtime or generated file"
    return None
