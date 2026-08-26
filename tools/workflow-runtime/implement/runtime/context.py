"""Append implementation evidence through its state transitions."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import subprocess
import sys

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
import implementation_evidence

from runtime.storage import canonical_json, read_json, write_atomic, write_once
from runtime import tdd
from runtime.secret_detect import contains_secret
from runtime.staging import assess_paths
from runtime.types import COMMIT_SHA, Run, RuntimeResult, failure, ok

EVENT_TYPES = {
    "worktree-bound", "red", "green", "refactor", "check", "artifact", "external",
    "commit", "human_gate", "delegated", "returned", "resumed", "rebound", "recovering",
    "stopped", "implementation_green",
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
            elif not str(fields.get("summary", "")).strip() or not isinstance(fields.get("condition_met"), bool):
                return failure("stage_invalid", "external evidence needs a bounded summary and explicit condition result")
        elif event_type == "commit":
            if COMMIT_SHA.fullmatch(str(fields.get("commit", ""))) is None:
                return failure("commit_invalid", "commit evidence needs a full Git SHA")
            required = "refactor" if completion == "test" else completion
            if not prior or prior[-1].get("event_type") != required:
                return failure("transition_invalid", "commit needs completed step evidence")
    return ok()

def _status(binding: dict, events: list[dict], event: dict) -> dict:
    derived = implementation_evidence.derive_implementation(binding, events + [event])
    completed = derived.value["completed_steps"] if derived.ok else []
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
        event = {"version": 2, "sequence": sequence, "event_type": event_type, "run_id": run.run_id, "writer": actor, **fields}
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
    prepared = dict(fields)
    if event_type in {"red", "green", "refactor", "check", "artifact", "external"}:
        binding = read_json(run.binding_path)
        if not binding.ok:
            return binding
        if binding.value.get("worktree"):
            staged = _staged_paths(_worktree(binding.value, run))
            if not staged.ok:
                return staged
            assessed = _safety(binding.value, staged.value, prepared.get("unplanned_reasons"))
            if not assessed.ok:
                return assessed
            content = _content_safety(_worktree(binding.value, run), staged.value, index=True)
            if not content.ok:
                return content
            prepared["changed_paths"] = assessed.value["paths"]
            prepared["safety"] = assessed.value
        else:
            prepared["changed_paths"] = []
            prepared["safety"] = {"paths": [], "unplanned": []}
    return _append_event(run, event_type, prepared, actor=actor)

def record_stage(
    run: Run, step: str, phase: str, *, command: str, exit_code: int,
    test_paths: list[str] | None = None,
) -> RuntimeResult:
    binding = read_json(run.binding_path)
    events = load_events(run)
    if not binding.ok or not events.ok:
        return binding if not binding.ok else events
    worktree = _worktree(binding.value, run)
    if phase == "red":
        paths = sorted(set(test_paths or []))
        if not paths:
            return failure("frozen_red_unavailable", "RED needs test and fixture paths")
        current = _test_bytes(worktree, paths)
        if not current.ok:
            return current
        snapshot = tdd.freeze_test(current.value, command=command)
    else:
        red = next((event for event in reversed(events.value) if event.get("step") == step and event.get("event_type") == "red"), None)
        if red is None:
            return failure("transition_invalid", f"{phase.upper()} needs a prior RED")
        current = _test_bytes(worktree, list(red["snapshot"]["files"]))
        if not current.ok:
            return current
        snapshot = tdd.freeze_test(current.value, command=command)
        if snapshot != red["snapshot"]:
            return failure("frozen_red_mismatch", "test, fixture, or command differs from the accepted RED")
    return append_event(run, phase, {
        "step": step, "command": command, "exit_code": exit_code, "snapshot": snapshot,
    })

def record_commit(
    run: Run, step: str, commit: str, *, recorded_late: bool = False,
    unplanned_reasons: dict[str, str] | None = None,
) -> RuntimeResult:
    binding = read_json(run.binding_path)
    if not binding.ok:
        return binding
    if binding.value.get("worktree"):
        worktree = _worktree(binding.value, run)
        events = load_events(run)
        if not events.ok:
            return events
        if any(event.get("event_type") == "commit" and event.get("commit") == commit for event in events.value):
            return failure("commit_already_recorded", "one implementation commit can belong to only one step")
        ancestry = _validate_commit_ancestry(worktree, binding.value, commit)
        if not ancestry.ok:
            return ancestry
        paths = _commit_paths(worktree, commit)
        if not paths.ok:
            return paths
        assessed = _safety(binding.value, paths.value, unplanned_reasons)
        if not assessed.ok:
            return assessed
        content = _content_safety(worktree, paths.value, commit=commit)
        if not content.ok:
            return content
        safety = assessed.value
    else:
        safety = {"paths": [], "unplanned": []}
    return append_event(run, "commit", {
        "step": step, "commit": commit, "recorded_late": recorded_late, "safety": safety,
    })

def stop_run(run: Run, reason: str) -> RuntimeResult:
    return append_event(run, "stopped", {"reason": reason})

def rebound_run(run: Run, approval_commit: str, reason: str) -> RuntimeResult:
    return append_event(run, "rebound", {"approval_commit": approval_commit, "reason": reason})

def _git(worktree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(worktree), *args], text=True, capture_output=True, check=False)

def _git_bytes(worktree: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(worktree), *args], capture_output=True, check=False)

def _worktree(binding: dict, run: Run) -> Path:
    return Path(binding.get("worktree") or run.root)

def _staged_paths(worktree: Path) -> RuntimeResult:
    result = _git(worktree, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if result.returncode != 0:
        return failure("git_inspection_failed", "staged paths could not be inspected")
    return ok(sorted(filter(None, result.stdout.splitlines())))

def _commit_paths(worktree: Path, commit: str) -> RuntimeResult:
    if _git(worktree, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return failure("commit_invalid", "commit evidence names a missing Git commit")
    result = _git(worktree, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit)
    if result.returncode != 0:
        return failure("git_inspection_failed", "commit paths could not be inspected")
    return ok(sorted(filter(None, result.stdout.splitlines())))

def _commits_after(worktree: Path, approval_commit: str) -> RuntimeResult:
    result = _git(worktree, "rev-list", "--reverse", f"{approval_commit}..HEAD")
    if result.returncode != 0:
        return failure("git_inspection_failed", "implementation commit range could not be inspected")
    return ok(list(filter(None, result.stdout.splitlines())))

def _validate_commit_ancestry(worktree: Path, binding: dict, commit: str) -> RuntimeResult:
    if commit == binding["approval_commit"] or _git(
        worktree, "merge-base", "--is-ancestor", binding["approval_commit"], commit,
    ).returncode != 0:
        return failure("commit_before_approval", "implementation commit must follow the approval commit")
    branch_head = _git(worktree, "rev-parse", "--verify", f"refs/heads/{binding['branch']}^{{commit}}")
    if branch_head.returncode != 0 or _git(
        worktree, "merge-base", "--is-ancestor", commit, branch_head.stdout.strip(),
    ).returncode != 0:
        return failure("commit_not_on_branch", "implementation commit must be an ancestor of the bound branch tip")
    return ok()

def _content_safety(
    worktree: Path, paths: list[str], *, index: bool = False, commit: str | None = None,
) -> RuntimeResult:
    for path in paths:
        reference = f":{path}" if index else f"{commit}:{path}"
        content = _git_bytes(worktree, "show", reference)
        if content.returncode != 0:
            return failure("git_inspection_failed", "changed file content could not be inspected", path)
        if contains_secret(content.stdout):
            return failure("secret_content", "secret-shaped content is not allowed", path)
    return ok()

def _safety(binding: dict, paths: list[str], reasons: dict[str, str] | None = None) -> RuntimeResult:
    assessed = assess_paths(paths, expected_paths=binding.get("expected_paths", []), reasons=reasons or {})
    if not assessed.ok:
        return assessed
    return ok({"paths": assessed.value["paths"], "unplanned": assessed.value["unplanned"]})

def _test_bytes(worktree: Path, paths: list[str]) -> RuntimeResult:
    values: dict[str, bytes] = {}
    for relative in paths:
        target = worktree / relative
        if target.is_symlink() or not target.is_file():
            return failure("frozen_red_unavailable", f"test or fixture is unavailable: {relative}")
        values[relative] = target.read_bytes()
    return ok(values)

def complete_run(run: Run) -> RuntimeResult:
    binding = read_json(run.binding_path)
    events = load_events(run)
    if not binding.ok or not events.ok:
        return binding if not binding.ok else events
    if not events.value or events.value[0].get("event_type") != "worktree-bound":
        return failure("completion_invalid", "worktree binding evidence is missing")
    derived = implementation_evidence.derive_implementation(binding.value, events.value)
    if not derived.ok:
        return failure(derived.error.code, derived.error.message)
    if derived.value["resume_step"] is not None:
        return failure("completion_invalid", f"step is incomplete: {derived.value['resume_step']}")
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
    history = _commits_after(worktree, binding.value["approval_commit"])
    if not history.ok:
        return history
    recorded_list = [event["commit"] for event in events.value if event.get("event_type") == "commit"]
    if len(recorded_list) != len(set(recorded_list)):
        return failure("commit_assignment_invalid", "one implementation commit is assigned more than once")
    if set(history.value) != set(recorded_list):
        return failure("commit_bijection_invalid", "implementation history and commit evidence differ")
    return _append_event(
        run, "implementation_green",
        {"completed_steps": derived.value["completed_steps"]}, derived=True,
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
