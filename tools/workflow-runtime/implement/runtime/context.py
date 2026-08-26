"""Evidence chain: context validation, event append, stop and permission records."""
from pathlib import Path, PurePosixPath
from typing import Any

from runtime.planning import validate_write_path
from runtime.storage import SECRET_ARGUMENT, canonical_json
from runtime.storage import RAW_LOG_FIELDS, first_forbidden_field, first_secret_field
from runtime.types import RuntimeFailure, RuntimeResult, Attempt, ok, failure
from runtime.gitio import run_git
from runtime.storage import read_json, write_atomic, write_once
from runtime.planning import raw_identity, read_plan_file
from runtime.repository import discover_repository


def seal_event(candidate: dict, previous_event: dict | None = None) -> RuntimeResult:
    raw_log = first_forbidden_field(candidate, RAW_LOG_FIELDS)
    if raw_log is not None:
        return failure("raw_log_forbidden", "raw process logs are not durable evidence", raw_log)
    secret = first_secret_field(candidate)
    if secret is not None:
        return failure("secret_value_forbidden", "secret values are not durable evidence", secret)
    if previous_event is not None and (
        previous_event.get("event_type") == "implementation_green"
        or (
            previous_event.get("event_type") == "stopped"
            and candidate.get("event_type") not in {"resumed", "rebound"}
        )
    ):
        return failure("terminal_event_chain", "terminal event cannot be extended", "sequence")
    return ok(dict(candidate))


def _last_rebound(events: list[dict]) -> tuple[int, dict | None]:
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("event_type") == "rebound":
            return index, events[index]
    return -1, None


def effective_binding(binding: dict, events: list[dict]) -> dict:
    """The binding as the last rebound left it: plan, specs, scope and gates follow the revision."""
    _, rebound = _last_rebound(events)
    if rebound is None:
        return dict(binding)
    effective = dict(binding)
    for field in ("plan", "specs", "write_scope", "human_gates", "steps"):
        if field not in rebound:
            continue
        effective[field] = rebound[field]
    return effective


def effective_events(events: list[dict]) -> list[dict]:
    """Events as the rebounds read them: carried steps renumbered, superseded evidence dropped.

    Every rebound applies to what the rebounds before it already left, so evidence one revision
    dropped stays dropped even when a later revision carries a step of the same number."""
    effective: list[dict] = []
    for event in events:
        if event.get("event_type") == "rebound":
            renumbered = {
                entry["previous_step_id"]: entry["step_id"]
                for entry in event["step_map"]
                if entry["previous_step_id"] is not None
            }
            superseded = set(event["superseded_steps"])
            carried: list[dict] = []
            for earlier in effective:
                step_id = earlier.get("step_id")
                if step_id is None:
                    carried.append(earlier)
                elif step_id in superseded or step_id not in renumbered:
                    continue
                else:
                    carried.append(dict(earlier, step_id=renumbered[step_id]))
            effective = carried
        effective.append(event)
    return effective


def derive_result(events: list[dict]) -> dict:
    if not events:
        return {"state": "not_started", "event_count": 0}
    last = events[-1]
    result = {
        "state": "stopped",
        "attempt_id": last["attempt_id"],
        "last_sequence": last["sequence"],
        "event_count": len(events),
    }
    if last["event_type"] == "implementation_green":
        result["state"] = "implementation_green"
        result["commits"] = list(last["commits"])
    elif last["event_type"] == "stopped":
        result["reason"] = last["reason"]
        if "step_id" in last:
            result["step_id"] = last["step_id"]
    elif last["event_type"] == "permission_required":
        result["reason"] = "permission_required"
        result["step_id"] = last["step_id"]
    else:
        result["reason"] = "terminal_event_missing"
    return result


def changed_paths(worktree: Path) -> RuntimeResult:
    status = run_git(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return failure("git_status_failed", "Git status could not be observed", status.stderr.strip())
    paths: list[str] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            before, after = path.split(" -> ", 1)
            paths.extend((before, after))
        else:
            paths.append(path)
    return ok(tuple(paths))

def load_effective_binding(attempt: Attempt) -> RuntimeResult:
    """The binding as the last rebound left it; the chain must be valid to trust a rebound."""
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    # A binding that cannot be read fails the same comparison a drifted one does, so the
    # runtime needs no separate check that its own record is well formed.
    if (
        not isinstance(binding, dict)
        or binding.get("attempt_id") != attempt.attempt_id
        or binding.get("branch") != attempt.branch
    ):
        return failure("binding_identity_drift", "attempt and binding disagree")
    events = load_events(attempt)
    if not events.ok:
        return events
    return ok(effective_binding(binding, events.value))

def validate_context(attempt: Attempt, *, step_id: str) -> RuntimeResult:
    effective = load_effective_binding(attempt)
    if not effective.ok:
        return effective
    binding = effective.value

    # The id and revision are not compared: they are prose the agent read once and declared at
    # binding time (docs/spec/plan.md), so the file cannot be asked for them again. The bytes are
    # what the execution stands on, and they are checked here.
    bound_plan = read_plan_file(attempt.main_checkout, binding["plan"]["path"])
    if not bound_plan.ok:
        return failure("plan_identity_drift", "the bound plan is no longer readable", binding["plan"]["path"])
    if raw_identity(bound_plan.value) != binding["plan"]["content_identity"]:
        return failure("plan_identity_drift", "the bound plan differs from the working tree", binding["plan"]["path"])
    if step_id not in {step.get("step_id") for step in (binding.get("steps") or [])}:
        return failure("step_missing", "current step is not one the execution was bound to")

    repository = discover_repository(attempt.worktree)
    if not repository.ok:
        return failure("worktree_identity_drift", "bound worktree is not a valid linked worktree")
    if (
        repository.value.main_checkout != attempt.main_checkout.resolve()
        or repository.value.checkout != attempt.worktree.resolve()
        or repository.value.repository_identity != binding["repository_identity"]
    ):
        return failure("worktree_identity_drift", "worktree Git identity differs from the binding")
    branch = run_git(attempt.worktree, "branch", "--show-current")
    ancestor = run_git(
        attempt.worktree,
        "merge-base",
        "--is-ancestor",
        binding["base_head"],
        "HEAD",
    )
    if branch.returncode != 0 or branch.stdout.strip() != binding["branch"] or ancestor.returncode != 0:
        return failure("worktree_identity_drift", "worktree branch or base HEAD differs from the binding")

    for spec in binding["specs"]:
        path = attempt.worktree.joinpath(*PurePosixPath(spec["path"]).parts)
        if path.is_symlink() or not path.is_file():
            return failure("spec_identity_drift", f"bound spec is unavailable: {spec['path']}")
        if raw_identity(path.read_text(encoding="utf-8")) != spec["content_identity"]:
            return failure("spec_identity_drift", f"bound spec changed: {spec['path']}")

    changed = changed_paths(attempt.worktree)
    if not changed.ok:
        return changed
    # Changes outside the write scope are a fact for the human, never a stop: the staging
    # boundary keeps them out of commits and the terminal check lists them for approval.
    out_of_scope = [
        path
        for path in changed.value
        if not validate_write_path(path, binding["write_scope"]).ok
    ]
    return ok(dict(binding, out_of_scope_changes=sorted(out_of_scope)))

def load_events(attempt: Attempt) -> RuntimeResult:
    events: list[dict] = []
    for path in sorted(attempt.evidence_path.glob("0*.json")):
        loaded = read_json(path)
        if not loaded.ok:
            return loaded
        events.append(loaded.value)
    return ok(events)

def completed_steps(events: list[dict]) -> list[str]:
    """Steps that reached a commit, numbered as the rebounds left them."""
    seen: list[str] = []
    for event in effective_events(events):
        if event.get("event_type") != "commit":
            continue
        step_id = event.get("step_id")
        if step_id is not None and step_id not in seen:
            seen.append(step_id)
    return seen

def current_status_path(attempt: Attempt) -> Path:
    return attempt.evidence_path / "current-status"

def write_current_status(attempt: Attempt, events: list[dict]) -> RuntimeResult:
    """The four facts of the specification, every one of them derived from the record.

    No "what to do next": a judgement cannot be derived by appending code, so writing one here
    would go stale the moment the reader disagrees with it.
    """
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = effective_binding(binding_result.value, events)
    plan = binding.get("plan") or {}
    last = events[-1] if events else {}
    document = {
        "plan": {"path": plan.get("path"), "revision": plan.get("revision")},
        "completed_steps": completed_steps(events),
        "last_event": {
            "event_type": last.get("event_type"),
            "reason": last.get("reason"),
        },
        "branch": attempt.branch,
        "worktree": str(attempt.worktree),
    }
    return write_atomic(current_status_path(attempt), canonical_json(document))

def append_event(attempt: Attempt, event_type: str, details: dict[str, Any]) -> RuntimeResult:
    loaded = load_events(attempt)
    if not loaded.ok:
        return loaded
    events = loaded.value
    next_sequence = len(events) + 1
    candidate = {
        "version": 1,
        "sequence": next_sequence,
        "event_type": event_type,
        "attempt_id": attempt.attempt_id,
        **details,
    }
    sealed = seal_event(candidate, previous_event=events[-1] if events else None)
    if not sealed.ok:
        return failure(sealed.error.code, sealed.error.message)
    persisted = write_once(
        attempt.evidence_path / f"{next_sequence:06d}-{event_type}.json",
        canonical_json(sealed.value),
    )
    if not persisted.ok:
        return persisted
    # The event is the record; the status is derived from it. Writing the status after the event
    # means a failure here leaves a stale status that the next append repairs, never a lost event.
    status = write_current_status(attempt, events + [sealed.value])
    if not status.ok:
        return status
    return ok(sealed.value)

RECORDED_TEXT_LIMIT = 500


def bounded_outside_text(label: str, text: object) -> RuntimeResult:
    """Text arriving from outside on its way into a durable record.

    The length is the guard the specification asks for, not a format check: it is what keeps a
    pasted process output out of the evidence, so it belongs where the text arrives.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > RECORDED_TEXT_LIMIT:
        return failure("recorded_text_invalid", f"{label} must be short, non-empty text")
    if SECRET_ARGUMENT.search(text):
        return failure("secret_value_forbidden", f"{label} carries a secret-shaped value")
    return ok(text)

def record_delegation(attempt: Attempt, *, executor: str, model: str) -> RuntimeResult:
    """Who the implementation was handed to. Handing it over is cycle's work, not implement's;
    implement only writes down that it happened."""
    for label, text in (("executor", executor), ("model", model)):
        checked = bounded_outside_text(label, text)
        if not checked.ok:
            return checked
    return append_event(attempt, "delegated", {"executor": executor, "model": model})

def record_return(attempt: Attempt, *, step_id: str, reason: str) -> RuntimeResult:
    """How far the delegated conversation got before it came back."""
    checked = bounded_outside_text("reason", reason)
    if not checked.ok:
        return checked
    return append_event(attempt, "returned", {"step_id": step_id, "reason": reason})

def derive_attempt_result(attempt: Attempt) -> dict:
    loaded = load_events(attempt)
    if not loaded.ok:
        return {
            "state": "stopped",
            "reason": loaded.error.code,
            "attempt_id": attempt.attempt_id,
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "evidence_path": str(attempt.evidence_path),
        }
    result = derive_result(loaded.value)
    result.update(
        {
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "evidence_path": str(attempt.evidence_path),
        }
    )
    commits = [event["commit_sha"] for event in loaded.value if event["event_type"] == "commit"]
    if commits and "commits" not in result:
        result["commits"] = commits
    return result

# What only a human can settle (docs/spec/implement.md「止まり方」): a decision the plan does not
# carry, a difference from what the human approved, a rejected deliverable, and a permission or a
# record that cannot be obtained. Everything else the agent puts right itself.
HUMAN_RETURNING = frozenset(
    {
        "steps_undeclared",
        "check_declaration_missing",
        "plan_identity_drift",
        "plan_registration_missing",
        "spec_identity_drift",
        "worktree_identity_drift",
        "binding_identity_drift",
        "approval_rejected",
        "human_gate_rejected",
        "human_gate_missing",
        "human_gate_undeclared",
        "human_gate_target_changed",
        "permission_required",
        "persistence_unavailable",
        "unsafe_path",
        "recovery_exhausted",
    }
)
RECOVERY_LIMIT = 3


def _recoveries_in_a_row(events: list[dict], step_id: str) -> int:
    """Recoveries the step has taken with nothing else happening in between."""
    count = 0
    for event in reversed([event for event in events if event.get("step_id") == step_id]):
        if event.get("event_type") != "recovering":
            break
        count += 1
    return count

def stop_attempt(attempt: Attempt, error: RuntimeFailure, step_id: str) -> RuntimeResult:
    """A durable stop is written only for what a human has to answer.

    Anything the agent can put right is recorded as a recovery and left to it. A step that takes
    the limit of recoveries without moving goes back to the human anyway: at that point the
    trouble is no longer something the next attempt will fix.
    """
    if error.code in HUMAN_RETURNING:
        append_event(attempt, "stopped", {"reason": error.code, "step_id": step_id})
        return RuntimeResult(None, error)
    loaded = load_events(attempt)
    taken = _recoveries_in_a_row(loaded.value, step_id) if loaded.ok else 0
    if taken + 1 >= RECOVERY_LIMIT:
        append_event(attempt, "stopped", {"reason": "recovery_exhausted", "step_id": step_id})
        return RuntimeResult(
            None,
            RuntimeFailure(
                "recovery_exhausted",
                f"{step_id} did not move after {RECOVERY_LIMIT} recoveries",
                error.code,
            ),
        )
    append_event(attempt, "recovering", {"reason": error.code, "step_id": step_id})
    return RuntimeResult(None, error)

def permission_required(
    attempt: Attempt,
    error: RuntimeFailure,
    step_id: str,
    operation_identity: str,
) -> RuntimeResult:
    append_event(
        attempt,
        "permission_required",
        {
            "step_id": step_id,
            "operation_identity": operation_identity,
            "outcome": "permission_required",
        },
    )
    return RuntimeResult(None, error)


def raw_events(evidence_path: Path) -> list[dict]:
    events: list[dict] = []
    for path in sorted(evidence_path.glob("0*.json")):
        loaded = read_json(path)
        if loaded.ok and isinstance(loaded.value, dict):
            events.append(loaded.value)
    return events
