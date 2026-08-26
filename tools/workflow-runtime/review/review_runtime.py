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
        "structure", "assumptions", "order", "dependencies", "completion", "specification"
    })

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

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review evidence runtime")
    parser.parse_args(argv)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
