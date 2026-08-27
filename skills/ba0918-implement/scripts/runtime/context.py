"""Append implementation evidence through its state transitions."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import subprocess
import sys

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
import implementation_evidence

from runtime.storage import canonical_json, read_json, write_atomic, write_once
from runtime import tdd
from runtime.deps import plan_artifact
from runtime.secret_detect import contains_secret
from runtime.staging import assess_paths
from runtime.types import COMMIT_SHA, Run, RuntimeResult, failure, ok

EVENT_TYPES = {
    "worktree-bound", "red", "green", "refactor", "check", "artifact", "external",
    "commit", "human_gate", "delegated", "returned", "resumed", "rebound", "recovering",
    "resume-candidate-retired", "stopped", "implementation_green",
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
        "event_type": "recovering", "current_commit": current_commit,
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
    implementation_complete = any(event.get("event_type") == "implementation_green" for event in events)
    returning_completed_delegation = (
        implementation_complete and events[-1].get("event_type") == "implementation_green"
        and event_type == "returned" and actor == "cycle"
    )
    if implementation_complete and not returning_completed_delegation:
        return failure("run_already_complete", "completed implementation evidence cannot be extended")
    if events and events[-1].get("event_type") == "stopped" and event_type not in {"resumed", "rebound", "resume-candidate-retired"}:
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
    if event_type == "recovering" and "current_commit" in fields and (
        COMMIT_SHA.fullmatch(str(fields.get("current_commit", ""))) is None
        or not fields.get("changed_documents")
    ):
        return failure("event_field_invalid", "document recovery needs a commit and changed documents")
    if event_type == "rebound" and (
        _steps_value(fields.get("steps")) is None or not isinstance(fields.get("mappings"), list)
    ):
        return failure("event_field_invalid", "rebound needs new steps and mappings")
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
                if (
                    not isinstance(checks, list) or (event_type == "check" and not checks)
                    or any(not isinstance(check, dict) or check.get("exit_code") != 0 for check in checks)
                ):
                    return failure("stage_invalid", "check evidence needs successful commands")
            elif not str(fields.get("summary", "")).strip() or not isinstance(fields.get("condition_met"), bool):
                return failure("stage_invalid", "external evidence needs a bounded summary and explicit condition result")
        elif event_type == "commit":
            if COMMIT_SHA.fullmatch(str(fields.get("commit", ""))) is None:
                return failure("commit_invalid", "commit evidence needs a full Git SHA")
            safety = fields.get("safety")
            if (
                not isinstance(safety, dict) or not isinstance(safety.get("paths"), list)
                or not all(isinstance(path, str) and path for path in safety["paths"])
                or not isinstance(safety.get("unplanned"), list)
            ):
                return failure("commit_invalid", "commit evidence needs canonical safety results")
            required = "refactor" if completion == "test" else completion
            if not any(event.get("event_type") == required for event in prior):
                return failure("transition_invalid", "commit needs completed step evidence")
    if event_type == "resume-candidate-retired" and not str(fields.get("reason", "")).strip():
        return failure("event_field_missing", "logical run retirement needs a reason")
    return ok()

def _status(binding: dict, events: list[dict], event: dict) -> dict:
    derived = implementation_evidence.derive_implementation(binding, events + [event])
    completed = derived.value["completed_steps"] if derived.ok else []
    reason = event.get("reason") or event.get("summary") or event.get("outcome")
    approval_commit = derived.value["approval_commit"] if derived.ok else binding["approval_commit"]
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
        effective = implementation_evidence.derive_implementation(binding.value, loaded.value)
        if loaded.value and not effective.ok:
            return failure(effective.error.code, effective.error.message)
        effective_binding = binding.value if not effective.ok else {
            **binding.value, "steps": effective.value["steps"],
            "approval_commit": effective.value["approval_commit"],
        }
        checked = _validate_event(effective_binding, loaded.value, event_type, fields, actor, derived)
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
    if event_type in {"commit", "implementation_green"}:
        return failure("event_not_recordable", f"{event_type} is recorded only by its canonical operation")
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
        derived = implementation_evidence.derive_implementation(binding.value, events.value)
        if not derived.ok:
            return failure(derived.error.code, derived.error.message)
        effective_binding = {
            **binding.value, "steps": derived.value["steps"],
            "approval_commit": derived.value["approval_commit"],
        }
        if any(event.get("event_type") == "commit" and event.get("commit") == commit for event in events.value):
            return failure("commit_already_recorded", "one implementation commit can belong to only one step")
        ancestry = _validate_commit_ancestry(worktree, effective_binding, commit)
        if not ancestry.ok:
            return ancestry
        paths = _commit_paths(worktree, commit)
        if not paths.ok:
            return paths
        assessed = _safety(effective_binding, paths.value, unplanned_reasons)
        if not assessed.ok:
            return assessed
        content = _content_safety(worktree, paths.value, commit=commit)
        if not content.ok:
            return content
        safety = assessed.value
    else:
        safety = {"paths": [], "unplanned": []}
    return _append_event(run, "commit", {
        "step": step, "commit": commit, "recorded_late": recorded_late, "safety": safety,
    })

def stop_run(run: Run, reason: str) -> RuntimeResult:
    return append_event(run, "stopped", {"reason": reason})

def follow_documents(
    run: Run, current_commit: str, changed_documents: list[str], reason: str,
) -> RuntimeResult:
    binding = read_json(run.binding_path)
    if not binding.ok:
        return binding
    checked = _validate_document_commit(run, binding.value, current_commit)
    if not checked.ok:
        return checked
    return append_event(run, "recovering", {
        "current_commit": current_commit, "changed_documents": sorted(changed_documents), "reason": reason,
    })

def rebound_run(
    run: Run, approval_commit: str, reason: str, *, steps: list[dict], mappings: list[dict],
) -> RuntimeResult:
    binding = read_json(run.binding_path)
    events = load_events(run)
    if not binding.ok or not events.ok:
        return binding if not binding.ok else events
    checked = _validate_document_commit(run, binding.value, approval_commit)
    if not checked.ok:
        return checked
    candidate = {
        "version": 2, "sequence": len(events.value) + 1, "event_type": "rebound",
        "approval_commit": approval_commit, "steps": steps, "mappings": mappings, "reason": reason,
    }
    derived = implementation_evidence.derive_implementation(binding.value, events.value + [candidate])
    if not derived.ok:
        return failure(derived.error.code, derived.error.message)
    return append_event(run, "rebound", {
        "approval_commit": approval_commit, "steps": steps, "mappings": mappings, "reason": reason,
    })

def _steps_value(value: object) -> list[dict] | None:
    if not isinstance(value, list) or not value:
        return None
    return value if all(isinstance(step, dict) for step in value) else None

def _validate_document_commit(run: Run, binding: dict, commit: str) -> RuntimeResult:
    if COMMIT_SHA.fullmatch(commit) is None or _git(run.root, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return failure("document_commit_invalid", "document commit does not exist")
    plan = _git(run.root, "show", f"{commit}:{binding['plan_path']}")
    if plan.returncode != 0:
        return failure("document_commit_invalid", "plan is unavailable in the document commit")
    try:
        header = plan_artifact.read_plan_header(plan.stdout)
    except plan_artifact.PlanArtifactError:
        return failure("document_commit_invalid", "plan cannot be read from the document commit")
    for specification in header.specifications:
        content = _git(run.root, "show", f"{commit}:{specification.path}")
        if content.returncode != 0 or any(
            not re.search(rf"^#+\s+{re.escape(section)}\s*$", content.stdout, re.MULTILINE)
            for section in specification.sections
        ):
            return failure("document_commit_invalid", "target specification is unavailable in the document commit")
    return ok()

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

def _segment_commits(worktree: Path, segments: list[dict]) -> RuntimeResult:
    result = _git(worktree, "rev-list", "--reverse", f"{segments[0]['approval_commit']}..HEAD")
    if result.returncode != 0:
        return failure("git_inspection_failed", "implementation revision range could not be inspected")
    document_boundaries = {segment["approval_commit"] for segment in segments[1:]}
    history = [commit for commit in filter(None, result.stdout.splitlines()) if commit not in document_boundaries]
    commits = [commit for segment in segments for commit in segment["commits"]]
    if history != commits:
        return failure("commit_bijection_invalid", "implementation revision range and commit evidence differ")
    return ok(history)

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
    working_tree: bool = False,
) -> RuntimeResult:
    for path in paths:
        tracked = _git(worktree, "ls-files", "--error-unmatch", "--", path).returncode == 0
        if working_tree and not tracked:
            try:
                added = (worktree / path).read_bytes()
            except OSError:
                return failure("git_inspection_failed", "untracked content could not be inspected", path)
            if contains_secret(added):
                return failure("secret_content", "secret-shaped content is not allowed", path)
            continue
        if working_tree:
            content = _git_bytes(worktree, "diff", "--unified=0", "--", path)
        elif index:
            content = _git_bytes(worktree, "diff", "--cached", "--unified=0", "--", path)
        else:
            content = _git_bytes(worktree, "show", "--format=", "--unified=0", commit or "", "--", path)
        if content.returncode != 0:
            return failure("git_inspection_failed", "changed diff content could not be inspected", path)
        added = b"\n".join(
            line[1:] for line in content.stdout.splitlines()
            if line.startswith(b"+") and not line.startswith(b"+++")
        )
        if contains_secret(added):
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
    if not derived.value["steps"]:
        return failure("completion_invalid", "implementation has no step contracts")
    if derived.value["resume_step"] is not None:
        return failure("completion_invalid", f"step is incomplete: {derived.value['resume_step']}")
    if events.value[-1].get("event_type") == "stopped":
        return failure("completion_invalid", "stopped run must be resumed or rebound")
    worktree = Path(binding.value.get("worktree") or "")
    branch = binding.value.get("branch")
    if not worktree.is_dir():
        return failure("worktree_binding_invalid", "implementation worktree is unavailable")
    status = _git(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return failure("git_inspection_failed", "worktree status could not be inspected")
    dirty_paths = sorted({
        line[3:] for line in status.stdout.splitlines()
        if len(line) >= 4 and not line[3:].startswith(".agents/")
    })
    planned_dirty = sorted(set(dirty_paths) & set(binding.value.get("expected_paths", [])))
    if planned_dirty:
        return failure("planned_changes_uncommitted", "planned paths still have uncommitted changes", planned_dirty[0])
    outside_dirty = sorted(set(dirty_paths) - set(binding.value.get("expected_paths", [])))
    outside_safety = assess_paths(outside_dirty, expected_paths=outside_dirty)
    if not outside_safety.ok:
        return outside_safety
    outside_content = _content_safety(worktree, outside_dirty, working_tree=True)
    if not outside_content.ok:
        return outside_content
    current_branch = _git(worktree, "branch", "--show-current")
    if current_branch.returncode != 0 or current_branch.stdout.strip() != branch:
        return failure("worktree_binding_invalid", "worktree branch differs from the run binding")
    for event in events.value:
        if event.get("event_type") == "commit" and _git(worktree, "cat-file", "-e", f"{event['commit']}^{{commit}}").returncode != 0:
            return failure("commit_invalid", f"recorded commit does not exist: {event['commit']}")
    history = _segment_commits(worktree, derived.value["segments"])
    if not history.ok:
        return history
    recorded_list = [event["commit"] for event in events.value if event.get("event_type") == "commit"]
    if len(recorded_list) != len(set(recorded_list)):
        return failure("commit_assignment_invalid", "one implementation commit is assigned more than once")
    if set(history.value) != set(recorded_list):
        return failure("commit_bijection_invalid", "implementation history and commit evidence differ")
    return _append_event(
        run, "implementation_green",
        {"completed_steps": derived.value["completed_steps"],
         "uncommitted_outside_scope": outside_dirty}, derived=True,
    )

def load_events(run: Run) -> RuntimeResult:
    events: list[dict] = []
    for expected, path in enumerate(sorted(run.evidence_path.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")), 1):
        loaded = read_json(path)
        if not loaded.ok:
            return loaded
        if loaded.value.get("sequence") != expected or not path.name.startswith(f"{expected:06d}-"):
            return failure("evidence_sequence_invalid", f"invalid event sequence: {path.name}")
        if loaded.value.get("version") == 1:
            return failure("legacy_evidence_unsupported", "version 1 implementation evidence is unsupported")
        if loaded.value.get("version") != 2:
            return failure("evidence_sequence_invalid", f"invalid event version: {path.name}")
        events.append(loaded.value)
    return ok(events)
