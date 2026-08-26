"""Command-line entry point for implementation state transitions."""
import argparse
import json
from pathlib import Path

from runtime.context import (
    append_event, complete_run, rebound_run, record_commit, record_stage, stop_run,
)
from runtime.planning import resolve_plan
from runtime.repository import bind_run, load_run
from runtime.resume import resume_unique

def _run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-key", required=True)
    parser.add_argument("--run-id", required=True)

def _emit(parser: argparse.ArgumentParser, result) -> int:
    if not result.ok:
        parser.error(result.error.message)
    value = result.value
    if isinstance(value, dict):
        value = {key: str(item) if isinstance(item, Path) else item for key, item in value.items()}
    print(json.dumps(value, ensure_ascii=False))
    return 0

def _reasons(parser: argparse.ArgumentParser, values: list[str]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for value in values:
        path, separator, reason = value.partition("=")
        if not separator or not path or not reason.strip() or path in reasons:
            parser.error("--unplanned-reason must be a unique PATH=REASON")
        reasons[path] = reason.strip()
    return reasons

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an approved implementation plan")
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--repo", default=".")
    resolve.add_argument("--plan-path")
    bind = commands.add_parser("bind")
    bind.add_argument("--repo", required=True)
    bind.add_argument("--plan-path", required=True)
    bind.add_argument("--run-id", required=True)
    bind.add_argument("--branch", required=True)
    bind.add_argument("--worktree", required=True)
    bind.add_argument("--delegated", action="store_true")
    bind.add_argument("--step", action="append", default=[])
    resume = commands.add_parser("resume")
    resume.add_argument("--repo", required=True)
    resume.add_argument("--plan-key", required=True)
    resume.add_argument("--branch-head", required=True)
    resume.add_argument("--unexplained-commit", action="append", default=[])
    resume.add_argument("--uncommitted-path", action="append", default=[])
    resume.add_argument("--consequential-change", action="store_true")
    stage = commands.add_parser("stage")
    _run_arguments(stage)
    stage.add_argument("--step", required=True)
    stage.add_argument("--phase", choices=("red", "green", "refactor", "check", "artifact", "external"), required=True)
    stage.add_argument("--command", dest="oracle_command", required=True)
    stage.add_argument("--exit-code", type=int, required=True)
    stage.add_argument("--path", action="append", default=[])
    stage.add_argument("--test-path", action="append", default=[])
    stage.add_argument("--summary")
    stage.add_argument("--condition-met", choices=("true", "false"))
    stage.add_argument("--unplanned-reason", action="append", default=[])
    commit = commands.add_parser("record-commit")
    _run_arguments(commit)
    commit.add_argument("--step", required=True)
    commit.add_argument("--commit", required=True)
    commit.add_argument("--recorded-late", action="store_true")
    commit.add_argument("--unplanned-reason", action="append", default=[])
    stop = commands.add_parser("stop")
    _run_arguments(stop)
    stop.add_argument("--reason", required=True)
    rebound = commands.add_parser("rebound")
    _run_arguments(rebound)
    rebound.add_argument("--approval-commit", required=True)
    rebound.add_argument("--reason", required=True)
    complete = commands.add_parser("complete")
    _run_arguments(complete)
    delegated = commands.add_parser("delegated")
    _run_arguments(delegated)
    returned = commands.add_parser("returned")
    _run_arguments(returned)
    args = parser.parse_args(argv)

    if args.command == "resolve":
        result = resolve_plan(Path(args.repo), plan_path=args.plan_path)
        if not result.ok:
            parser.error(result.error.message)
        print(json.dumps({
            "plan_key": result.value.plan_key, "path": result.value.path,
            "approval_commit": result.value.approval_commit,
        }, ensure_ascii=False))
        return 0
    if args.command == "bind":
        plan = resolve_plan(Path(args.repo), plan_path=args.plan_path)
        if not plan.ok:
            parser.error(plan.error.message)
        steps = []
        for value in args.step:
            step_id, separator, completion = value.partition(":")
            if not separator:
                parser.error("--step must be ID:COMPLETION")
            steps.append({"id": step_id, "completion": completion})
        result = bind_run(
            Path(args.repo), plan.value, run_id=args.run_id, delegated=args.delegated,
            steps=steps, branch=args.branch, worktree=args.worktree,
        )
        if not result.ok:
            parser.error(result.error.message)
        print(json.dumps({"plan_key": result.value.plan_key, "run_id": result.value.run_id}, ensure_ascii=False))
        return 0
    if args.command == "resume":
        result = resume_unique(
            Path(args.repo), plan_key=args.plan_key, branch_head=args.branch_head,
            unexplained_commits=args.unexplained_commit, uncommitted_paths=args.uncommitted_path,
            consequential_change=args.consequential_change,
        )
        if not result.ok:
            parser.error(result.error.message)
        print(json.dumps({"run_id": result.value["run"].run_id, "resume_step": result.value["resume_step"]}, ensure_ascii=False))
        return 0
    run = load_run(Path(args.repo), args.plan_key, args.run_id)
    if not run.ok:
        parser.error(run.error.message)
    if args.command == "stage":
        reasons = _reasons(parser, args.unplanned_reason)
        if args.phase in {"red", "green", "refactor"}:
            result = record_stage(
                run.value, args.step, args.phase, command=args.oracle_command,
                exit_code=args.exit_code, test_paths=args.test_path,
            )
        elif args.phase in {"check", "artifact"}:
            result = append_event(run.value, args.phase, {
                "step": args.step, "checks": [{"command": args.oracle_command, "exit_code": args.exit_code}],
                "paths": sorted(args.path), "unplanned_reasons": reasons,
            })
        else:
            if args.condition_met is None:
                parser.error("external stage needs --condition-met=true|false")
            result = append_event(run.value, "external", {
                "step": args.step, "checked": args.oracle_command, "summary": args.summary or "",
                "condition_met": args.condition_met == "true",
                "unplanned_reasons": reasons,
            })
    elif args.command == "record-commit":
        result = record_commit(
            run.value, args.step, args.commit, recorded_late=args.recorded_late,
            unplanned_reasons=_reasons(parser, args.unplanned_reason),
        )
    elif args.command == "stop":
        result = stop_run(run.value, args.reason)
    elif args.command == "rebound":
        result = rebound_run(run.value, args.approval_commit, args.reason)
    elif args.command == "complete":
        result = complete_run(run.value)
    elif args.command == "delegated":
        result = append_event(run.value, "delegated", {}, actor="cycle")
    else:
        result = append_event(run.value, "returned", {}, actor="cycle")
    return _emit(parser, result)

if __name__ == "__main__":
    raise SystemExit(main())
