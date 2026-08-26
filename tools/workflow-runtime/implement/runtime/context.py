"""Append and inspect implementation evidence."""
from runtime.storage import canonical_json, read_json, write_once
from runtime.types import Run, RuntimeResult, failure, ok

def document_context(binding: dict, current_commit: str, changed_documents: list[str]) -> RuntimeResult:
    return ok({
        "approval_commit": binding["approval_commit"],
        "current_commit": current_commit,
        "changed_documents": sorted(changed_documents),
    })

def document_decision(
    *,
    current_commit: str,
    changed_documents: list[str],
    important: bool,
    reason: str,
) -> RuntimeResult:
    if not reason.strip():
        return failure("document_decision_reason_missing", "document meaning decision needs a reason")
    if important:
        return failure("rebound_or_new_run_required", reason, ", ".join(sorted(changed_documents)))
    return ok({
        "event_type": "documents-followed",
        "current_commit": current_commit,
        "changed_documents": sorted(changed_documents),
        "reason": reason,
    })

def stop_event(reason: str, *, changed_documents: list[str] | None = None) -> dict:
    return {
        "event_type": "stopped",
        "reason": reason,
        "changed_documents": sorted(changed_documents or []),
    }

def append_event(run: Run, event_type: str, fields: dict, *, actor: str | None = None) -> RuntimeResult:
    binding = read_json(run.binding_path)
    if not binding.ok:
        return binding
    events = load_events(run)
    if not events.ok:
        return events
    if actor is None:
        actor = "cycle" if event_type in {"delegation-started", "delegation-finished"} else "implement"
    active_delegation = False
    for existing in events.value:
        if existing.get("event_type") == "delegation-started":
            active_delegation = True
        elif existing.get("event_type") == "delegation-finished":
            active_delegation = False
    if actor == "cycle":
        allowed = binding.value.get("delegated") and (
            (event_type == "delegation-started" and not active_delegation) or (
                event_type == "delegation-finished" and active_delegation
            )
        )
        if not allowed:
            return failure("writer_not_allowed", "cycle writes only delegation boundaries outside implementation evidence")
    elif actor != "implement":
        return failure("writer_not_allowed", "unknown evidence writer")
    elif event_type in {"delegation-started", "delegation-finished"}:
        return failure("writer_not_allowed", "cycle is the only writer of delegation boundaries")
    elif binding.value.get("delegated") and not active_delegation:
        return failure("writer_not_allowed", "implement writes delegated evidence only during active delegation")
    sequence = len(list(run.evidence_path.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json"))) + 1
    event = {"version": 1, "sequence": sequence, "event_type": event_type, "run_id": run.run_id, "writer": actor, **fields}
    if any("identity" in key.lower() for key in event):
        return failure("identity_field_forbidden", "event identity chains are not supported")
    path = run.evidence_path / f"{sequence:06d}-{event_type}.json"
    try:
        write_once(path, canonical_json(event))
    except FileExistsError:
        return failure("event_collision", "event sequence already exists")
    return ok({**event, "path": path})

def load_events(run: Run) -> RuntimeResult:
    events = []
    for path in sorted(run.evidence_path.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")):
        loaded = read_json(path)
        if not loaded.ok:
            return loaded
        events.append(loaded.value)
    return ok(events)
