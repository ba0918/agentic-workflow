"""Command-line entry point."""
import argparse
import json
from pathlib import Path
from runtime.planning import resolve_plan

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an approved implementation plan")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan-path")
    args = parser.parse_args(argv)
    result = resolve_plan(Path(args.repo), plan_path=args.plan_path)
    if not result.ok:
        parser.error(result.error.message)
    print(json.dumps({
        "plan_key": result.value.plan_key,
        "path": result.value.path,
        "approval_commit": result.value.approval_commit,
    }, ensure_ascii=False))
    return 0
