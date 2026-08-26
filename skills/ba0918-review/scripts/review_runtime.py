#!/usr/bin/env python3
"""Append-only review evidence for execution and standalone inputs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any, NamedTuple

import review_model

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
COMMIT = re.compile(r"[0-9a-f]{40,64}")

class RuntimeFailure(NamedTuple):
    code: str
    message: str

class RuntimeResult(NamedTuple):
    value: Any | None
    error: RuntimeFailure | None
    @property
    def ok(self) -> bool:
        return self.error is None

def ok(value: Any = None) -> RuntimeResult:
    return RuntimeResult(value, None)

def failure(code: str, message: str) -> RuntimeResult:
    return RuntimeResult(None, RuntimeFailure(code, message))

def execution_binding(plan_key: str, run_id: str, approval_commit: str, *, implement_sequence: int) -> dict:
    if SAFE_ID.fullmatch(plan_key) is None or SAFE_ID.fullmatch(run_id) is None or COMMIT.fullmatch(approval_commit) is None:
        raise ValueError("unsafe execution binding")
    return {
        "kind": "execution",
        "plan_key": plan_key,
        "run_id": run_id,
        "approval_commit": approval_commit,
        "implement_sequence": implement_sequence,
    }

def standalone_binding(
    review_id: str,
    *,
    base: str,
    head: str,
    spec_paths: list[str],
    branch: str | None = None,
) -> dict:
    if SAFE_ID.fullmatch(review_id) is None or COMMIT.fullmatch(base) is None or COMMIT.fullmatch(head) is None:
        raise ValueError("unsafe standalone binding")
    if branch is not None and (not branch or ".." in branch or branch.startswith("-")):
        raise ValueError("unsafe branch")
    for path in spec_paths:
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("unsafe specification path")
    return {
        "kind": "standalone",
        "review_id": review_id,
        "input": {"kind": "branch" if branch else "commits", "branch": branch, "base": base, "head": head},
        "spec_paths": sorted(spec_paths),
        "spec_commit": head,
    }

def input_kind(binding: dict) -> str:
    if binding.get("kind") == "execution":
        return "execution"
    return binding.get("input", {}).get("kind", "unknown")

def choose_comparison_base(
    *, explicit: str | None, pull_request_target: str | None, default_branch: str | None
) -> RuntimeResult:
    for candidate in (explicit, pull_request_target, default_branch):
        if candidate:
            return ok(candidate)
    return failure("comparison_base_required", "branch comparison base cannot be determined uniquely")

def requires_full_review(changed_dimensions: set[str]) -> bool:
    return bool(changed_dimensions & {
        "structure", "assumptions", "order", "dependencies", "completion", "specification",
        "scope_topology",
    })

def resolve_input(
    root: Path,
    *,
    review_id: str,
    plan_key: str | None = None,
    run_id: str | None = None,
    branch: str | None = None,
    base: str | None = None,
    head: str | None = None,
    spec_paths: list[str] | None = None,
) -> RuntimeResult:
    if plan_key is not None or run_id is not None:
        if plan_key is None or run_id is None:
            return failure("execution_input_incomplete", "plan key and run id must be supplied together")
        store = root.resolve() / ".agents/evidence" / plan_key / run_id
        binding_path = store / "binding.json"
        if binding_path.is_symlink() or not binding_path.is_file():
            return failure("execution_input_unavailable", "implementation binding is unavailable")
        try:
            implementation = json.loads(binding_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return failure("execution_input_invalid", "implementation binding is invalid")
        completed = sorted(store.glob("*-all-steps-complete.json"))
        if not completed:
            return failure("implementation_incomplete", "implementation has no all-steps-complete event")
        sequence = int(completed[-1].name.split("-", 1)[0])
        try:
            return ok(execution_binding(plan_key, run_id, implementation["approval_commit"], implement_sequence=sequence))
        except (KeyError, ValueError):
            return failure("execution_input_invalid", "implementation binding cannot start review")
    if base is None or head is None:
        return failure("commit_input_incomplete", "standalone review needs base and head commits")
    try:
        return ok(standalone_binding(
            review_id, base=base, head=head, branch=branch, spec_paths=spec_paths or ["docs/spec/"]
        ))
    except ValueError as error:
        return failure("standalone_input_invalid", str(error))

def review_directory(root: Path, binding: dict) -> Path:
    repository = root.resolve()
    if binding["kind"] == "execution":
        path = repository / ".agents/evidence" / binding["plan_key"] / binding["run_id"] / "review"
    else:
        path = repository / ".agents/evidence/reviews" / binding["review_id"]
    cursor = repository
    for part in path.relative_to(repository).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"symlink is not allowed: {cursor}")
    return path

def _write_once(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def append_event(root: Path, binding: dict, event_type: str, fields: dict) -> RuntimeResult:
    directory = review_directory(root, binding)
    sequence = len(list(directory.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json"))) + 1 if directory.exists() else 1
    event = {"version": 1, "sequence": sequence, "event_type": event_type, **fields}
    if any("identity" in key.lower() for key in event):
        return failure("identity_field_forbidden", "review identity chains are not supported")
    if sequence > 1:
        previous_path = sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json"))[-1]
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        if not review_model.can_append_after(previous):
            return failure("review_already_completed", "completed review cannot be extended")
    try:
        _write_once(directory / f"{sequence:06d}-{event_type}.json", event)
    except FileExistsError:
        return failure("event_collision", "review event sequence already exists")
    return ok(event)

def load_events(root: Path, binding: dict) -> RuntimeResult:
    directory = review_directory(root, binding)
    events: list[dict] = []
    for path in sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")) if directory.is_dir() else []:
        try:
            events.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            return failure("review_event_invalid", f"invalid review event: {path.name}")
    return ok(events)

def begin_stage(root: Path, binding: dict, findings: list[dict]) -> RuntimeResult:
    events = load_events(root, binding)
    if not events.ok:
        return events
    stage = review_model.next_review_stage(events.value, findings)
    if stage == "complete":
        return ok({"event_type": "review-complete"})
    return append_event(root, binding, f"{stage}-review", {"input_kind": input_kind(binding)})

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review evidence runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    bind = commands.add_parser("bind")
    bind.add_argument("--repo", required=True)
    bind.add_argument("--review-id", required=True)
    bind.add_argument("--plan-key")
    bind.add_argument("--run-id")
    bind.add_argument("--branch")
    bind.add_argument("--base")
    bind.add_argument("--head")
    bind.add_argument("--spec-path", action="append", default=[])
    args = parser.parse_args(argv)
    binding = resolve_input(
        Path(args.repo), review_id=args.review_id, plan_key=args.plan_key, run_id=args.run_id,
        branch=args.branch, base=args.base, head=args.head, spec_paths=args.spec_path,
    )
    if not binding.ok:
        parser.error(binding.error.message)
    stage = begin_stage(Path(args.repo), binding.value, [])
    if not stage.ok:
        parser.error(stage.error.message)
    print(json.dumps({"input": binding.value, "stage": stage.value}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
