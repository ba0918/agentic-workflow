"""Check, artifact and external steps: what each records, and which of them a human judges."""
from runtime.planning import raw_identity, step_checks, step_completion_kinds
import shlex
import subprocess
from pathlib import PurePosixPath
from typing import Any

from runtime.deps import execution_model
from runtime.types import RuntimeFailure, RuntimeResult, Attempt, ok, failure
from runtime.planning import require_completion_kind
from runtime.context import append_event, changed_paths, load_events, validate_context, stop_attempt

EXTERNAL_TEXT_LIMIT = 500


def _run_check(attempt: Attempt, command: list[str]) -> RuntimeResult:
    if any(execution_model.SECRET_ARGUMENT.search(part) for part in command):
        return failure("secret_value_forbidden", "check command carries a secret-shaped argument")
    try:
        completed = subprocess.run(
            command,
            cwd=attempt.worktree,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return failure("check_failed", "format check could not be executed", str(error))
    return ok({"command": list(command), "exit_code": completed.returncode})

def _changed_files_in_scope(attempt: Attempt, scopes: list[str]) -> RuntimeResult:
    changed = changed_paths(attempt.worktree)
    if not changed.ok:
        return changed
    files: list[dict[str, str]] = []
    for path in changed.value:
        if not execution_model.validate_write_path(path, scopes).ok:
            continue
        candidate = attempt.worktree.joinpath(*PurePosixPath(path).parts)
        if candidate.is_symlink() or not candidate.is_file():
            continue
        files.append({"path": path, "content_identity": raw_identity(candidate.read_text(encoding="utf-8"))})
    return ok(files)

def record_check(attempt: Attempt, *, step_id: str) -> RuntimeResult:
    """Run the checks the plan declared for the step; no human verdict stands between them and done."""
    kind = require_completion_kind(attempt, step_id, "check")
    if not kind.ok:
        return stop_attempt(attempt, kind.error, step_id)
    declared = step_checks(attempt, step_id)
    if not declared.ok:
        return declared
    if not declared.value:
        return failure("check_declaration_missing", f"{step_id} declares no check command")
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return stop_attempt(attempt, context.error, step_id)
    results: list[dict[str, Any]] = []
    for command in declared.value:
        ran = _run_check(attempt, shlex.split(command))
        if not ran.ok:
            return ran
        results.append(ran.value)
        if ran.value["exit_code"] != 0:
            # A check that fails is not a stop: it names what to fix, and the step records again.
            return failure("check_failed", f"a declared check of {step_id} did not succeed", command)
    after = validate_context(attempt, step_id=step_id)
    if not after.ok:
        return stop_attempt(attempt, after.error, step_id)
    files = _changed_files_in_scope(attempt, after.value["write_scope"])
    if not files.ok:
        return files
    return append_event(attempt, "check", {"step_id": step_id, "checks": results, "files": files.value})

def record_artifact(attempt: Attempt, *, step_id: str, paths: list[str], checks: list[list[str]]) -> RuntimeResult:
    """Record the files an artifact step produced, with their identities and format checks."""
    kind = require_completion_kind(attempt, step_id, "artifact")
    if not kind.ok:
        return stop_attempt(attempt, kind.error, step_id)
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return stop_attempt(attempt, context.error, step_id)
    scopes = context.value["write_scope"]
    files: list[dict[str, str]] = []
    for path in paths:
        validation = execution_model.validate_write_path(path, scopes)
        if not validation.ok:
            return failure(validation.error.code, validation.error.message, path)
        candidate = attempt.worktree.joinpath(*PurePosixPath(path).parts)
        if candidate.is_symlink() or not candidate.is_file():
            return failure("artifact_missing", f"artifact file does not exist: {path}")
        files.append({"path": path, "content_identity": raw_identity(candidate.read_text(encoding="utf-8"))})
    results: list[dict[str, Any]] = []
    for command in checks:
        ran = _run_check(attempt, command)
        if not ran.ok:
            return ran
        results.append(ran.value)
    after = validate_context(attempt, step_id=step_id)
    if not after.ok:
        return stop_attempt(attempt, after.error, step_id)
    return append_event(attempt, "artifact", {"step_id": step_id, "files": files, "checks": results})

def record_external(attempt: Attempt, *, step_id: str, checked: str, summary: str) -> RuntimeResult:
    """Record what an external step checked and how it went; the human's verdict comes separately."""
    kind = require_completion_kind(attempt, step_id, "external")
    if not kind.ok:
        return stop_attempt(attempt, kind.error, step_id)
    for label, text in (("checked", checked), ("summary", summary)):
        # Bounded here rather than in the record's own validation: the length is what keeps a
        # pasted process output from reaching the evidence, so it belongs where the text arrives.
        if not text.strip() or len(text) > EXTERNAL_TEXT_LIMIT:
            return failure("external_text_invalid", f"external {label} must be short, non-empty text")
        if execution_model.SECRET_ARGUMENT.search(text):
            return failure("secret_value_forbidden", f"external {label} carries a secret-shaped value")
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return stop_attempt(attempt, context.error, step_id)
    return append_event(attempt, "external", {"step_id": step_id, "checked": checked, "summary": summary})

def record_approval(attempt: Attempt, *, step_id: str, result: str) -> RuntimeResult:
    """Record the human's verdict on the step's latest deliverable; a rejection stops the execution."""
    kinds = step_completion_kinds(attempt)
    if not kinds.ok:
        return kinds
    kind = kinds.value.get(step_id)
    if kind not in {"artifact", "external"}:
        mismatch = RuntimeFailure("completion_kind_mismatch", f"{step_id} is shown by '{kind}', which needs no approval")
        return stop_attempt(attempt, mismatch, step_id)
    if result not in execution_model.APPROVAL_RESULTS:
        return failure("approval_result_invalid", "approval result must be approved or rejected")
    events = load_events(attempt)
    if not events.ok:
        return events
    target = execution_model.latest_deliverable(events.value, step_id)
    if target is None:
        return failure("approval_target_missing", f"{step_id} has no artifact or external evidence to approve")
    failed_checks = [check for check in target.get("checks", []) if check.get("exit_code") != 0]
    if failed_checks:
        # The specification makes passing the format check part of the completion itself, so a
        # human verdict cannot stand in for a check that failed: fix and record again first.
        return failure(
            "format_check_failed",
            f"the latest deliverable of {step_id} failed a format check; fix it and record it again",
            ", ".join(" ".join(check["command"]) for check in failed_checks),
        )
    recorded = append_event(
        attempt,
        "approval",
        {"step_id": step_id, "target_identity": execution_model.content_identity(target), "result": result},
    )
    if not recorded.ok:
        return recorded
    if result == "rejected":
        return stop_attempt(attempt, RuntimeFailure("approval_rejected", f"the human rejected the deliverable of {step_id}"), step_id)
    return recorded
