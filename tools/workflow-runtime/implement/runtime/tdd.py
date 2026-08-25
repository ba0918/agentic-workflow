"""The test-first cycle: oracle execution, RED acceptance, frozen GREEN/REFACTOR."""
import hashlib
from runtime.gitio import run_git
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from runtime.deps import execution_model
from runtime.types import RuntimeFailure, RuntimeResult, Attempt, ok, failure
from runtime.storage import read_json, write_once
from runtime.planning import require_completion_kind
from runtime.context import append_event, load_events, validate_context, stop_attempt, permission_required


def bounded_observation(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
    diagnostic = re.compile(
        r"(?i)(modulenotfounderror|importerror|permissionerror|permission denied|"
        r"assertionerror|fixture|collection error|network|connection)"
    )
    observation = next((line for line in reversed(lines) if diagnostic.search(line)), None)
    if observation is None:
        observation = lines[-1] if lines else "no output"
    observation = re.sub(
        r"(?i)\b(token|password|secret|credential)\s*[=:]\s*\S+",
        r"\1=<redacted>",
        observation,
    )
    return observation[:512]

def classify_process_failure(stdout: str, stderr: str) -> str:
    lowered = (stdout + "\n" + stderr).lower()
    if "modulenotfounderror" in lowered or "importerror" in lowered:
        return "import_failure"
    if "permissionerror" in lowered or "permission denied" in lowered:
        return "permission_failure"
    if "fixture" in lowered or "collection error" in lowered:
        return "fixture_failure"
    if "network" in lowered or "connection" in lowered:
        return "network_failure"
    return "behavior_failure"

def test_summary(stdout: str, stderr: str) -> dict[str, Any]:
    output = stdout + "\n" + stderr
    totals = re.findall(r"^Ran ([0-9]+) tests? in [^\n]+$", output, re.MULTILINE)
    failures = re.findall(r"^FAILED \(([^\n]+)\)$", output, re.MULTILINE)
    successes = re.findall(r"^OK(?: \(skipped=([0-9]+)\))?$", output, re.MULTILINE)
    if len(totals) == 1 and len(successes) == 1 and not failures:
        total = int(totals[0])
        skipped = int(successes[0] or 0)
        if skipped <= total:
            return {
                "status": "complete",
                "passed": total - skipped,
                "failed": 0,
                "skipped": skipped,
            }
    if len(totals) == 1 and len(failures) == 1:
        values = {"failures": 0, "errors": 0, "skipped": 0}
        for raw_item in failures[0].split(","):
            match = re.fullmatch(r"\s*(failures|errors|skipped)=([0-9]+)\s*", raw_item)
            if match is None:
                break
            values[match.group(1)] = int(match.group(2))
        else:
            total = int(totals[0])
            failed = values["failures"] + values["errors"]
            passed = total - failed - values["skipped"]
            if passed >= 0:
                return {
                    "status": "complete",
                    "passed": passed,
                    "failed": failed,
                    "skipped": values["skipped"],
                }
    return {
        "status": "unavailable",
        "reason": "runner did not expose one supported structured summary",
    }

def _oracle_cwd(attempt: Attempt, relative_path: str) -> RuntimeResult:
    if not execution_model.validate_relative_path(relative_path).ok:
        return failure("unsafe_path", "oracle cwd is not a safe relative path")
    root = attempt.worktree.resolve()
    parts = () if relative_path == "." else PurePosixPath(relative_path).parts
    candidate = attempt.worktree
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return failure("unsafe_path", "oracle cwd contains a symlink", relative_path)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        return failure("cwd_unavailable", "oracle cwd is unavailable", str(error))
    if (resolved != root and root not in resolved.parents) or not resolved.is_dir():
        return failure("unsafe_path", "oracle cwd escapes the bound worktree", relative_path)
    return ok(resolved)

def execute_oracle(attempt: Attempt, oracle: dict) -> RuntimeResult:
    cwd_result = _oracle_cwd(attempt, oracle["cwd"])
    if not cwd_result.ok:
        return cwd_result
    try:
        completed = subprocess.run(
            oracle["command"],
            cwd=cwd_result.value,
            text=True,
            capture_output=True,
            timeout=oracle["timeout_seconds"],
            check=False,
        )
    except subprocess.TimeoutExpired:
        return failure("timeout", "oracle exceeded its frozen timeout")
    except FileNotFoundError:
        return failure("command_missing", "oracle command is unavailable")
    except PermissionError:
        return failure("permission_required", "oracle command requires additional permission")
    observation = bounded_observation(completed.stdout, completed.stderr)
    return ok(
        {
            "exit_code": completed.returncode,
            "observation": observation,
            "test_summary": test_summary(completed.stdout, completed.stderr),
            "failure_kind": (
                "passed"
                if completed.returncode == 0
                else classify_process_failure(completed.stdout, completed.stderr)
            ),
        }
    )

def test_target_snapshot(worktree: Path, paths: list[str]) -> RuntimeResult:
    targets: list[dict[str, str]] = []
    root = worktree.resolve()
    for relative_path in paths:
        if not execution_model.validate_relative_path(relative_path).ok:
            return failure("test_target_invalid", "test target path is unsafe", relative_path)
        path = worktree.joinpath(*PurePosixPath(relative_path).parts)
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            return failure("test_target_unavailable", "test target is unavailable", str(error))
        if path.is_symlink() or (resolved.parent != root and root not in resolved.parents) or not resolved.is_file():
            return failure("test_target_invalid", "test target escapes the bound worktree", relative_path)
        try:
            identity = "sha256:" + hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError as error:
            return failure("test_target_unavailable", "test target cannot be read", str(error))
        targets.append({"path": relative_path, "content_identity": identity})
    return ok(targets)

def _validate_frozen_test_targets(attempt: Attempt, oracle: dict) -> RuntimeResult:
    expected = oracle["test_targets"]
    observed = test_target_snapshot(attempt.worktree, [item["path"] for item in expected])
    if not observed.ok:
        return observed
    if observed.value != expected:
        return failure("test_identity_drift", "frozen test target bytes changed")
    return ok(expected)

def validate_step_test_targets(attempt: Attempt, step_id: str) -> RuntimeResult:
    oracle_result = read_json(attempt.evidence_path / "oracles" / f"{step_id}.json")
    if not oracle_result.ok:
        return failure("oracle_missing", "frozen oracle is unavailable")
    validation = execution_model.validate_oracle(oracle_result.value)
    if not validation.ok:
        return failure(validation.error.code, validation.error.message)
    return _validate_frozen_test_targets(attempt, oracle_result.value)

def validate_step_test_targets_at(attempt: Attempt, step_id: str, commit_sha: str) -> RuntimeResult:
    """The freeze holds for the step's own lifetime: verify its targets as of its commit,
    so a later step may legitimately evolve the same test file afterwards."""
    oracle_result = read_json(attempt.evidence_path / "oracles" / f"{step_id}.json")
    if not oracle_result.ok:
        return failure("oracle_missing", "frozen oracle is unavailable")
    validation = execution_model.validate_oracle(oracle_result.value)
    if not validation.ok:
        return failure(validation.error.code, validation.error.message)
    for expected in oracle_result.value["test_targets"]:
        shown = run_git(attempt.worktree, "show", f"{commit_sha}:{expected['path']}")
        if shown.returncode != 0:
            return failure("test_target_unavailable", "frozen test target is absent from the step's commit", expected["path"])
        identity = "sha256:" + hashlib.sha256(shown.stdout.encode("utf-8")).hexdigest()
        if identity != expected["content_identity"]:
            return failure("test_identity_drift", "frozen test target bytes changed before the step's commit", expected["path"])
    return ok(oracle_result.value["test_targets"])


def accept_red(attempt: Attempt, oracle: dict) -> RuntimeResult:
    validation = execution_model.validate_oracle_candidate(oracle)
    if not validation.ok:
        return stop_attempt(
            attempt,
            RuntimeFailure(validation.error.code, validation.error.message),
            oracle.get("step_id", "unknown"),
        )
    step_id = oracle["step_id"]
    kind = require_completion_kind(attempt, step_id, "test")
    if not kind.ok:
        return stop_attempt(attempt, kind.error, step_id)
    before = validate_context(attempt, step_id=step_id)
    if not before.ok:
        return stop_attempt(attempt, before.error, step_id)
    targets_before = test_target_snapshot(attempt.worktree, oracle["test_targets"])
    if not targets_before.ok:
        return stop_attempt(attempt, targets_before.error, step_id)
    executed = execute_oracle(attempt, oracle)
    if not executed.ok:
        if executed.error.code == "permission_required":
            return permission_required(
                attempt,
                executed.error,
                step_id,
                execution_model.content_identity(oracle),
            )
        return stop_attempt(attempt, executed.error, step_id)
    after = validate_context(attempt, step_id=step_id)
    if not after.ok:
        return stop_attempt(attempt, after.error, step_id)
    targets_after = test_target_snapshot(attempt.worktree, oracle["test_targets"])
    if not targets_after.ok:
        return stop_attempt(attempt, targets_after.error, step_id)
    if targets_after.value != targets_before.value:
        return stop_attempt(
            attempt,
            RuntimeFailure("test_identity_drift", "test target changed during RED execution"),
            step_id,
        )
    observation = executed.value
    if (
        observation["exit_code"] == 0
        or observation["failure_kind"] != oracle["expected_failure_kind"]
        or oracle["failure_signature"] not in observation["observation"]
    ):
        return stop_attempt(
            attempt,
            RuntimeFailure("unintended_red", "RED did not fail for the approved missing behavior"),
            step_id,
        )
    frozen = dict(oracle)
    frozen["test_targets"] = targets_before.value
    frozen["observed_failure_kind"] = observation["failure_kind"]
    frozen_validation = execution_model.validate_oracle(frozen)
    if not frozen_validation.ok:
        return stop_attempt(
            attempt,
            RuntimeFailure(frozen_validation.error.code, frozen_validation.error.message),
            step_id,
        )
    oracle_identity = execution_model.content_identity(frozen)
    oracle_path = attempt.evidence_path / "oracles" / f"{step_id}.json"
    persisted = write_once(oracle_path, execution_model.canonical_json(frozen))
    if not persisted.ok:
        if persisted.error.code == "write_collision":
            # A step may change its mind about the test it freezes. What the freeze forbids is
            # weakening a test into GREEN, and this RED has just shown the new test failing.
            oracle_path.write_bytes(execution_model.canonical_json(frozen))
        else:
            return stop_attempt(attempt, persisted.error, step_id)
    return append_event(
        attempt,
        "red",
        {
            "step_id": step_id,
            "oracle_identity": oracle_identity,
            "outcome": "expected_failure",
            "exit_code": observation["exit_code"],
            "observation": observation["observation"],
            "test_summary": observation["test_summary"],
        },
    )

def run_frozen_oracle(attempt: Attempt, step_id: str, phase: str) -> RuntimeResult:
    if phase not in {"green", "refactor"}:
        return failure("phase_invalid", "frozen oracle phase must be green or refactor")
    oracle_result = read_json(attempt.evidence_path / "oracles" / f"{step_id}.json")
    if not oracle_result.ok:
        return stop_attempt(attempt, RuntimeFailure("oracle_missing", "frozen oracle is unavailable"), step_id)
    oracle = oracle_result.value
    validation = execution_model.validate_oracle(oracle)
    if not validation.ok:
        return stop_attempt(attempt, RuntimeFailure(validation.error.code, validation.error.message), step_id)
    target_validation = _validate_frozen_test_targets(attempt, oracle)
    if not target_validation.ok:
        # A frozen test that changed does not end the execution: the step takes a new RED,
        # which shows the changed test failing before it is allowed to pass.
        return target_validation
    events_result = load_events(attempt)
    if not events_result.ok:
        return RuntimeResult(None, events_result.error)
    red_events = [
        event
        for event in events_result.value
        if event["event_type"] == "red" and event.get("step_id") == step_id
    ]
    # Superseded REDs stay in the append-only evidence after a redo; only the newest
    # one is the freeze that GREEN and REFACTOR answer to.
    if not red_events or red_events[-1]["oracle_identity"] != execution_model.content_identity(
        oracle
    ):
        return stop_attempt(
            attempt,
            RuntimeFailure("oracle_identity_drift", "frozen oracle differs from the accepted RED"),
            step_id,
        )
    before = validate_context(attempt, step_id=step_id)
    if not before.ok:
        return stop_attempt(attempt, before.error, step_id)
    executed = execute_oracle(attempt, oracle)
    if not executed.ok:
        return stop_attempt(attempt, executed.error, step_id)
    after = validate_context(attempt, step_id=step_id)
    if not after.ok:
        return stop_attempt(attempt, after.error, step_id)
    target_validation = _validate_frozen_test_targets(attempt, oracle)
    if not target_validation.ok:
        return target_validation
    if executed.value["exit_code"] != 0:
        return stop_attempt(
            attempt,
            RuntimeFailure(f"{phase}_failed", f"frozen oracle did not pass during {phase}"),
            step_id,
        )
    return append_event(
        attempt,
        phase,
        {
            "step_id": step_id,
            "oracle_identity": execution_model.content_identity(oracle),
            "outcome": "passed",
            "exit_code": executed.value["exit_code"],
            "test_summary": executed.value["test_summary"],
            "observation": executed.value["observation"],
        },
    )
