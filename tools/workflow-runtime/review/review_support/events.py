"""Append-only review event storage and validation."""
from __future__ import annotations

import json
from pathlib import Path

import review_model
from review_support.repository import review_directory, write_once
from review_support.types import JsonObject, RuntimeResult, failure, object_values, ok
from review_support.validation import safe_finding_strings


def current_findings(events: list[JsonObject]) -> list[JsonObject]:
    """Reduce events to their current finding set."""

    reduced = review_model.reduce_review(events)
    if not reduced.ok or reduced.value is None:
        return []
    return object_values(reduced.value.get("findings")) or []


def findings_stale(events: list[JsonObject]) -> bool:
    """Return whether the most recent stale marker remains active."""

    active = False
    for event in events:
        if event.get("event_type") == "findings_stale":
            active = True
        elif event.get("event_type") == "findings-rebound":
            active = False
    return active


def _event_file_error(path: Path, expected: int, event: JsonObject) -> RuntimeResult[object] | None:
    if event.get("version") == 1:
        return failure("legacy_evidence_unsupported", "version 1 review evidence is unsupported")
    if event.get("version") != 2:
        return failure("review_event_invalid", "review event version must be 2")
    name = f"{expected:06d}-{event.get('event_type')}"
    if event.get("sequence") != expected or not path.name.startswith(name):
        return failure("review_event_invalid", "review event sequence is invalid")
    return None


def _validate_finding_references(
    root: Path,
    binding: JsonObject,
    events: list[JsonObject],
) -> RuntimeResult[None]:
    from review_support.findings import validate_finding_for_binding

    active_spec_commit = str(binding.get("spec_commit") or binding.get("approval_commit") or "")
    for event in events:
        findings = (object_values(event.get("findings")) or []) + (
            object_values(event.get("terminal_observations")) or []
        )
        for item in findings:
            checked = validate_finding_for_binding(
                root,
                binding,
                item,
                spec_commit=active_spec_commit,
            )
            if not checked.ok:
                return RuntimeResult(None, checked.error)
        if event.get("event_type") == "findings-rebound":
            active_spec_commit = str(event.get("spec_commit", ""))
    return ok()


def _read_event(path: Path, expected: int) -> RuntimeResult[JsonObject]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
        event = decoded if isinstance(decoded, dict) else None
    except (OSError, json.JSONDecodeError):
        event = None
    if event is None or not all(isinstance(key, str) for key in event):
        return RuntimeResult(None, failure("review_event_invalid", f"invalid review event: {path.name}").error)
    normalized = {str(key): item for key, item in event.items()}
    invalid = _event_file_error(path, expected, normalized)
    if invalid is not None:
        return RuntimeResult(None, invalid.error)
    safe_event = safe_finding_strings(normalized, field="event")
    if not safe_event.ok:
        return RuntimeResult(None, safe_event.error)
    return ok(normalized)


def _validate_loaded_events(
    root: Path,
    binding: JsonObject,
    events: list[JsonObject],
) -> RuntimeResult[list[JsonObject]]:
    reduced = review_model.reduce_review(events)
    if not reduced.ok:
        assert reduced.error is not None
        return RuntimeResult(None, failure(reduced.error.code, reduced.error.message).error)
    checked = _validate_finding_references(root, binding, events)
    if not checked.ok:
        return RuntimeResult(None, checked.error)
    return ok(events)


def load_events(root: Path, binding: JsonObject) -> RuntimeResult[list[JsonObject]]:
    """Load contiguous, valid review events."""

    try:
        directory = review_directory(root, binding)
    except ValueError:
        return RuntimeResult(None, failure("review_binding_invalid", "review directory is invalid").error)
    paths = sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")) if directory.is_dir() else []
    events: list[JsonObject] = []
    for expected, path in enumerate(paths, 1):
        loaded = _read_event(path, expected)
        if not loaded.ok:
            return RuntimeResult(None, loaded.error)
        events.append(loaded.required())
    return _validate_loaded_events(root, binding, events)


def _appendability(
    events: list[JsonObject],
    event_type: str,
    fields: JsonObject,
) -> RuntimeResult[None]:
    if findings_stale(events) and event_type != "findings-rebound":
        return RuntimeResult(None, failure("findings_stale", "stale findings allow only a human-approved rebound").error)
    if review_model.review_complete(events, current_findings(events)):
        return RuntimeResult(None, failure("review_already_completed", "completed review cannot be extended").error)
    safe_fields = safe_finding_strings(fields, field="event")
    if not safe_fields.ok:
        return RuntimeResult(None, safe_fields.error)
    return ok()


def append_event(
    root: Path,
    binding: JsonObject,
    event_type: str,
    fields: JsonObject,
) -> RuntimeResult[JsonObject]:
    """Append one canonical event after validating current state."""

    try:
        directory = review_directory(root, binding)
    except ValueError:
        return RuntimeResult(None, failure("review_binding_invalid", "review directory is invalid").error)
    loaded = load_events(root, binding)
    if not loaded.ok:
        return RuntimeResult(None, loaded.error)
    events = loaded.required()
    appendable = _appendability(events, event_type, fields)
    if not appendable.ok:
        return RuntimeResult(None, appendable.error)
    sequence = len(events) + 1
    event: JsonObject = {"version": 2, "sequence": sequence, "event_type": event_type, **fields}
    if any("identity" in key.lower() for key in event):
        return RuntimeResult(None, failure("identity_field_forbidden", "review identity chains are not supported").error)
    try:
        write_once(directory / f"{sequence:06d}-{event_type}.json", event)
    except FileExistsError:
        return RuntimeResult(None, failure("event_collision", "review event sequence already exists").error)
    return ok(event)
