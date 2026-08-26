"""Command-line entry point."""
import argparse
import json
from pathlib import Path
from runtime.planning import resolve_plan
from runtime.resume import resume_unique

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an approved implementation plan")
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--repo", default=".")
    resolve.add_argument("--plan-path")
    resume = commands.add_parser("resume")
    resume.add_argument("--repo", required=True)
    resume.add_argument("--plan-key", required=True)
    resume.add_argument("--branch-head", required=True)
    resume.add_argument("--unexplained-commit", action="append", default=[])
    resume.add_argument("--uncommitted-path", action="append", default=[])
    resume.add_argument("--consequential-change", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "resume":
        result = resume_unique(
            Path(args.repo),
            plan_key=args.plan_key,
            branch_head=args.branch_head,
            unexplained_commits=args.unexplained_commit,
            uncommitted_paths=args.uncommitted_path,
            consequential_change=args.consequential_change,
        )
        if not result.ok:
            parser.error(result.error.message)
        print(json.dumps({
            "run_id": result.value["run"].run_id,
            "resume_step": result.value["resume_step"],
        }, ensure_ascii=False))
        return 0
    result = resolve_plan(Path(args.repo), plan_path=args.plan_path)
    if not result.ok:
        parser.error(result.error.message)
    print(json.dumps({
        "plan_key": result.value.plan_key,
        "path": result.value.path,
        "approval_commit": result.value.approval_commit,
    }, ensure_ascii=False))
    return 0
