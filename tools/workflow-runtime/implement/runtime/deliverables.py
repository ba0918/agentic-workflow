"""Evidence payloads for non-test completion kinds."""
from runtime.types import JsonObject

def artifact_event(step: str, paths: list[str], checks: list[JsonObject]) -> JsonObject:
    return {
        "event_type": "artifact",
        "step": step,
        "paths": sorted(paths),
        "checks": list(checks),
    }

def external_event(step: str, checked: str, summary: str) -> JsonObject:
    return {
        "event_type": "external",
        "step": step,
        "checked": checked,
        "summary": summary,
    }

def check_event(step: str, checks: list[JsonObject], paths: list[str]) -> JsonObject:
    return {
        "event_type": "check",
        "step": step,
        "checks": list(checks),
        "paths": sorted(paths),
    }
