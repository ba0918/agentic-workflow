"""Command-line entry point for implementation state transitions."""
import argparse
import json
from pathlib import Path

from runtime.context import (
    append_event, complete_run, follow_documents, rebound_run, record_commit, record_stage, stop_run,
)
from runtime.planning import resolve_plan
from runtime.repository import bind_run, load_run
from runtime.resume import discover_unfinished, resume_run, retire_run

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
    resume = commands.add_parser("resume")
    resume.add_argument("--repo", required=True)
    resume.add_argument("--plan-key", required=True)
    resume.add_argument("--run-id", required=True)
    discover = commands.add_parser("discover")
    discover.add_argument("--repo", required=True)
    discover.add_argument("--plan-key", required=True)
    retire = commands.add_parser("retire")
    _run_arguments(retire)
    retire.add_argument("--reason", required=True)
    stage = commands.add_parser("stage")
    _run_arguments(stage)
    stage.add_argument("--step", required=True)
    stage.add_argument("--phase", choices=("red", "green", "refactor", "check", "artifact", "external"), required=True)
    stage.add_argument("--command", dest="oracle_commands", action="append")
    stage.add_argument("--exit-code", dest="exit_codes", type=int, action="append")
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
    rebound.add_argument("--map", action="append", default=[])
    follow = commands.add_parser("follow-documents")
    _run_arguments(follow)
    follow.add_argument("--current-commit", required=True)
    follow.add_argument("--document", action="append", required=True)
    follow.add_argument("--reason", required=True)
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
        result = bind_run(
            Path(args.repo), plan.value, run_id=args.run_id, delegated=args.delegated,
            branch=args.branch, worktree=args.worktree,
        )
        if not result.ok:
            parser.error(result.error.message)
        print(json.dumps({"plan_key": result.value.plan_key, "run_id": result.value.run_id}, ensure_ascii=False))
        return 0
    if args.command == "resume":
        result = resume_run(Path(args.repo), plan_key=args.plan_key, run_id=args.run_id)
        if not result.ok:
            parser.error(result.error.message)
        print(json.dumps({"run_id": result.value["run"].run_id, "resume_step": result.value["resume_step"]}, ensure_ascii=False))
        return 0
    if args.command == "discover":
        return _emit(parser, discover_unfinished(Path(args.repo), args.plan_key))
    run = load_run(Path(args.repo), args.plan_key, args.run_id)
    if not run.ok:
        parser.error(run.error.message)
    if args.command == "retire":
        result = retire_run(Path(args.repo), plan_key=args.plan_key, run_id=args.run_id, reason=args.reason)
    elif args.command == "stage":
        reasons = _reasons(parser, args.unplanned_reason)
        commands = args.oracle_commands or []
        exit_codes = args.exit_codes or []
        if args.phase in {"red", "green", "refactor"}:
            if len(commands) != 1 or len(exit_codes) != 1:
                parser.error("test stage needs --command and --exit-code")
            result = record_stage(
                run.value, args.step, args.phase, command=commands[0],
                exit_code=exit_codes[0], test_paths=args.test_path,
            )
        elif args.phase in {"check", "artifact"}:
            if len(commands) != len(exit_codes) or (args.phase == "check" and not commands):
                parser.error("check commands need one matching --exit-code each")
            checks = [
                {"command": command, "exit_code": exit_code}
                for command, exit_code in zip(commands, exit_codes)
            ]
            result = append_event(run.value, args.phase, {
                "step": args.step, "checks": checks,
                "paths": sorted(args.path), "unplanned_reasons": reasons,
            })
        else:
            if args.condition_met is None or len(commands) != 1 or exit_codes or not args.summary:
                parser.error("external stage needs --command, --summary, and --condition-met=true|false")
            result = append_event(run.value, "external", {
                "step": args.step, "checked": commands[0], "summary": args.summary or "",
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
        mappings = []
        for value in args.map:
            old, separator, new = value.partition("=")
            if not separator:
                parser.error("--map must be OLD=NEW")
            mappings.append({"old": old, "new": new})
        result = rebound_run(
            run.value, args.approval_commit, args.reason, mappings=mappings,
        )
    elif args.command == "follow-documents":
        result = follow_documents(run.value, args.current_commit, args.document, args.reason)
    elif args.command == "complete":
        result = complete_run(run.value)
    elif args.command == "delegated":
        result = append_event(run.value, "delegated", {}, actor="cycle")
    else:
        result = append_event(run.value, "returned", {}, actor="cycle")
    return _emit(parser, result)

if __name__ == "__main__":
    raise SystemExit(main())
