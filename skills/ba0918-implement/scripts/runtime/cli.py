"""Command-line entry: completion marking and the argparse surface."""
import shlex
from datetime import datetime, timezone
from typing import Callable
from runtime.tdd import validate_step_test_targets
from runtime.context import changed_paths
from runtime.gates import check_human_gates
import argparse
import json
import secrets
from pathlib import Path
from typing import Any

from runtime.deps import execution_model, plan_artifact
from runtime.types import RuntimeFailure, RuntimeResult, Attempt, ok, failure
from runtime.gitio import run_git
from runtime.storage import read_json
from runtime.planning import resolve_plan
from runtime.repository import bootstrap_attempt
from runtime.context import load_events, validate_context, append_event, derive_attempt_result, stop_attempt
from runtime.resume import residual_executions, resume_execution, load_current_attempt
from runtime.tdd import accept_red, run_frozen_oracle
from runtime.gates import record_human_gate
from runtime.deliverables import record_artifact, record_external, record_approval
from runtime.staging import stage_paths, record_commit


def mark_implementation_green(attempt: Attempt) -> RuntimeResult:
    loaded = load_events(attempt)
    if not loaded.ok:
        return loaded
    commits = [event["commit_sha"] for event in loaded.value if event["event_type"] == "commit"]
    if not commits:
        return failure("commit_missing", "implementation green requires at least one commit")
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    try:
        registered = plan_artifact.read_registered_plan(
            attempt.main_checkout,
            binding_result.value["plan"]["path"],
        )
    except (KeyError, TypeError, plan_artifact.PlanArtifactError) as error:
        return failure("plan_identity_drift", "bound plan cannot be verified", str(error))
    try:
        steps = plan_artifact.read_plan_steps(registered.text)
    except plan_artifact.InvalidPlanFormat as error:
        return failure("plan_format_invalid", str(error))
    step_ids = tuple(f"step-{step.number}" for step in steps)
    for step in steps:
        step_id = f"step-{step.number}"
        evidence = execution_model.validate_step_evidence(loaded.value, step_id, step.completion_kind)
        if not evidence.ok:
            return failure(evidence.error.code, evidence.error.message)
        if step.completion_kind == "test":
            targets = validate_step_test_targets(attempt, step_id)
            if not targets.ok:
                return targets
    final_step = step_ids[-1]
    context = validate_context(attempt, step_id=final_step)
    if not context.ok:
        return stop_attempt(attempt, context.error, final_step)
    changed = changed_paths(attempt.worktree)
    if not changed.ok:
        return stop_attempt(attempt, changed.error, final_step)
    if changed.value:
        return stop_attempt(
            attempt,
            RuntimeFailure(
                "post_verification_dirty",
                "final verification left the bound worktree dirty",
            ),
            final_step,
        )
    head = run_git(attempt.worktree, "rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != commits[-1]:
        return stop_attempt(
            attempt,
            RuntimeFailure(
                "commit_identity_drift",
                "worktree HEAD differs from the last durable commit event",
            ),
            final_step,
        )
    history = run_git(
        attempt.worktree,
        "rev-list",
        "--reverse",
        f"{binding_result.value['base_head']}..{head.stdout.strip()}",
    )
    observed_commits = [line for line in history.stdout.splitlines() if line]
    if history.returncode != 0 or observed_commits != commits:
        return stop_attempt(
            attempt,
            RuntimeFailure(
                "commit_history_mismatch",
                "base-to-HEAD commits differ from durable commit events",
            ),
            final_step,
        )
    history_paths = run_git(
        attempt.worktree,
        "diff",
        "--name-only",
        binding_result.value["base_head"],
        head.stdout.strip(),
    )
    if history_paths.returncode != 0:
        return stop_attempt(
            attempt,
            RuntimeFailure("commit_history_mismatch", "base-to-HEAD paths cannot be observed"),
            final_step,
        )
    for path in history_paths.stdout.splitlines():
        scope = execution_model.validate_write_path(path, binding_result.value["write_scope"])
        if not scope.ok:
            return stop_attempt(attempt, RuntimeFailure(scope.error.code, scope.error.message), final_step)
    for step_id in step_ids:
        gates = check_human_gates(
            attempt,
            step_id=step_id,
            timing="before_implementation_green",
        )
        if not gates.ok:
            return gates
    return append_event(attempt, "implementation_green", {"commits": commits})

def generate_attempt_id(
    *,
    now: Callable[[], str] | None = None,
    random_suffix: Callable[[], str] | None = None,
) -> str:
    timestamp = (
        now()
        if now is not None
        else datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")
    )
    suffix = random_suffix() if random_suffix is not None else secrets.token_hex(4)
    return f"{timestamp}-{suffix}"

def _attempt_payload(attempt: Attempt) -> dict[str, Any]:
    return {
        "attempt_id": attempt.attempt_id,
        "plan_id": attempt.plan_id,
        "branch": attempt.branch,
        "worktree": str(attempt.worktree),
        "binding_path": str(attempt.binding_path),
        "evidence_path": str(attempt.evidence_path),
    }

def _print_failure(result: RuntimeResult, *, state: str) -> int:
    payload = {
        "state": state,
        "reason": result.error.code,
        "message": result.error.message,
    }
    if result.error.detail:
        payload["detail"] = result.error.detail
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 2

def _load_for_command(args: argparse.Namespace) -> RuntimeResult:
    return load_current_attempt(
        Path(args.repo),
        plan_id=getattr(args, "plan_id", None),
        attempt_id=getattr(args, "execution_id", None),
    )

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bind and verify one implement execution")
    commands = parser.add_subparsers(dest="command", required=True)

    resolve = commands.add_parser("resolve", help="resolve and validate a registered plan")
    resolve.add_argument("--repo", required=True)
    resolve.add_argument("--plan-path")
    resolve.add_argument("--receipt-path")
    resolve.add_argument("--receipt-identity")

    bootstrap = commands.add_parser("bootstrap", help="create the execution branch and worktree")
    bootstrap.add_argument("--repo", required=True)
    bootstrap.add_argument("--plan-path")
    bootstrap.add_argument("--receipt-path")
    bootstrap.add_argument("--receipt-identity")
    bootstrap.add_argument("--worktree", required=True)
    bootstrap.add_argument("--executor", required=True)
    bootstrap.add_argument("--backend", default="unavailable")
    bootstrap.add_argument("--session-id", default="unavailable")

    def execution_ids(command: argparse.ArgumentParser) -> None:
        command.add_argument("--plan-id")
        command.add_argument("--execution-id")

    load = commands.add_parser("load", help="reconstruct an execution from its evidence")
    load.add_argument("--repo", required=True)
    execution_ids(load)

    context = commands.add_parser("context", help="revalidate the current execution boundary")
    context.add_argument("--repo", required=True)
    execution_ids(context)
    context.add_argument("--step", required=True)

    red = commands.add_parser("accept-red", help="run and freeze an expected RED oracle")
    red.add_argument("--repo", required=True)
    execution_ids(red)
    red.add_argument("--oracle", required=True)

    run = commands.add_parser("run-oracle", help="run the frozen GREEN or REFACTOR oracle")
    run.add_argument("--repo", required=True)
    execution_ids(run)
    run.add_argument("--step", required=True)
    run.add_argument("--phase", choices=("green", "refactor"), required=True)

    stage = commands.add_parser("stage", help="stage approved files individually")
    stage.add_argument("--repo", required=True)
    execution_ids(stage)
    stage.add_argument("--step", required=True)
    stage.add_argument("--path", action="append", required=True)

    artifact = commands.add_parser("record-artifact", help="record the files an artifact step produced")
    artifact.add_argument("--repo", required=True)
    execution_ids(artifact)
    artifact.add_argument("--step", required=True)
    artifact.add_argument("--path", action="append", required=True)
    artifact.add_argument("--check", action="append", default=[], help="a format check command, quoted as one shell-style string")

    external = commands.add_parser("record-external", help="record what an external step checked")
    external.add_argument("--repo", required=True)
    execution_ids(external)
    external.add_argument("--step", required=True)
    external.add_argument("--checked", required=True)
    external.add_argument("--summary", required=True)

    approve = commands.add_parser("approve", help="record the human's verdict on a step's deliverable")
    approve.add_argument("--repo", required=True)
    execution_ids(approve)
    approve.add_argument("--step", required=True)
    approve.add_argument("--result", choices=("approved", "rejected"), required=True)

    record = commands.add_parser("record-commit", help="verify and record an existing commit")
    record.add_argument("--repo", required=True)
    execution_ids(record)
    record.add_argument("--step", required=True)
    record.add_argument("--previous-head", required=True)

    human_gate = commands.add_parser("human-gate", help="record a declared human gate decision")
    human_gate.add_argument("--repo", required=True)
    execution_ids(human_gate)
    human_gate.add_argument("--step", required=True)
    human_gate.add_argument("--gate", required=True)
    human_gate.add_argument("--result", choices=("approved", "rejected"), required=True)

    check_gates = commands.add_parser(
        "check-gates",
        help="verify declared human gates before crossing a boundary",
    )
    check_gates.add_argument("--repo", required=True)
    execution_ids(check_gates)
    check_gates.add_argument("--step", required=True)
    check_gates.add_argument(
        "--timing",
        choices=tuple(execution_model.HUMAN_GATE_TIMINGS),
        required=True,
    )

    stop = commands.add_parser("stop", help="record a blocking stop")
    stop.add_argument("--repo", required=True)
    execution_ids(stop)
    stop.add_argument("--step", required=True)
    stop.add_argument("--reason", required=True)

    green = commands.add_parser(
        "implementation-green",
        help="record the Phase 3 terminal event",
    )
    green.add_argument("--repo", required=True)
    execution_ids(green)

    resume = commands.add_parser("resume", help="continue an unfinished execution after the human chose to")
    resume.add_argument("--repo", required=True)
    resume.add_argument("--plan-id", required=True)
    resume.add_argument("--execution-id", required=True)

    residual = commands.add_parser("residual", help="describe unfinished executions of a plan (read-only)")
    residual.add_argument("--repo", required=True)
    residual.add_argument("--plan-id", required=True)

    result = commands.add_parser("result", help="derive the current result from events")
    result.add_argument("--repo", required=True)
    execution_ids(result)

    args = parser.parse_args(argv)
    repo = Path(args.repo)
    if args.command in {"resolve", "bootstrap"}:
        receipt = None
        if args.receipt_path is not None or args.receipt_identity is not None:
            if args.receipt_path is None or args.receipt_identity is None:
                incomplete = failure(
                    "publication_receipt_invalid",
                    "receipt path and identity must be supplied together",
                )
                return _print_failure(incomplete, state="not_started")
            receipt = {
                "path": args.receipt_path,
                "content_identity": args.receipt_identity,
            }
        resolved = resolve_plan(repo, explicit_path=args.plan_path, receipt=receipt)
        if not resolved.ok:
            return _print_failure(resolved, state="not_started")
        if args.command == "resolve":
            print(
                json.dumps(
                    {
                        "plan_id": resolved.value.plan_id,
                        "path": resolved.value.path,
                        "revision": resolved.value.revision,
                        "content_identity": resolved.value.content_identity,
                        "specs": [
                            {"path": path, "content_identity": identity}
                            for path, identity in resolved.value.specs
                        ],
                        "write_scope": list(resolved.value.write_scope),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        executor = {
            "executor": args.executor,
            "backend": args.backend,
            "session_id": args.session_id,
        }
        if args.backend == "unavailable" or args.session_id == "unavailable":
            executor["reason"] = "not exposed safely"
        bootstrapped = bootstrap_attempt(
            repo,
            resolved.value,
            worktree_path=Path(args.worktree),
            attempt_id_factory=generate_attempt_id,
            executor=executor,
        )
        if not bootstrapped.ok:
            return _print_failure(bootstrapped, state="not_started")
        payload = _attempt_payload(bootstrapped.value)
        payload["state"] = "stopped"
        payload["reason"] = "terminal_event_missing"
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "resume":
        resumed = resume_execution(repo, plan_id=args.plan_id, attempt_id=args.execution_id)
        if not resumed.ok:
            return _print_failure(resumed, state="stopped")
        print(json.dumps(resumed.value, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "residual":
        found = residual_executions(repo, plan_id=args.plan_id)
        if not found.ok:
            return _print_failure(found, state="not_started")
        print(json.dumps({"plan_id": args.plan_id, "executions": found.value}, ensure_ascii=False))
        return 0

    loaded = _load_for_command(args)
    if not loaded.ok:
        return _print_failure(loaded, state="not_started")
    attempt = loaded.value
    if args.command == "load":
        print(json.dumps(_attempt_payload(attempt), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "record-artifact":
        recorded = record_artifact(
            attempt, step_id=args.step, paths=args.path, checks=[shlex.split(check) for check in args.check]
        )
        if not recorded.ok:
            return _print_failure(recorded, state="stopped")
        print(json.dumps(recorded.value, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "record-external":
        recorded = record_external(attempt, step_id=args.step, checked=args.checked, summary=args.summary)
        if not recorded.ok:
            return _print_failure(recorded, state="stopped")
        print(json.dumps(recorded.value, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "approve":
        recorded = record_approval(attempt, step_id=args.step, result=args.result)
        if not recorded.ok:
            return _print_failure(recorded, state="stopped")
        print(json.dumps(recorded.value, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "context":
        operation = validate_context(attempt, step_id=args.step)
    elif args.command == "accept-red":
        oracle_path = Path(args.oracle)
        oracle_result = read_json(oracle_path)
        operation = oracle_result if not oracle_result.ok else accept_red(attempt, oracle_result.value)
    elif args.command == "run-oracle":
        operation = run_frozen_oracle(attempt, args.step, args.phase)
    elif args.command == "stage":
        operation = stage_paths(attempt, args.path, step_id=args.step)
    elif args.command == "record-commit":
        operation = record_commit(attempt, args.step, args.previous_head)
    elif args.command == "human-gate":
        operation = record_human_gate(
            attempt,
            step_id=args.step,
            gate_id=args.gate,
            result=args.result,
        )
    elif args.command == "check-gates":
        checked = check_human_gates(attempt, step_id=args.step, timing=args.timing)
        operation = checked if not checked.ok else ok(
            {
                "state": "approved",
                "step_id": args.step,
                "timing": args.timing,
                "target_identities": checked.value,
            }
        )
    elif args.command == "stop":
        operation = append_event(
            attempt,
            "stopped",
            {"reason": args.reason, "step_id": args.step},
        )
    elif args.command == "implementation-green":
        operation = mark_implementation_green(attempt)
    else:
        print(json.dumps(derive_attempt_result(attempt), ensure_ascii=False, sort_keys=True))
        return 0

    if not operation.ok:
        return _print_failure(operation, state="stopped")
    print(json.dumps(operation.value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
