"""Command-line entry point for implementation state transitions."""
import argparse
from collections.abc import Callable
import json
from pathlib import Path

from runtime.context import (
    StageObservation, append_event, complete_run, follow_documents, rebound_run, record_commit,
    record_stage, stop_run,
)
from runtime.evidence import record_human_gate
from runtime.planning import resolve_plan
from runtime.repository import bind_run, load_run
from runtime.resume import discover_unfinished, resume_run, retire_run
from runtime.types import JsonObject, Run, RuntimeResult


def _run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-key", required=True)
    parser.add_argument("--run-id", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an approved implementation plan")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _entry_parsers(subparsers.add_parser)
    _transition_parsers(subparsers.add_parser)
    return parser


def _entry_parsers(add_parser: Callable[[str], argparse.ArgumentParser]) -> None:
    resolve = add_parser("resolve")
    resolve.add_argument("--repo", default=".")
    resolve.add_argument("--plan-path")
    bind = add_parser("bind")
    bind.add_argument("--repo", required=True)
    bind.add_argument("--plan-path", required=True)
    bind.add_argument("--run-id", required=True)
    bind.add_argument("--branch", required=True)
    bind.add_argument("--worktree", required=True)
    bind.add_argument("--delegated", action="store_true")
    resume = add_parser("resume")
    _run_arguments(resume)
    discover = add_parser("discover")
    discover.add_argument("--repo", required=True)
    discover.add_argument("--plan-key", required=True)


def _transition_parsers(add_parser: Callable[[str], argparse.ArgumentParser]) -> None:
    retire = add_parser("retire")
    _run_arguments(retire)
    retire.add_argument("--reason", required=True)
    stage = add_parser("stage")
    _run_arguments(stage)
    stage.add_argument("--step", required=True)
    stage.add_argument(
        "--phase",
        choices=("red", "green", "refactor", "check", "artifact", "external"),
        required=True,
    )
    stage.add_argument("--command", dest="oracle_commands", action="append")
    stage.add_argument("--exit-code", dest="exit_codes", type=int, action="append")
    stage.add_argument("--path", action="append", default=[])
    stage.add_argument("--test-path", action="append", default=[])
    stage.add_argument("--summary")
    stage.add_argument("--condition-met", choices=("true", "false"))
    stage.add_argument("--unplanned-reason", action="append", default=[])
    commit = add_parser("record-commit")
    _run_arguments(commit)
    commit.add_argument("--step", required=True)
    commit.add_argument("--commit", required=True)
    commit.add_argument("--recorded-late", action="store_true")
    commit.add_argument("--unplanned-reason", action="append", default=[])
    human_gate = add_parser("human-gate")
    _run_arguments(human_gate)
    human_gate.add_argument("--step", required=True)
    human_gate.add_argument("--gate-id", required=True)
    human_gate.add_argument("--result", choices=("approved", "rejected"), required=True)
    stop = add_parser("stop")
    _run_arguments(stop)
    stop.add_argument("--reason", required=True)
    rebound = add_parser("rebound")
    _run_arguments(rebound)
    rebound.add_argument("--approval-commit", required=True)
    rebound.add_argument("--reason", required=True)
    rebound.add_argument("--map", action="append", default=[])
    follow = add_parser("follow-documents")
    _run_arguments(follow)
    follow.add_argument("--current-commit", required=True)
    follow.add_argument("--document", action="append", required=True)
    follow.add_argument("--reason", required=True)
    complete = add_parser("complete")
    _run_arguments(complete)
    delegated = add_parser("delegated")
    _run_arguments(delegated)
    delegated.add_argument("--role", required=True, help="who received the delegation")
    delegated.add_argument("--model", required=True, help="full model id of the delegate")
    returned = add_parser("returned")
    _run_arguments(returned)
    returned.add_argument("--outcome")


def _string(args: argparse.Namespace, name: str) -> str:
    value: object = getattr(args, name)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    return value


def _optional_string(args: argparse.Namespace, name: str) -> str | None:
    value: object = getattr(args, name)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"{name} must be text")


def _strings(args: argparse.Namespace, name: str) -> list[str]:
    value: object = getattr(args, name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of text")
    return [item for item in value if isinstance(item, str)]


def _integers(args: argparse.Namespace, name: str) -> list[int]:
    value: object = getattr(args, name)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise ValueError(f"{name} must be a list of integers")
    return [item for item in value if isinstance(item, int)]


def _boolean(args: argparse.Namespace, name: str) -> bool:
    value: object = getattr(args, name)
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _emit(
    parser: argparse.ArgumentParser, result: RuntimeResult[object],
) -> int:
    if not result.ok:
        parser.error(
            result.error.message if result.error is not None else "runtime operation failed"
        )
    value = result.value
    if isinstance(value, dict):
        value = {
            str(key): str(item) if isinstance(item, Path) else item
            for key, item in value.items()
        }
    print(json.dumps(value, ensure_ascii=False))
    return 0


def _reasons(
    parser: argparse.ArgumentParser, values: list[str],
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for value in values:
        path, separator, reason = value.partition("=")
        if not separator or not path or not reason.strip() or path in reasons:
            parser.error("--unplanned-reason must be a unique PATH=REASON")
        reasons[path] = reason.strip()
    return reasons


def _resolve_command(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    result = resolve_plan(
        Path(_string(args, "repo")), plan_path=_optional_string(args, "plan_path")
    )
    if not result.ok:
        parser.error(
            result.error.message if result.error is not None else "plan could not be resolved"
        )
    plan = result.required()
    print(json.dumps({
        "plan_key": plan.plan_key,
        "path": plan.path,
        "approval_commit": plan.approval_commit,
        "specification_changes": [
            {
                "path": change.path,
                "approval_commit": plan.approval_commit,
                "current_commit": change.current_commit,
                "diff": change.diff,
            }
            for change in plan.specification_changes
        ],
    }, ensure_ascii=False))
    return 0


def _bind_command(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    plan = resolve_plan(Path(_string(args, "repo")), plan_path=_string(args, "plan_path"))
    if not plan.ok:
        parser.error(
            plan.error.message if plan.error is not None else "plan could not be resolved"
        )
    result = bind_run(
        Path(_string(args, "repo")),
        plan.required(),
        run_id=_string(args, "run_id"),
        delegated=_boolean(args, "delegated"),
        branch=_string(args, "branch"),
        worktree=_string(args, "worktree"),
    )
    if not result.ok:
        parser.error(
            result.error.message if result.error is not None else "run could not be bound"
        )
    run = result.required()
    print(json.dumps({"plan_key": run.plan_key, "run_id": run.run_id}, ensure_ascii=False))
    return 0


def _resume_command(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    result = resume_run(
        Path(_string(args, "repo")),
        plan_key=_string(args, "plan_key"),
        run_id=_string(args, "run_id"),
    )
    if not result.ok:
        parser.error(
            result.error.message if result.error is not None else "run could not be resumed"
        )
    value = result.required()
    run = value.get("run")
    if not isinstance(run, Run):
        parser.error("resumed run is invalid")
    print(json.dumps({
        "run_id": run.run_id,
        "resume_step": value.get("resume_step"),
    }, ensure_ascii=False))
    return 0


def _stage_command(
    parser: argparse.ArgumentParser, args: argparse.Namespace, run: Run,
) -> RuntimeResult[JsonObject]:
    reasons = _reasons(parser, _strings(args, "unplanned_reason"))
    commands_value: object = getattr(args, "oracle_commands")
    oracle_commands = [] if commands_value is None else _strings(args, "oracle_commands")
    exit_codes = _integers(args, "exit_codes")
    phase = _string(args, "phase")
    if phase in {"red", "green", "refactor"}:
        if len(oracle_commands) != 1 or len(exit_codes) != 1:
            parser.error("test stage needs --command and --exit-code")
        return record_stage(
            run,
            _string(args, "step"),
            phase,
            StageObservation(oracle_commands[0], exit_codes[0], _strings(args, "test_path")),
        )
    if phase in {"check", "artifact"}:
        if len(oracle_commands) != len(exit_codes) or phase == "check" and not oracle_commands:
            parser.error("check commands need one matching --exit-code each")
        checks: list[JsonObject] = [
            {"command": command, "exit_code": exit_code}
            for command, exit_code in zip(oracle_commands, exit_codes)
        ]
        return append_event(run, phase, {
            "step": _string(args, "step"),
            "checks": checks,
            "paths": sorted(_strings(args, "path")),
            "unplanned_reasons": reasons,
        })
    summary = _optional_string(args, "summary")
    condition = _optional_string(args, "condition_met")
    if condition is None or len(oracle_commands) != 1 or exit_codes or not summary:
        parser.error("external stage needs --command, --summary, and --condition-met=true|false")
    return append_event(run, "external", {
        "step": _string(args, "step"),
        "checked": oracle_commands[0],
        "summary": summary,
        "condition_met": condition == "true",
        "unplanned_reasons": reasons,
    })


def _mappings(parser: argparse.ArgumentParser, values: list[str]) -> list[JsonObject]:
    mappings: list[JsonObject] = []
    for value in values:
        old, separator, new = value.partition("=")
        if not separator:
            parser.error("--map must be OLD=NEW")
        mappings.append({"old": old, "new": new})
    return mappings


def _bound_command(
    parser: argparse.ArgumentParser, args: argparse.Namespace, run: Run,
) -> RuntimeResult[object]:
    command = _string(args, "command")
    if command == "stage":
        return _stage_command(parser, args, run)
    if command in {"retire", "record-commit", "stop"}:
        return _history_command(parser, args, run, command)
    if command == "human-gate":
        return record_human_gate(
            run,
            _string(args, "step"),
            _string(args, "gate_id"),
            _string(args, "result"),
        )
    if command in {"rebound", "follow-documents", "complete"}:
        return _document_command(parser, args, run, command)
    if command == "delegated":
        fields: JsonObject = {"role": _string(args, "role"), "model": _string(args, "model")}
        return append_event(run, command, fields, actor="cycle")
    outcome = _optional_string(args, "outcome")
    return append_event(
        run, command, {} if outcome is None else {"outcome": outcome}, actor="cycle",
    )


def _history_command(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    run: Run,
    command: str,
) -> RuntimeResult[object]:
    if command == "retire":
        return retire_run(
            Path(_string(args, "repo")),
            plan_key=_string(args, "plan_key"),
            run_id=_string(args, "run_id"),
            reason=_string(args, "reason"),
        )
    if command == "record-commit":
        return record_commit(
            run,
            _string(args, "step"),
            _string(args, "commit"),
            recorded_late=_boolean(args, "recorded_late"),
            unplanned_reasons=_reasons(parser, _strings(args, "unplanned_reason")),
        )
    if command == "stop":
        return stop_run(run, _string(args, "reason"))
    parser.error("unsupported history command")


def _document_command(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    run: Run,
    command: str,
) -> RuntimeResult[object]:
    if command == "rebound":
        return rebound_run(
            run,
            _string(args, "approval_commit"),
            _string(args, "reason"),
            mappings=_mappings(parser, _strings(args, "map")),
        )
    if command == "follow-documents":
        return follow_documents(
            run,
            _string(args, "current_commit"),
            _strings(args, "document"),
            _string(args, "reason"),
        )
    if command == "complete":
        return complete_run(run)
    parser.error("unsupported document command")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    command = _string(args, "command")
    if command == "resolve":
        return _resolve_command(parser, args)
    if command == "bind":
        return _bind_command(parser, args)
    if command == "resume":
        return _resume_command(parser, args)
    if command == "discover":
        return _emit(
            parser,
            discover_unfinished(
                Path(_string(args, "repo")), _string(args, "plan_key")
            ),
        )
    loaded = load_run(
        Path(_string(args, "repo")),
        _string(args, "plan_key"),
        _string(args, "run_id"),
    )
    if not loaded.ok:
        parser.error(
            loaded.error.message if loaded.error is not None else "run is unavailable"
        )
    return _emit(parser, _bound_command(parser, args, loaded.required()))


if __name__ == "__main__":
    raise SystemExit(main())
