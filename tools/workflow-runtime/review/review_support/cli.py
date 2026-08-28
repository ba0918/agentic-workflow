"""Command-line composition for the review runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_support.binding import bind_review, load_review_binding, resolve_input
from review_support.findings import (
    add_findings,
    begin_stage,
    close_finding,
    complete_review,
    mark_stale,
    rebound_findings,
    record_findings,
    record_human_decision,
    record_progress,
    record_second_review,
)
from review_support.types import JsonObject, RuntimeResult, object_value, object_values


def _selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True)
    parser.add_argument("--review-id")
    parser.add_argument("--plan-key")
    parser.add_argument("--run-id")


def _bind_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    bind = commands.add_parser("bind")
    bind.add_argument("--repo", required=True)
    bind.add_argument("--review-id", required=True)
    bind.add_argument("--plan-key")
    bind.add_argument("--run-id")
    bind.add_argument("--branch")
    bind.add_argument("--base")
    bind.add_argument("--head")
    bind.add_argument("--pull-request-target")
    bind.add_argument("--spec-path", action="append", default=[])
    bind.add_argument("--model", required=True)
    bind.add_argument("--model-source", default="explicit")
    bind.add_argument("--level", choices=("light", "standard"), default="standard")
    bind.add_argument("--profile", action="append", default=[])
    bind.add_argument("--second-reviewer")
    bind.add_argument("--second-model")
    bind.add_argument("--reviewer-context", required=True)


def _stage_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    begin = commands.add_parser("begin")
    _selector(begin)
    begin.add_argument("--reviewer-context", required=True)
    findings = commands.add_parser("record-findings")
    _selector(findings)
    findings.add_argument("--stage", choices=("initial", "final"), required=True)
    findings.add_argument("--reviewer-context", required=True)
    findings.add_argument("--actual-model", required=True)
    findings.add_argument("--findings-file", required=True)
    findings.add_argument("--safety-file", required=True)
    second = commands.add_parser("record-second-review")
    _selector(second)
    second.add_argument("--result-file", required=True)
    additions = commands.add_parser("add-findings")
    _selector(additions)
    additions.add_argument("--findings-file", required=True)
    additions.add_argument("--related-id", action="append", default=[])


def _transition_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    close = commands.add_parser("close-finding")
    _selector(close)
    close.add_argument("--finding-id", required=True)
    close.add_argument("--oracle-exit-code", type=int, required=True)
    close.add_argument("--fix-commit", action="append", default=[])
    close.add_argument("--operation", required=True)
    close.add_argument("--result-summary", required=True)
    human = commands.add_parser("human-decision")
    _selector(human)
    human.add_argument("--finding-id", required=True)
    human.add_argument("--decision", required=True)
    human.add_argument("--reason", required=True)
    progress = commands.add_parser("progress")
    _selector(progress)
    stale = commands.add_parser("stale")
    _selector(stale)
    stale.add_argument("--reason", required=True)
    rebound = commands.add_parser("rebound")
    _selector(rebound)
    rebound.add_argument("--spec-commit", required=True)
    rebound.add_argument("--reason", required=True)
    complete = commands.add_parser("complete")
    _selector(complete)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review evidence runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    _bind_parser(commands)
    _stage_parsers(commands)
    _transition_parsers(commands)
    return parser


def _read_object(path: str) -> JsonObject:
    value = object_value(json.loads(Path(path).read_text(encoding="utf-8")))
    if value is None:
        raise ValueError("review result file must contain an object")
    return value


def _read_objects(path: str) -> list[JsonObject]:
    value = object_values(json.loads(Path(path).read_text(encoding="utf-8")))
    if value is None:
        raise ValueError("findings file must contain a list of objects")
    return value


def _bind(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    root = Path(args.repo)
    binding = resolve_input(
        root,
        review_id=args.review_id,
        plan_key=args.plan_key,
        run_id=args.run_id,
        branch=args.branch,
        base=args.base,
        head=args.head,
        pull_request_target=args.pull_request_target,
        spec_paths=args.spec_path,
    )
    if not binding.ok:
        parser.error(binding.required_error().message)
    value = binding.required()
    bound = bind_review(
        root,
        value,
        model=args.model,
        model_source=args.model_source,
        level=args.level,
        profiles=args.profile,
        second_reviewer=args.second_reviewer,
        second_model=args.second_model,
    )
    if not bound.ok:
        parser.error(bound.required_error().message)
    stage = begin_stage(root, value, reviewer_context=args.reviewer_context)
    if not stage.ok:
        parser.error(stage.required_error().message)
    print(json.dumps({"input": value, "stage": stage.required()}, ensure_ascii=False))
    return 0


def _record_stage(root: Path, binding: JsonObject, args: argparse.Namespace) -> RuntimeResult[JsonObject]:
    return record_findings(
        root,
        binding,
        stage=args.stage,
        findings=_read_objects(args.findings_file),
        safety=_read_object(args.safety_file),
        reviewer_context=args.reviewer_context,
        actual_model=args.actual_model,
    )


def _record_second(root: Path, binding: JsonObject, path: str) -> RuntimeResult[JsonObject]:
    payload = _read_object(path)
    actual_model = payload.get("actual_model")
    return record_second_review(
        root,
        binding,
        status=str(payload.get("status", "")),
        actual_model=actual_model if isinstance(actual_model, str) else None,
        summary=str(payload.get("summary", "")),
    )


def _stage_transition(
    root: Path,
    binding: JsonObject,
    args: argparse.Namespace,
) -> RuntimeResult[JsonObject]:
    if args.command == "begin":
        return begin_stage(root, binding, reviewer_context=args.reviewer_context)
    if args.command == "record-findings":
        return _record_stage(root, binding, args)
    if args.command == "record-second-review":
        return _record_second(root, binding, args.result_file)
    if args.command == "add-findings":
        return add_findings(
            root,
            binding,
            candidates=_read_objects(args.findings_file),
            related_ids=set(args.related_id),
        )
    raise ValueError(f"unknown review stage command: {args.command}")


def _finding_transition(
    root: Path,
    binding: JsonObject,
    args: argparse.Namespace,
) -> RuntimeResult[JsonObject]:
    if args.command == "close-finding":
        return close_finding(
            root,
            binding,
            args.finding_id,
            oracle_exit_code=args.oracle_exit_code,
            fix_commits=args.fix_commit,
            operation=args.operation,
            result_summary=args.result_summary,
        )
    if args.command == "human-decision":
        return record_human_decision(
            root,
            binding,
            args.finding_id,
            decision=args.decision,
            reason=args.reason,
        )
    if args.command == "progress":
        return record_progress(root, binding)
    raise ValueError(f"unknown finding command: {args.command}")


def _lifecycle_transition(
    root: Path,
    binding: JsonObject,
    args: argparse.Namespace,
) -> RuntimeResult[JsonObject]:
    if args.command == "stale":
        return mark_stale(root, binding, reason=args.reason)
    if args.command == "rebound":
        return rebound_findings(root, binding, spec_commit=args.spec_commit, reason=args.reason)
    return complete_review(root, binding)


def _selected_transition(
    root: Path,
    binding: JsonObject,
    args: argparse.Namespace,
) -> RuntimeResult[JsonObject]:
    if args.command in {"begin", "record-findings", "record-second-review", "add-findings"}:
        return _stage_transition(root, binding, args)
    if args.command in {"close-finding", "human-decision", "progress"}:
        return _finding_transition(root, binding, args)
    return _lifecycle_transition(root, binding, args)


def main(argv: list[str] | None = None) -> int:
    """Run the stable review command-line interface."""

    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "bind":
        return _bind(parser, args)
    root = Path(args.repo)
    binding = load_review_binding(
        root,
        review_id=args.review_id,
        plan_key=args.plan_key,
        run_id=args.run_id,
    )
    if not binding.ok:
        parser.error(binding.required_error().message)
    try:
        result = _selected_transition(root, binding.required(), args)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    if not result.ok:
        parser.error(result.required_error().message)
    print(json.dumps(result.required(), ensure_ascii=False))
    return 0
