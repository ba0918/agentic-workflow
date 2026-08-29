"""Compose implementation evidence storage and pure transition rules."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
from typing import NamedTuple

from runtime import gates, tdd
from runtime.completion import completion_fields, validate_commit_ancestry
from runtime.documents import (
    document_context as _document_context,
    document_decision as _document_decision,
    plan_scope_unchanged,
    stop_event as _stop_event,
    validate_document_commit,
)
from runtime.events import EventCandidate, derive_implementation, validate_event
from runtime.gitio import commit_paths, run_git, staged_paths
from runtime.safety import assess_safety, test_bytes, worktree
from runtime.storage import canonical_json, read_json, write_atomic, write_once
from runtime.types import (
    JsonObject, Run, RuntimeResult, failure, forward_failure, object_value, ok, string_values,
)


class StageObservation(NamedTuple):
    command: str
    exit_code: int
    test_paths: list[str] | None = None


class _HumanGateContext(NamedTuple):
    source_binding: JsonObject
    active_binding: JsonObject
    events: list[JsonObject]
    gate: JsonObject


def _reason_mapping(value: object) -> Mapping[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        return None
    return {str(key): item for key, item in value.items() if isinstance(item, str)}


def document_context(
    binding: JsonObject, current_commit: str, changed_documents: list[str],
) -> RuntimeResult[JsonObject]:
    return _document_context(binding, current_commit, changed_documents)


def document_decision(
    *, current_commit: str, changed_documents: list[str], important: bool, reason: str,
) -> RuntimeResult[JsonObject]:
    return _document_decision(
        current_commit=current_commit,
        changed_documents=changed_documents,
        important=important,
        reason=reason,
    )


def stop_event(
    reason: str, *, changed_documents: list[str] | None = None,
) -> JsonObject:
    return _stop_event(reason, changed_documents=changed_documents)


def _status(binding: JsonObject, event_values: list[JsonObject], event: JsonObject) -> JsonObject:
    derived = derive_implementation(binding, [*event_values, event])
    completed: list[str] = []
    approval_commit = binding.get("approval_commit")
    if derived.ok:
        value = derived.required()
        completed = string_values(value.get("completed_steps")) or []
        approval_commit = value.get("approval_commit", approval_commit)
    reason = event.get("reason") or event.get("summary") or event.get("outcome")
    return {
        "plan": {"path": binding.get("plan_path"), "approval_commit": approval_commit},
        "completed_steps": completed,
        "last_event": {
            "event_type": event["event_type"],
            "reason": reason,
            **{name: event[name] for name in ("role", "model") if name in event},
        },
        "worktree": {"branch": binding.get("branch"), "path": binding.get("worktree")},
    }


@contextmanager
def _event_lock(run: Run) -> Iterator[None]:
    descriptor = os.open(run.evidence_path / ".events.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "rb", closefd=True) as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _overlay_derived(binding: JsonObject, derived: JsonObject) -> JsonObject:
    """Binding as it currently applies: rebound-aware steps, approval commit and scope."""
    return {
        **binding,
        "steps": derived.get("steps"),
        "approval_commit": derived.get("approval_commit"),
        "expected_paths": derived.get("expected_paths"),
    }


def _effective_binding(
    binding: JsonObject, event_values: list[JsonObject],
) -> RuntimeResult[JsonObject]:
    derived = derive_implementation(binding, event_values)
    if not event_values and not derived.ok:
        return ok(binding)
    if not derived.ok:
        return forward_failure(
            derived.error, "implementation_evidence_invalid", "implementation evidence is invalid"
        )
    return ok(_overlay_derived(binding, derived.required()))


def _store_event(
    run: Run,
    binding: JsonObject,
    event_values: list[JsonObject],
    event_candidate: EventCandidate,
) -> RuntimeResult[JsonObject]:
    checked = validate_event(binding, event_values, event_candidate)
    if not checked.ok:
        return forward_failure(checked.error, "event_invalid", "implementation event is invalid")
    sequence = len(event_values) + 1
    event: JsonObject = {
        **event_candidate.fields,
        "version": 2,
        "sequence": sequence,
        "event_type": event_candidate.event_type,
        "run_id": run.run_id,
        "writer": event_candidate.actor,
    }
    if any("identity" in key.lower() for key in event):
        return failure(
            "identity_field_forbidden", "event identity chains are not supported"
        )
    path = run.evidence_path / f"{sequence:06d}-{event_candidate.event_type}.json"
    try:
        write_once(path, canonical_json(event))
        write_atomic(
            run.evidence_path / "current-status",
            canonical_json(_status(binding, event_values, event)),
        )
    except (FileExistsError, OSError) as error:
        path.unlink(missing_ok=True)
        return failure(
            "evidence_write_failed",
            "event and current status could not be recorded",
            str(error),
        )
    return ok({**event, "path": path})


def _append_event(
    run: Run,
    event_type: str,
    fields: JsonObject,
    *,
    actor: str | None = None,
    derived: bool = False,
) -> RuntimeResult[JsonObject]:
    binding_result = read_json(run.binding_path)
    if not binding_result.ok:
        return forward_failure(
            binding_result.error, "evidence_unavailable", "implementation binding is unavailable"
        )
    writer = actor or (
        "cycle" if event_type in {"delegated", "returned"} else "implement"
    )
    with _event_lock(run):
        loaded = load_events(run)
        if not loaded.ok:
            return forward_failure(
                loaded.error, "evidence_unavailable", "implementation events are unavailable"
            )
        return _store_event(
            run,
            binding_result.required(),
            loaded.required(),
            EventCandidate(event_type, fields, writer, derived),
        )


def _prepare_safety(
    run: Run, binding: JsonObject, prepared: JsonObject,
) -> RuntimeResult[JsonObject]:
    checkout = worktree(binding, run)
    paths = staged_paths(checkout)
    if not paths.ok:
        return forward_failure(paths.error, "git_inspection_failed", "staged paths are unavailable")
    assessed = assess_safety(
        binding, paths.required(), _reason_mapping(prepared.get("unplanned_reasons"))
    )
    if not assessed.ok:
        return forward_failure(assessed.error, "dangerous_path", "changed paths are unsafe")
    return ok(assessed.required())


def append_event(
    run: Run,
    event_type: str,
    fields: JsonObject,
    *,
    actor: str | None = None,
) -> RuntimeResult[JsonObject]:
    if event_type in {"commit", "implementation_green"}:
        return failure(
            "event_not_recordable",
            f"{event_type} is recorded only by its canonical operation",
        )
    prepared = dict(fields)
    if event_type in {"red", "green", "refactor", "check", "artifact", "external"}:
        binding = read_json(run.binding_path)
        if not binding.ok:
            return forward_failure(
                binding.error, "evidence_unavailable", "implementation binding is unavailable"
            )
        if binding.required().get("worktree"):
            loaded = load_events(run)
            if not loaded.ok:
                return forward_failure(
                    loaded.error, "evidence_unavailable", "implementation events are unavailable"
                )
            effective = _effective_commit_binding(binding.required(), loaded.required())
            if not effective.ok:
                return forward_failure(
                    effective.error, "implementation_evidence_invalid",
                    "implementation evidence is invalid",
                )
            active_binding = effective.required()
            assessed = _prepare_safety(run, active_binding, prepared)
            if not assessed.ok:
                return forward_failure(assessed.error, "dangerous_path", "changed paths are unsafe")
            prepared["changed_paths"] = assessed.required()["paths"]
            prepared["safety"] = assessed.required()
        else:
            prepared["changed_paths"] = []
            prepared["safety"] = {"paths": [], "unplanned": []}
    return _append_event(run, event_type, prepared, actor=actor)


def _snapshot_paths(snapshot: JsonObject) -> list[str] | None:
    files = snapshot.get("files")
    if not isinstance(files, dict) or not all(isinstance(path, str) for path in files):
        return None
    return sorted(str(path) for path in files)


def record_stage(
    run: Run,
    step: str,
    phase: str,
    observation: StageObservation,
) -> RuntimeResult[JsonObject]:
    binding = read_json(run.binding_path)
    loaded = load_events(run)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "events are unavailable")
    checkout = worktree(binding.required(), run)
    snapshot = _stage_snapshot(checkout, step, phase, loaded.required(), observation)
    if not snapshot.ok:
        return forward_failure(
            snapshot.error, "frozen_red_unavailable", "test evidence is unavailable"
        )
    return append_event(run, phase, {
        "step": step,
        "command": observation.command,
        "exit_code": observation.exit_code,
        "snapshot": snapshot.required(),
    })


def _stage_snapshot(
    checkout: Path,
    step: str,
    phase: str,
    event_values: list[JsonObject],
    observation: StageObservation,
) -> RuntimeResult[JsonObject]:
    prior_red: JsonObject | None = None
    if phase == "red":
        paths: list[str] = sorted(set(observation.test_paths or []))
        if not paths:
            return failure("frozen_red_unavailable", "RED needs test and fixture paths")
    else:
        prior_red = next(
            (
                event for event in reversed(event_values)
                if event.get("step") == step and event.get("event_type") == "red"
            ),
            None,
        )
        if prior_red is None:
            return failure("transition_invalid", f"{phase.upper()} needs a prior RED")
        prior_snapshot = object_value(prior_red.get("snapshot"))
        frozen_paths = _snapshot_paths(prior_snapshot) if prior_snapshot is not None else None
        if frozen_paths is None:
            return failure("frozen_red_unavailable", "RED snapshot is invalid")
        paths = frozen_paths
    current = test_bytes(checkout, paths)
    if not current.ok:
        return forward_failure(
            current.error, "frozen_red_unavailable", "test or fixture is unavailable"
        )
    snapshot = tdd.freeze_test(current.required(), command=observation.command)
    if phase != "red" and prior_red is not None:
        if snapshot != object_value(prior_red.get("snapshot")):
            return failure(
                "frozen_red_mismatch", "test, fixture, or command differs from the accepted RED"
            )
    return ok(snapshot)


def _effective_commit_binding(
    binding: JsonObject, event_values: list[JsonObject],
) -> RuntimeResult[JsonObject]:
    derived = derive_implementation(binding, event_values)
    if not derived.ok:
        return forward_failure(
            derived.error, "implementation_evidence_invalid", "implementation evidence is invalid"
        )
    return ok(_overlay_derived(binding, derived.required()))


def record_commit(
    run: Run,
    step: str,
    commit: str,
    *,
    recorded_late: bool = False,
    unplanned_reasons: Mapping[str, str] | None = None,
) -> RuntimeResult[JsonObject]:
    binding = read_json(run.binding_path)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    safety: JsonObject = {"paths": [], "unplanned": []}
    if binding.required().get("worktree"):
        prepared = _commit_safety(
            run, binding.required(), commit, unplanned_reasons
        )
        if not prepared.ok:
            return forward_failure(prepared.error, "commit_invalid", "commit could not be validated")
        safety = prepared.required()
    return _append_event(run, "commit", {
        "step": step,
        "commit": commit,
        "recorded_late": recorded_late,
        "safety": safety,
    })


def _commit_safety(
    run: Run,
    binding: JsonObject,
    commit: str,
    reasons: Mapping[str, str] | None,
) -> RuntimeResult[JsonObject]:
    loaded = load_events(run)
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "events are unavailable")
    effective = _effective_commit_binding(binding, loaded.required())
    if not effective.ok:
        return forward_failure(
            effective.error, "implementation_evidence_invalid", "implementation evidence is invalid"
        )
    if any(
        event.get("event_type") == "commit" and event.get("commit") == commit
        for event in loaded.required()
    ):
        return failure(
            "commit_already_recorded", "one implementation commit can belong to only one step"
        )
    return _commit_path_safety(
        worktree(binding, run), effective.required(), commit, reasons
    )


def _commit_path_safety(
    checkout: Path,
    binding: JsonObject,
    commit: str,
    reasons: Mapping[str, str] | None,
) -> RuntimeResult[JsonObject]:
    ancestry = validate_commit_ancestry(checkout, binding, commit)
    if not ancestry.ok:
        return forward_failure(ancestry.error, "commit_invalid", "commit ancestry is invalid")
    paths = commit_paths(checkout, commit)
    if not paths.ok:
        return forward_failure(paths.error, "commit_invalid", "commit paths are unavailable")
    assessed = assess_safety(binding, paths.required(), reasons)
    if not assessed.ok:
        return forward_failure(assessed.error, "dangerous_path", "commit paths are unsafe")
    return ok(assessed.required())


def stop_run(run: Run, reason: str) -> RuntimeResult[JsonObject]:
    return append_event(run, "stopped", {"reason": reason})


def record_human_gate(
    run: Run, step: str, gate_id: str, result: str,
) -> RuntimeResult[JsonObject]:
    context = _human_gate_context(run, step, gate_id, result)
    if not context.ok:
        return forward_failure(
            context.error, "implementation_evidence_invalid", "Human gate context is invalid",
        )
    source_binding, active_binding, event_values, declared = context.required()
    clean = _gate_target_clean(run, active_binding, declared)
    if not clean.ok:
        return forward_failure(clean.error, "human_gate_target_changed", "Human gate target changed")
    fields: JsonObject = {
        "step": step,
        "gate_id": gate_id,
        "result": result,
        "reason": f"declared Human gate recorded as {result}",
    }
    candidate: JsonObject = {
        "version": 2,
        "sequence": len(event_values) + 1,
        "event_type": "human_gate",
        **fields,
    }
    derived = derive_implementation(source_binding, [*event_values, candidate])
    if not derived.ok:
        return forward_failure(
            derived.error, "implementation_evidence_invalid", "Human gate evidence is invalid"
        )
    return _append_event(run, "human_gate", fields)


def _human_gate_context(
    run: Run, step: str, gate_id: str, result: str,
) -> RuntimeResult[_HumanGateContext]:
    binding = read_json(run.binding_path)
    loaded = load_events(run)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "events are unavailable")
    effective = _effective_binding(binding.required(), loaded.required())
    if not effective.ok:
        return forward_failure(
            effective.error, "implementation_evidence_invalid", "implementation evidence is invalid"
        )
    declared = gates.declared_gate(effective.required(), step, gate_id, result)
    if not declared.ok:
        return forward_failure(declared.error, "human_gate_unknown", "Human gate is unavailable")
    return ok(
        _HumanGateContext(
            binding.required(), effective.required(), loaded.required(), declared.required(),
        ),
    )


def _gate_target_clean(
    run: Run, binding: JsonObject, gate: JsonObject,
) -> RuntimeResult[None]:
    if gate.get("timing") != "before_edit":
        return ok(None)
    target = object_value(gate.get("target")) or {}
    paths = string_values(target.get("paths")) if target.get("kind") == "files" else None
    if not paths or not binding.get("worktree"):
        return ok(None)
    checkout = worktree(binding, run)
    status = run_git(
        checkout, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths,
    )
    if status.returncode != 0:
        return failure("git_inspection_failed", "Human gate target status is unavailable")
    if status.stdout:
        return failure(
            "human_gate_target_changed", "before_edit target is already modified", paths[0],
        )
    return ok(None)


def follow_documents(
    run: Run, current_commit: str, changed_documents: list[str], reason: str,
) -> RuntimeResult[JsonObject]:
    binding = read_json(run.binding_path)
    loaded = load_events(run)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "events are unavailable")
    checked = validate_document_commit(run, binding.required(), current_commit)
    if not checked.ok:
        return forward_failure(
            checked.error, "document_commit_invalid", "document commit is invalid"
        )
    effective = _effective_binding(binding.required(), loaded.required())
    if not effective.ok:
        return forward_failure(
            effective.error, "implementation_evidence_invalid", "implementation evidence is invalid",
        )
    unchanged = plan_scope_unchanged(
        run, effective.required(), checked.required().scope,
    )
    if not unchanged.ok:
        return forward_failure(
            unchanged.error, "rebound_or_new_run_required", "plan Scope changed after approval",
        )
    return append_event(run, "recovering", {
        "current_commit": current_commit,
        "changed_documents": sorted(changed_documents),
        "reason": reason,
    })


def rebound_run(
    run: Run,
    approval_commit: str,
    reason: str,
    *,
    mappings: list[JsonObject],
) -> RuntimeResult[JsonObject]:
    binding = read_json(run.binding_path)
    loaded = load_events(run)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "events are unavailable")
    checked = validate_document_commit(run, binding.required(), approval_commit)
    if not checked.ok:
        return forward_failure(
            checked.error, "document_commit_invalid", "document commit is invalid"
        )
    steps: list[JsonObject] = [
        {
            "id": step.id,
            "completion": step.completion,
            "checks": list(step.checks),
            "human_gates": list(step.human_gates),
        }
        for step in checked.required().header.steps
    ]
    fields: JsonObject = {
        "approval_commit": approval_commit,
        "expected_paths": list(checked.required().scope),
        "steps": steps,
        "mappings": mappings,
        "reason": reason,
    }
    rebound_candidate: JsonObject = {
        "version": 2,
        "sequence": len(loaded.required()) + 1,
        "event_type": "rebound",
        **fields,
    }
    derived = derive_implementation(binding.required(), [*loaded.required(), rebound_candidate])
    if not derived.ok:
        return forward_failure(
            derived.error, "implementation_evidence_invalid", "rebound evidence is invalid"
        )
    return append_event(run, "rebound", fields)


def complete_run(run: Run) -> RuntimeResult[JsonObject]:
    binding = read_json(run.binding_path)
    loaded = load_events(run)
    if not binding.ok:
        return forward_failure(binding.error, "evidence_unavailable", "binding is unavailable")
    if not loaded.ok:
        return forward_failure(loaded.error, "evidence_unavailable", "events are unavailable")
    fields = completion_fields(binding.required(), loaded.required())
    if not fields.ok:
        return forward_failure(fields.error, "completion_invalid", "implementation cannot complete")
    return _append_event(run, "implementation_green", fields.required(), derived=True)


def load_events(run: Run) -> RuntimeResult[list[JsonObject]]:
    event_values: list[JsonObject] = []
    paths = sorted(
        run.evidence_path.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")
    )
    for expected, path in enumerate(paths, 1):
        loaded = read_json(path)
        if not loaded.ok:
            return forward_failure(
                loaded.error, "evidence_invalid", "implementation event is invalid"
            )
        event = loaded.required()
        if event.get("sequence") != expected or not path.name.startswith(f"{expected:06d}-"):
            return failure(
                "evidence_sequence_invalid", f"invalid event sequence: {path.name}"
            )
        if event.get("version") == 1:
            return failure(
                "legacy_evidence_unsupported", "version 1 implementation evidence is unsupported"
            )
        if event.get("version") != 2:
            return failure(
                "evidence_sequence_invalid", f"invalid event version: {path.name}"
            )
        event_values.append(event)
    return ok(event_values)
