"""Append implementation evidence through its state transitions."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import subprocess

from runtime.storage import canonical_json, read_json, write_atomic, write_once
from runtime.types import COMMIT_SHA, Run, RuntimeResult, failure, ok

EVENT_TYPES = {
    "worktree-bound", "red", "green", "refactor", "check", "artifact", "external",
    "commit", "human_gate", "delegated", "returned", "resumed", "rebound", "recovering",
    "stopped", "safety-check", "implementation_green",
}

def document_context(binding: dict, current_commit: str, changed_documents: list[str]) -> RuntimeResult:
    return ok({
        "approval_commit": binding["approval_commit"],
        "current_commit": current_commit,
        "changed_documents": sorted(changed_documents),
    })

def document_decision(
    *, current_commit: str, changed_documents: list[str], important: bool, reason: str,
) -> RuntimeResult:
    if not reason.strip():
        return failure("document_decision_reason_missing", "document meaning decision needs a reason")
    if important:
        return failure("rebound_or_new_run_required", reason, ", ".join(sorted(changed_documents)))
    return ok({
        "event_type": "documents-followed", "current_commit": current_commit,
        "changed_documents": sorted(changed_documents), "reason": reason,
    })

def stop_event(reason: str, *, changed_documents: list[str] | None = None) -> dict:
    return {"event_type": "stopped", "reason": reason, "changed_documents": sorted(changed_documents or [])}

def _step_contract(binding: dict, step_id: str) -> dict | None:
    return next((step for step in binding.get("steps", []) if step.get("id") == step_id), None)

def _events_for_step(events: list[dict], step_id: str) -> list[dict]:
    return [event for event in events if event.get("step") == step_id]

def _validate_event(binding: dict, events: list[dict], event_type: str, fields: dict, actor: str, derived: bool) -> RuntimeResult:
    if event_type not in EVENT_TYPES:
        return failure("event_type_invalid", f"unsupported implementation event: {event_type}")
    if events and events[-1].get("event_type") == "implementation_green":
        return failure("run_already_complete", "completed implementation evidence cannot be extended")
    if events and events[-1].get("event_type") == "stopped" and event_type not in {"resumed", "rebound"}:
        return failure("run_stopped", "stopped implementation must be resumed or rebound before more work")
    active_delegation = False
    for existing in events:
        if existing.get("event_type") == "delegated":
            active_delegation = True
        elif existing.get("event_type") == "returned":
            active_delegation = False
    if actor == "cycle":
        allowed = binding.get("delegated") and (
            (event_type == "worktree-bound" and not events)
            or (event_type == "delegated" and not active_delegation)
            or (event_type == "returned" and active_delegation)
        )
        if not allowed:
            return failure("writer_not_allowed", "cycle writes only delegated and returned boundaries")
    elif actor != "implement":
        return failure("writer_not_allowed", "unknown evidence writer")
    elif event_type in {"delegated", "returned"}:
        return failure("writer_not_allowed", "cycle is the only writer of delegation boundaries")
    elif binding.get("delegated") and not active_delegation:
        return failure("writer_not_allowed", "implement writes delegated evidence only during active delegation")
    if event_type == "implementation_green" and not derived:
        return failure("event_not_recordable", "implementation_green is derived by complete_run")
    if event_type == "worktree-bound":
        if events or fields.get("branch") != binding.get("branch") or fields.get("worktree") != binding.get("worktree"):
            return failure("worktree_binding_invalid", "worktree-bound must be the first event and match binding")
    if event_type in {"recovering", "stopped", "rebound"} and not str(fields.get("reason", "")).strip():
        return failure("event_field_missing", f"{event_type} needs a reason")
    if event_type == "rebound" and COMMIT_SHA.fullmatch(str(fields.get("approval_commit", ""))) is None:
        return failure("event_field_invalid", "rebound needs an approval commit")
    if event_type in {"red", "green", "refactor", "check", "artifact", "external", "commit"}:
        step_id = fields.get("step")
        contract = _step_contract(binding, step_id)
        if contract is None:
            return failure("step_unknown", "event step is not declared by the run")
        prior = _events_for_step(events, step_id)
        completion = contract["completion"]
        if event_type in {"red", "green", "refactor"}:
            if completion != "test" or not str(fields.get("command", "")).strip():
                return failure("stage_invalid", "test stages need a declared test step and command")
            exit_code = fields.get("exit_code")
            if not isinstance(exit_code, int):
                return failure("stage_invalid", "test stage needs an integer exit code")
            if event_type == "red" and exit_code == 0:
                return failure("stage_invalid", "RED must fail")
            last_test_stage = next((e["event_type"] for e in reversed(prior) if e["event_type"] in {"red", "green", "refactor"}), None)
            if event_type == "green" and (exit_code != 0 or last_test_stage != "red"):
                return failure("transition_invalid", "GREEN needs a prior RED and a passing command")
            if event_type == "refactor" and (exit_code != 0 or last_test_stage != "green"):
                return failure("transition_invalid", "REFACTOR needs a prior GREEN and a passing command")
        elif event_type in {"check", "artifact", "external"}:
            if event_type != completion:
                return failure("stage_invalid", "evidence kind does not match step completion")
            if event_type in {"check", "artifact"}:
                checks = fields.get("checks")
                if not isinstance(checks, list) or not checks or any(check.get("exit_code") != 0 for check in checks):
                    return failure("stage_invalid", "check evidence needs successful commands")
            elif not str(fields.get("summary", "")).strip():
                return failure("stage_invalid", "external evidence needs a bounded summary")
        elif event_type == "commit":
            if COMMIT_SHA.fullmatch(str(fields.get("commit", ""))) is None:
                return failure("commit_invalid", "commit evidence needs a full Git SHA")
            required = "refactor" if completion == "test" else completion
            if not prior or prior[-1].get("event_type") != required:
                return failure("transition_invalid", "commit needs completed step evidence")
    if event_type == "safety-check" and (fields.get("passed") is not True or not str(fields.get("summary", "")).strip()):
        return failure("safety_check_invalid", "safety check needs a passing bounded summary")
    return ok()

def _status(binding: dict, events: list[dict], event: dict) -> dict:
    completed = sorted({existing["step"] for existing in events + [event] if existing.get("event_type") == "commit"})
    reason = event.get("reason") or event.get("summary") or event.get("outcome")
    approval_commit = binding["approval_commit"]
    for existing in events + [event]:
        if existing.get("event_type") == "rebound":
            approval_commit = existing["approval_commit"]
    return {
        "plan": {"path": binding["plan_path"], "approval_commit": approval_commit},
        "completed_steps": completed,
        "last_event": {"event_type": event["event_type"], "reason": reason},
        "worktree": {"branch": binding.get("branch"), "path": binding.get("worktree")},
    }

@contextmanager
def _event_lock(run: Run):
    descriptor = os.open(run.evidence_path / ".events.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

def _append_event(
    run: Run, event_type: str, fields: dict, *, actor: str | None = None, derived: bool = False,
) -> RuntimeResult:
    binding = read_json(run.binding_path)
    if not binding.ok:
        return binding
    if actor is None:
        actor = "cycle" if event_type in {"delegated", "returned"} else "implement"
    with _event_lock(run):
        loaded = load_events(run)
        if not loaded.ok:
            return loaded
        checked = _validate_event(binding.value, loaded.value, event_type, fields, actor, derived)
        if not checked.ok:
            return checked
        sequence = len(loaded.value) + 1
        event = {"version": 1, "sequence": sequence, "event_type": event_type, "run_id": run.run_id, "writer": actor, **fields}
        if any("identity" in key.lower() for key in event):
            return failure("identity_field_forbidden", "event identity chains are not supported")
        path = run.evidence_path / f"{sequence:06d}-{event_type}.json"
        try:
            write_once(path, canonical_json(event))
            write_atomic(run.evidence_path / "current-status", canonical_json(_status(binding.value, loaded.value, event)))
        except (FileExistsError, OSError) as error:
            path.unlink(missing_ok=True)
            return failure("evidence_write_failed", "event and current status could not be recorded", str(error))
        return ok({**event, "path": path})

def append_event(run: Run, event_type: str, fields: dict, *, actor: str | None = None) -> RuntimeResult:
    return _append_event(run, event_type, fields, actor=actor)

def record_stage(run: Run, step: str, phase: str, *, command: str, exit_code: int) -> RuntimeResult:
    return append_event(run, phase, {"step": step, "command": command, "exit_code": exit_code})

def record_commit(run: Run, step: str, commit: str, *, recorded_late: bool = False) -> RuntimeResult:
    return append_event(run, "commit", {"step": step, "commit": commit, "recorded_late": recorded_late})

def record_safety_check(run: Run, *, passed: bool, summary: str) -> RuntimeResult:
    return append_event(run, "safety-check", {"passed": passed, "summary": summary})

def stop_run(run: Run, reason: str) -> RuntimeResult:
    return append_event(run, "stopped", {"reason": reason})

def rebound_run(run: Run, approval_commit: str, reason: str) -> RuntimeResult:
    return append_event(run, "rebound", {"approval_commit": approval_commit, "reason": reason})

def _git(worktree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(worktree), *args], text=True, capture_output=True, check=False)

def complete_run(run: Run) -> RuntimeResult:
    binding = read_json(run.binding_path)
    events = load_events(run)
    if not binding.ok or not events.ok:
        return binding if not binding.ok else events
    if not events.value or events.value[0].get("event_type") != "worktree-bound":
        return failure("completion_invalid", "worktree binding evidence is missing")
    if not binding.value.get("steps"):
        return failure("completion_invalid", "implementation run has no declared steps")
    for step in binding.value.get("steps", []):
        step_events = _events_for_step(events.value, step["id"])
        required = "refactor" if step["completion"] == "test" else step["completion"]
        if not any(event.get("event_type") == required for event in step_events) or not any(
            event.get("event_type") == "commit" for event in step_events
        ):
            return failure("completion_invalid", f"step is incomplete: {step['id']}")
    if not any(event.get("event_type") == "safety-check" and event.get("passed") is True for event in events.value):
        return failure("completion_invalid", "passing safety evidence is missing")
    if events.value[-1].get("event_type") == "stopped":
        return failure("completion_invalid", "stopped run must be resumed or rebound")
    worktree = Path(binding.value.get("worktree") or "")
    branch = binding.value.get("branch")
    if not worktree.is_dir() or _git(worktree, "status", "--porcelain").stdout.strip():
        return failure("worktree_dirty", "implementation worktree must be clean")
    current_branch = _git(worktree, "branch", "--show-current")
    if current_branch.returncode != 0 or current_branch.stdout.strip() != branch:
        return failure("worktree_binding_invalid", "worktree branch differs from the run binding")
    for event in events.value:
        if event.get("event_type") == "commit" and _git(worktree, "cat-file", "-e", f"{event['commit']}^{{commit}}").returncode != 0:
            return failure("commit_invalid", f"recorded commit does not exist: {event['commit']}")
    return _append_event(
        run, "implementation_green",
        {"completed_steps": [step["id"] for step in binding.value.get("steps", [])]}, derived=True,
    )

def load_events(run: Run) -> RuntimeResult:
    events: list[dict] = []
    for expected, path in enumerate(sorted(run.evidence_path.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")), 1):
        loaded = read_json(path)
        if not loaded.ok:
            return loaded
        if loaded.value.get("sequence") != expected or not path.name.startswith(f"{expected:06d}-"):
            return failure("evidence_sequence_invalid", f"invalid event sequence: {path.name}")
        events.append(loaded.value)
    return ok(events)
