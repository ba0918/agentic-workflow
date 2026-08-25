"""Command-line entry: completion marking and the argparse surface."""
import shlex
from datetime import datetime, timezone
from typing import Callable
from runtime.tdd import validate_step_test_targets_at
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
from runtime.resume import rebind_execution, rebind_preview, residual_executions, resume_execution, load_current_attempt
from runtime.tdd import accept_red, run_frozen_oracle
from runtime.gates import record_human_gate
from runtime.deliverables import record_artifact, record_check, record_external, record_approval
from runtime.staging import stage_paths, record_commit, record_commit_late


def _history_facts(attempt: Attempt, binding: dict, events: list[dict], final_step: str) -> RuntimeResult:
    """What the human must see before the terminal: commits and changes the evidence does not explain."""
    commits = [event["commit_sha"] for event in events if event["event_type"] == "commit"]
    changed = changed_paths(attempt.worktree)
    if not changed.ok:
        return stop_attempt(attempt, changed.error, final_step)
    in_scope_dirty = [path for path in changed.value if path not in binding["out_of_scope_changes"]]
    if in_scope_dirty:
        return stop_attempt(
            attempt,
            RuntimeFailure("post_verification_dirty", "final verification left in-scope files uncommitted"),
            final_step,
        )
    head = run_git(attempt.worktree, "rev-parse", "HEAD")
    history = run_git(attempt.worktree, "rev-list", "--reverse", f"{binding['base_head']}..{head.stdout.strip()}")
    observed_commits = [line for line in history.stdout.splitlines() if line]
    if head.returncode != 0 or history.returncode != 0:
        return stop_attempt(attempt, RuntimeFailure("commit_history_mismatch", "branch history cannot be observed"), final_step)
    # A recorded commit the history no longer holds means the branch was rewritten: that is a
    # contradiction between record and history, not an unplanned fact, so it still stops.
    if any(commit not in observed_commits for commit in commits):
        return stop_attempt(
            attempt,
            RuntimeFailure("commit_identity_drift", "a recorded commit is missing from the branch history"),
            final_step,
        )
    history_paths = run_git(attempt.worktree, "diff", "--name-only", binding["base_head"], head.stdout.strip())
    if history_paths.returncode != 0:
        return stop_attempt(attempt, RuntimeFailure("commit_history_mismatch", "base-to-HEAD paths cannot be observed"), final_step)
    out_of_scope_paths = sorted(
        path
        for path in history_paths.stdout.splitlines()
        if path and not execution_model.validate_write_path(path, binding["write_scope"]).ok
    )
    return ok(
        {
            "commits": observed_commits,
            "listing": {
                "unexplained_commits": [commit for commit in observed_commits if commit not in commits],
                "out_of_scope_paths": out_of_scope_paths,
                "uncommitted_out_of_scope": list(binding["out_of_scope_changes"]),
            },
        }
    )

def _terminal_context(attempt: Attempt) -> RuntimeResult:
    loaded = load_events(attempt)
    if not loaded.ok:
        return loaded
    events = execution_model.effective_events(loaded.value)
    if not any(event["event_type"] == "commit" for event in events):
        return failure("commit_missing", "implementation green requires at least one commit")
    try:
        registered = plan_artifact.read_registered_plan(
            attempt.main_checkout,
            execution_model.effective_binding(read_json(attempt.binding_path).value, loaded.value)["plan"]["path"],
        )
    except (KeyError, TypeError, plan_artifact.PlanArtifactError) as error:
        return failure("plan_identity_drift", "bound plan cannot be verified", str(error))
    try:
        steps = plan_artifact.read_plan_steps(registered.text)
    except plan_artifact.InvalidPlanFormat as error:
        return failure("plan_format_invalid", str(error))
    final_step = f"step-{steps[-1].number}"
    context = validate_context(attempt, step_id=final_step)
    if not context.ok:
        return stop_attempt(attempt, context.error, final_step)
    return ok((loaded.value, events, steps, context.value))

def approve_history(attempt: Attempt, reason: str | None = None) -> RuntimeResult:
    """Record the human's approval of the commits and changes the evidence does not explain."""
    prepared = _terminal_context(attempt)
    if not prepared.ok:
        return prepared
    _, events, steps, binding = prepared.value
    facts = _history_facts(attempt, binding, events, f"step-{steps[-1].number}")
    if not facts.ok:
        return facts
    listing = facts.value["listing"]
    if not any(listing.values()):
        return failure("history_approval_unnecessary", "every commit and change is explained by the evidence")
    details = dict(listing)
    if reason is not None:
        details["reason"] = reason
    return append_event(attempt, "history_approved", details)

def _history_is_approved(events: list[dict], listing: dict) -> bool:
    approvals = [event for event in events if event["event_type"] == "history_approved"]
    if not approvals:
        return False
    latest = approvals[-1]
    return all(latest[field] == value for field, value in listing.items())

def mark_implementation_green(attempt: Attempt) -> RuntimeResult:
    prepared = _terminal_context(attempt)
    if not prepared.ok:
        return prepared
    raw_events, events, steps, binding = prepared.value
    for step in steps:
        step_id = f"step-{step.number}"
        evidence = execution_model.validate_step_evidence(events, step_id, step.completion_kind)
        if not evidence.ok:
            return failure(evidence.error.code, evidence.error.message)
        if step.completion_kind == "test":
            step_commits = [
                event["commit_sha"]
                for event in events
                if event["event_type"] == "commit" and event.get("step_id") == step_id
            ]
            targets = validate_step_test_targets_at(attempt, step_id, step_commits[-1])
            if not targets.ok:
                return targets
    final_step = f"step-{steps[-1].number}"
    facts = _history_facts(attempt, binding, events, final_step)
    if not facts.ok:
        return facts
    listing = facts.value["listing"]
    if any(listing.values()) and not _history_is_approved(raw_events, listing):
        return failure(
            "history_approval_required",
            "commits or changes the evidence does not explain need the human's approval",
            json.dumps(listing, ensure_ascii=False, sort_keys=True),
        )
    for step in steps:
        gates = check_human_gates(
            attempt,
            step_id=f"step-{step.number}",
            timing="before_implementation_green",
        )
        if not gates.ok:
            return gates
    return append_event(attempt, "implementation_green", {"commits": facts.value["commits"]})

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

    checked = commands.add_parser("record-check", help="run and record the checks a check step declares")
    checked.add_argument("--repo", required=True)
    execution_ids(checked)
    checked.add_argument("--step", required=True)

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
    record_target = record.add_mutually_exclusive_group(required=True)
    record_target.add_argument("--previous-head", help="record the one commit made since this HEAD")
    record_target.add_argument("--commit", help="record late a commit the branch holds but the evidence never saw")

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

    approve_history_command = commands.add_parser(
        "approve-history", help="approve the commits and changes the evidence does not explain"
    )
    approve_history_command.add_argument("--repo", required=True)
    execution_ids(approve_history_command)
    approve_history_command.add_argument("--reason")

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

    rebind = commands.add_parser("rebind", help="map a revised plan onto an execution; record it only with --confirm")
    rebind.add_argument("--repo", required=True)
    rebind.add_argument("--plan-id", required=True)
    rebind.add_argument("--execution-id", required=True)
    rebind.add_argument("--plan-path")
    rebind.add_argument("--confirm", action="store_true")

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
    if args.command == "rebind":
        operation = rebind_execution if args.confirm else rebind_preview
        rebound = operation(repo, plan_id=args.plan_id, attempt_id=args.execution_id, plan_path=args.plan_path)
        if not rebound.ok:
            return _print_failure(rebound, state="stopped")
        print(json.dumps(rebound.value, ensure_ascii=False, sort_keys=True))
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
    if args.command == "record-check":
        recorded = record_check(attempt, step_id=args.step)
        if not recorded.ok:
            return _print_failure(recorded, state="stopped")
        print(json.dumps(recorded.value, ensure_ascii=False, sort_keys=True))
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
        if args.commit is not None:
            operation = record_commit_late(attempt, args.step, args.commit)
        else:
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
    elif args.command == "approve-history":
        operation = approve_history(attempt, reason=args.reason)
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
