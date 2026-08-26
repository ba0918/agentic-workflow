#!/usr/bin/env python3
"""Git-bound review input validation and append-only review state transitions."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
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

def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)

def _commit(root: Path, reference: str | None) -> RuntimeResult:
    if not reference:
        return failure("commit_not_found", "Git commit reference is missing")
    result = _git(root, "rev-parse", "--verify", f"{reference}^{{commit}}")
    value = result.stdout.strip()
    if result.returncode != 0 or COMMIT.fullmatch(value) is None:
        return failure("commit_not_found", f"Git commit does not exist: {reference}")
    return ok(value)

def execution_binding(
    plan_key: str, run_id: str, approval_commit: str, *, implement_sequence: int,
    branch: str | None = None, head: str | None = None, worktree: str | None = None,
) -> dict:
    if SAFE_ID.fullmatch(plan_key) is None or SAFE_ID.fullmatch(run_id) is None or COMMIT.fullmatch(approval_commit) is None:
        raise ValueError("unsafe execution binding")
    return {
        "kind": "execution", "plan_key": plan_key, "run_id": run_id,
        "approval_commit": approval_commit, "implement_sequence": implement_sequence,
        "branch": branch, "head": head, "worktree": worktree,
    }

def standalone_binding(
    review_id: str, *, base: str, head: str, spec_paths: list[str], branch: str | None = None,
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
        "kind": "standalone", "review_id": review_id,
        "input": {"kind": "branch" if branch else "commits", "branch": branch, "base": base, "head": head},
        "spec_paths": sorted(spec_paths), "spec_commit": head,
    }

def input_kind(binding: dict) -> str:
    return "execution" if binding.get("kind") == "execution" else binding.get("input", {}).get("kind", "unknown")

def choose_comparison_base(
    *, explicit: str | None, pull_request_target: str | None, default_branch: str | None,
) -> RuntimeResult:
    for candidate in (explicit, pull_request_target, default_branch):
        if candidate:
            return ok(candidate)
    return failure("comparison_base_required", "branch comparison base cannot be determined uniquely")

def _default_branch(root: Path) -> RuntimeResult:
    remote = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if remote.returncode == 0 and remote.stdout.strip():
        return ok(remote.stdout.strip())
    candidates: set[str] = set()
    for name in ("main", "master", "trunk"):
        if _git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0:
            candidates.add(name)
    if len(candidates) != 1:
        return failure("comparison_base_required", "default branch is not unique")
    return ok(next(iter(candidates)))

def requires_full_review(changed_dimensions: set[str]) -> bool:
    return bool(changed_dimensions & {
        "structure", "assumptions", "order", "dependencies", "completion", "specification", "scope_topology",
    })

def _implementation_events(store: Path) -> RuntimeResult:
    events: list[dict] = []
    paths = sorted(store.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json"))
    for expected, path in enumerate(paths, 1):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return failure("execution_input_invalid", f"invalid implementation event: {path.name}")
        if event.get("sequence") != expected or not path.name.startswith(f"{expected:06d}-{event.get('event_type')}"):
            return failure("execution_input_invalid", "implementation evidence is not contiguous")
        events.append(event)
    return ok(events)

def _validate_execution_input(root: Path, plan_key: str, run_id: str) -> RuntimeResult:
    if SAFE_ID.fullmatch(plan_key) is None or SAFE_ID.fullmatch(run_id) is None:
        return failure("execution_input_invalid", "implementation identifiers are unsafe")
    store = root.resolve() / ".agents/evidence" / plan_key / run_id
    binding_path = store / "binding.json"
    if binding_path.is_symlink() or not binding_path.is_file():
        return failure("execution_input_unavailable", "implementation binding is unavailable")
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return failure("execution_input_invalid", "implementation binding is invalid")
    if binding.get("plan_key") != plan_key or binding.get("run_id") != run_id:
        return failure("execution_input_invalid", "implementation binding and path differ")
    approval = _commit(root, binding.get("approval_commit"))
    if not approval.ok:
        return failure("execution_input_invalid", "implementation approval commit does not exist")
    loaded = _implementation_events(store)
    if not loaded.ok:
        return loaded
    events = loaded.value
    if not events or events[-1].get("event_type") != "implementation_green":
        return failure("implementation_incomplete", "last implementation event is not implementation_green")
    step_ids = [step.get("id") for step in binding.get("steps", [])]
    if not step_ids or events[-1].get("completed_steps") != step_ids:
        return failure("execution_input_invalid", "implementation_green does not cover the bound steps")
    commits = [event for event in events if event.get("event_type") == "commit"]
    for step in binding["steps"]:
        step_events = [event for event in events if event.get("step") == step["id"]]
        required = "refactor" if step.get("completion") == "test" else step.get("completion")
        evidence = next((event for event in reversed(step_events) if event.get("event_type") == required), None)
        if evidence is None or not isinstance(evidence.get("safety"), dict):
            return failure("execution_input_invalid", f"implementation step evidence is incomplete: {step['id']}")
        commit_required = step.get("completion") in {"test", "artifact"} or bool(evidence.get("changed_paths"))
        step_commits = [event for event in step_events if event.get("event_type") == "commit"]
        if commit_required and not step_commits:
            return failure("execution_input_invalid", f"implementation step commit is missing: {step['id']}")
        if any(not isinstance(event.get("safety"), dict) for event in step_commits):
            return failure("execution_input_invalid", f"implementation commit safety is missing: {step['id']}")
    worktree = Path(str(binding.get("worktree", "")))
    branch = binding.get("branch")
    if not worktree.is_dir() or _git(worktree, "branch", "--show-current").stdout.strip() != branch:
        return failure("execution_input_invalid", "implementation worktree and branch do not match")
    if _git(worktree, "status", "--porcelain").stdout.strip():
        return failure("execution_input_invalid", "implementation worktree is no longer clean")
    root_common = _git(root, "rev-parse", "--git-common-dir")
    worktree_common = _git(worktree, "rev-parse", "--git-common-dir")
    if root_common.returncode != 0 or worktree_common.returncode != 0:
        return failure("execution_input_invalid", "implementation worktree is not a Git worktree")
    root_common_path = (root / root_common.stdout.strip()).resolve()
    worktree_common_path = (worktree / worktree_common.stdout.strip()).resolve()
    if root_common_path != worktree_common_path:
        return failure("execution_input_invalid", "implementation worktree belongs to another repository")
    branch_head = _commit(root, branch)
    last_commit = commits[-1].get("commit") if commits else None
    if any(not _commit(root, event.get("commit")).ok for event in commits):
        return failure("execution_input_invalid", "implementation evidence names a missing commit")
    if not branch_head.ok or branch_head.value != last_commit:
        return failure("execution_input_invalid", "implementation branch tip and commit evidence differ")
    try:
        return ok(execution_binding(
            plan_key, run_id, approval.value, implement_sequence=events[-1]["sequence"],
            branch=branch, head=branch_head.value, worktree=str(worktree.resolve()),
        ))
    except (KeyError, ValueError):
        return failure("execution_input_invalid", "implementation binding cannot start review")

def resolve_input(
    root: Path, *, review_id: str, plan_key: str | None = None, run_id: str | None = None,
    branch: str | None = None, base: str | None = None, head: str | None = None,
    pull_request_target: str | None = None, spec_paths: list[str] | None = None,
) -> RuntimeResult:
    repository = root.resolve()
    if plan_key is not None or run_id is not None:
        if plan_key is None or run_id is None:
            return failure("execution_input_incomplete", "plan key and run id must be supplied together")
        return _validate_execution_input(repository, plan_key, run_id)
    if branch is not None:
        branch_head = _commit(repository, f"refs/heads/{branch}")
        if not branch_head.ok:
            return failure("branch_not_found", f"branch does not exist: {branch}")
        default = None
        if base is None and pull_request_target is None:
            selected_default = _default_branch(repository)
            if not selected_default.ok:
                return selected_default
            default = selected_default.value
        selected = choose_comparison_base(
            explicit=base, pull_request_target=pull_request_target, default_branch=default,
        )
        if not selected.ok:
            return selected
        target = _commit(repository, selected.value)
        if not target.ok:
            return target
        merge_base = _git(repository, "merge-base", target.value, branch_head.value)
        if merge_base.returncode != 0 or COMMIT.fullmatch(merge_base.stdout.strip()) is None:
            return failure("comparison_base_required", "branch and target have no merge base")
        if head is not None:
            supplied_head = _commit(repository, head)
            if not supplied_head.ok or supplied_head.value != branch_head.value:
                return failure("branch_head_mismatch", "supplied head differs from branch tip")
        try:
            return ok(standalone_binding(
                review_id, branch=branch, base=merge_base.stdout.strip(), head=branch_head.value,
                spec_paths=spec_paths or ["docs/spec/"],
            ))
        except ValueError as error:
            return failure("standalone_input_invalid", str(error))
    if base is None or head is None:
        return failure("commit_input_incomplete", "two-commit review needs base and head")
    resolved_base = _commit(repository, base)
    resolved_head = _commit(repository, head)
    if not resolved_base.ok:
        return resolved_base
    if not resolved_head.ok:
        return resolved_head
    try:
        return ok(standalone_binding(
            review_id, base=resolved_base.value, head=resolved_head.value,
            spec_paths=spec_paths or ["docs/spec/"],
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
    loaded = load_events(root, binding)
    if not loaded.ok:
        return loaded
    if review_model.review_complete(loaded.value, current_findings(loaded.value)):
        return failure("review_already_completed", "completed review cannot be extended")
    sequence = len(loaded.value) + 1
    event = {"version": 1, "sequence": sequence, "event_type": event_type, **fields}
    if any("identity" in key.lower() for key in event):
        return failure("identity_field_forbidden", "review identity chains are not supported")
    try:
        _write_once(directory / f"{sequence:06d}-{event_type}.json", event)
    except FileExistsError:
        return failure("event_collision", "review event sequence already exists")
    return ok(event)

def load_events(root: Path, binding: dict) -> RuntimeResult:
    directory = review_directory(root, binding)
    events: list[dict] = []
    paths = sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")) if directory.is_dir() else []
    for expected, path in enumerate(paths, 1):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return failure("review_event_invalid", f"invalid review event: {path.name}")
        if event.get("sequence") != expected or not path.name.startswith(f"{expected:06d}-{event.get('event_type')}"):
            return failure("review_event_invalid", "review event sequence is invalid")
        events.append(event)
    return ok(events)

def bind_review(root: Path, binding: dict, *, model: str) -> RuntimeResult:
    if not model.strip():
        return failure("review_model_required", "review model must be recorded")
    directory = review_directory(root, binding)
    try:
        _write_once(directory / "binding.json", binding)
    except FileExistsError:
        return failure("review_collision", "review binding already exists")
    return append_event(root, binding, "review-bound", {"model": model, "input_kind": input_kind(binding)})

def current_findings(events: list[dict]) -> list[dict]:
    findings: dict[str, dict] = {}
    for event in events:
        if event.get("event_type") in {"initial-findings-recorded", "final-findings-recorded", "findings-added"}:
            for item in event.get("findings", []):
                findings[item["id"]] = dict(item)
        elif (
            event.get("event_type") == "targeted-review-result"
            and event.get("oracle_exit_code") == 0
            and event.get("finding_id") in findings
        ):
            findings[event["finding_id"]]["state"] = "closed"
    return list(findings.values())

def begin_stage(root: Path, binding: dict, *, reviewer_context: str) -> RuntimeResult:
    events_result = load_events(root, binding)
    if not events_result.ok:
        return events_result
    events = events_result.value
    if not events or events[0].get("event_type") != "review-bound":
        return failure("review_not_bound", "review input must be bound first")
    if events[-1].get("event_type") == "findings_stale":
        return failure("findings_stale", "review findings need a human-approved rebound")
    initial_started = next((event for event in events if event.get("event_type") == "initial-full-review-started"), None)
    initial_results = any(event.get("event_type") == "initial-findings-recorded" for event in events)
    final_started = next((event for event in events if event.get("event_type") == "final-full-review-started"), None)
    final_results = any(event.get("event_type") == "final-findings-recorded" for event in events)
    if initial_started is None:
        return append_event(root, binding, "initial-full-review-started", {"reviewer_context": reviewer_context})
    if not initial_results:
        return failure("stage_results_required", "initial full review results must be recorded")
    findings = current_findings(events)
    if any(item.get("state") == "open" for item in findings):
        targeted_positions = [index for index, event in enumerate(events) if event.get("event_type") == "targeted-review-started"]
        if targeted_positions:
            latest = targeted_positions[-1]
            required_ids = set(events[latest].get("finding_ids", []))
            result_ids = {
                event.get("finding_id") for event in events[latest + 1:]
                if event.get("event_type") == "targeted-review-result"
            }
        else:
            required_ids = result_ids = set()
        if required_ids - result_ids:
            return failure("stage_results_required", "targeted review must update findings before another stage")
        return append_event(root, binding, "targeted-review-started", {
            "reviewer_context": reviewer_context,
            "finding_ids": sorted(item["id"] for item in findings if item.get("state") == "open"),
        })
    if final_started is None:
        targeted_positions = [index for index, event in enumerate(events) if event.get("event_type") == "targeted-review-started"]
        if targeted_positions and not any(
            event.get("event_type") == "progress-assessed" for event in events[targeted_positions[-1] + 1:]
        ):
            return failure("progress_assessment_required", "targeted convergence needs lexicographic progress evidence")
        if reviewer_context == initial_started.get("reviewer_context"):
            return failure("fresh_context_required", "final full review needs a different context")
        return append_event(root, binding, "final-full-review-started", {"reviewer_context": reviewer_context})
    if not final_results:
        return failure("stage_results_required", "final full review results must be recorded")
    if any(item.get("state") == "open" for item in current_findings(events)):
        return append_event(root, binding, "targeted-review-started", {
            "reviewer_context": reviewer_context,
            "finding_ids": sorted(item["id"] for item in current_findings(events) if item.get("state") == "open"),
        })
    return ok({"event_type": "ready-to-complete"})

def record_findings(
    root: Path, binding: dict, *, stage: str, findings: list[dict], safety_check: bool,
    reviewer_context: str,
) -> RuntimeResult:
    if stage not in {"initial", "final"} or safety_check is not True:
        return failure("safety_check_required", "initial and final review require a completed safety check")
    events = load_events(root, binding)
    if not events.ok:
        return events
    start_type = f"{stage}-full-review-started"
    result_type = f"{stage}-findings-recorded"
    start = next((event for event in reversed(events.value) if event.get("event_type") == start_type), None)
    if start is None or start.get("reviewer_context") != reviewer_context:
        return failure("review_context_mismatch", "finding results must match their review context")
    if any(event.get("event_type") == result_type for event in events.value):
        return failure("findings_already_recorded", "stage findings are append-only")
    ids: set[str] = set()
    for item in findings:
        checked = review_model.validate_finding(item)
        if not checked.ok:
            return failure(checked.error.code, checked.error.message)
        if item["id"] in ids:
            return failure("finding_duplicate", "finding ids must be unique")
        if (item["severity"] == "info" and item["state"] != "closed") or (
            item["severity"] != "info" and item["state"] != "open"
        ):
            return failure("finding_state_invalid", "new fixable findings are open and info observations are closed")
        ids.add(item["id"])
    return append_event(root, binding, result_type, {
        "findings": findings, "safety_check": True, "reviewer_context": reviewer_context,
    })

def _commit_has_trailer(root: Path, commit: str, finding_id: str) -> bool:
    resolved = _commit(root, commit)
    if not resolved.ok:
        return False
    message = _git(root, "show", "-s", "--format=%B", resolved.value).stdout
    return re.search(rf"(?m)^Finding:\s*{re.escape(finding_id)}\s*$", message) is not None

def close_finding(
    root: Path, binding: dict, finding_id: str, *, oracle_exit_code: int, fix_commits: list[str],
) -> RuntimeResult:
    events = load_events(root, binding)
    if not events.ok:
        return events
    item = next((candidate for candidate in current_findings(events.value) if candidate["id"] == finding_id), None)
    if item is None or item.get("state") != "open":
        return failure("finding_not_open", "only an open admitted finding can close")
    targeted = [
        (index, event) for index, event in enumerate(events.value)
        if event.get("event_type") == "targeted-review-started" and finding_id in event.get("finding_ids", [])
    ]
    if not targeted:
        return failure("targeted_review_required", "finding can close only after its targeted review starts")
    latest_index, _ = targeted[-1]
    if any(
        event.get("event_type") == "targeted-review-result" and event.get("finding_id") == finding_id
        for event in events.value[latest_index + 1:]
    ):
        return failure("targeted_result_exists", "targeted review already recorded this finding result")
    if oracle_exit_code != 0:
        return failure("finding_oracle_failed", "finding oracle still fails")
    if not fix_commits or any(not _commit_has_trailer(root, commit, finding_id) for commit in fix_commits):
        return failure("fix_commit_unlinked", "every fix commit must exist and carry the finding trailer")
    return append_event(root, binding, "targeted-review-result", {
        "finding_id": finding_id, "oracle_exit_code": oracle_exit_code, "fix_commits": fix_commits,
    })

def record_targeted_result(
    root: Path, binding: dict, finding_id: str, *, oracle_exit_code: int, fix_commits: list[str],
) -> RuntimeResult:
    if oracle_exit_code == 0:
        return close_finding(
            root, binding, finding_id, oracle_exit_code=oracle_exit_code, fix_commits=fix_commits,
        )
    events = load_events(root, binding)
    if not events.ok:
        return events
    targeted = [
        (index, event) for index, event in enumerate(events.value)
        if event.get("event_type") == "targeted-review-started" and finding_id in event.get("finding_ids", [])
    ]
    if not targeted:
        return failure("targeted_review_required", "finding result needs a corresponding targeted review")
    latest_index, _ = targeted[-1]
    if any(
        event.get("event_type") == "targeted-review-result" and event.get("finding_id") == finding_id
        for event in events.value[latest_index + 1:]
    ):
        return failure("targeted_result_exists", "targeted review already recorded this finding result")
    if any(not _commit_has_trailer(root, commit, finding_id) for commit in fix_commits):
        return failure("fix_commit_unlinked", "every fix commit must exist and carry the finding trailer")
    return append_event(root, binding, "targeted-review-result", {
        "finding_id": finding_id, "oracle_exit_code": oracle_exit_code, "fix_commits": fix_commits,
    })

def add_findings(root: Path, binding: dict, *, candidates: list[dict], related_ids: set[str]) -> RuntimeResult:
    events = load_events(root, binding)
    if not events.ok:
        return events
    existing_ids = {item["id"] for item in current_findings(events.value)}
    for item in candidates:
        checked = review_model.validate_finding(item)
        if not checked.ok:
            return failure(checked.error.code, checked.error.message)
    admitted, observations = review_model.admit_new_findings(candidates, related_ids)
    if any(item["id"] in existing_ids for item in admitted):
        return failure("finding_duplicate", "an admitted finding id already exists")
    return append_event(root, binding, "findings-added", {
        "findings": admitted, "terminal_observations": observations,
    })

def record_progress(root: Path, binding: dict) -> RuntimeResult:
    events = load_events(root, binding)
    if not events.ok:
        return events
    positions = [index for index, event in enumerate(events.value) if event.get("event_type") == "targeted-review-started"]
    if not positions:
        return failure("targeted_review_required", "progress needs a targeted review event range")
    latest = positions[-1]
    finding_ids = set(events.value[latest].get("finding_ids", []))
    result_ids = {
        event.get("finding_id") for event in events.value[latest + 1:]
        if event.get("event_type") == "targeted-review-result"
    }
    if finding_ids - result_ids:
        return failure("targeted_results_required", "progress needs every targeted finding result")
    before = current_findings(events.value[:latest])
    after = current_findings(events.value)
    progressed = review_model.made_progress(before, after)
    stalled = 0
    for event in reversed(events.value):
        if event.get("event_type") == "progress-assessed":
            if event.get("progressed") is True:
                break
            stalled += 1
    actions = ("diagnose", "change_method", "human_judgment")
    next_action = "continue" if progressed else actions[min(stalled, len(actions) - 1)]
    return append_event(root, binding, "progress-assessed", {
        "before": review_model.open_counts(before), "after": review_model.open_counts(after),
        "progressed": progressed, "next_action": next_action,
    })

def mark_stale(root: Path, binding: dict, *, reason: str) -> RuntimeResult:
    if not reason.strip():
        return failure("stale_reason_required", "findings_stale needs a consequential change reason")
    return append_event(root, binding, "findings_stale", {"reason": reason})

def rebound_findings(root: Path, binding: dict, *, spec_commit: str, reason: str) -> RuntimeResult:
    events = load_events(root, binding)
    if not events.ok or not events.value or events.value[-1].get("event_type") != "findings_stale":
        return failure("findings_not_stale", "only stale findings can rebound")
    resolved = _commit(root, spec_commit)
    if not resolved.ok or not reason.strip():
        return failure("rebound_invalid", "rebound needs an existing specification commit and reason")
    return append_event(root, binding, "findings-rebound", {"spec_commit": resolved.value, "reason": reason})

def complete_review(root: Path, binding: dict) -> RuntimeResult:
    events = load_events(root, binding)
    if not events.ok:
        return events
    if not any(event.get("event_type") == "final-full-review-started" for event in events.value):
        return failure("final_review_required", "final full review has not started")
    if not any(event.get("event_type") == "final-findings-recorded" for event in events.value):
        return failure("final_results_required", "final full review results are missing")
    if any(item.get("state") == "open" for item in current_findings(events.value)):
        return failure("findings_open", "all admitted findings must close")
    targeted_positions = [index for index, event in enumerate(events.value) if event.get("event_type") == "targeted-review-started"]
    if targeted_positions and not any(
        event.get("event_type") == "progress-assessed" for event in events.value[targeted_positions[-1] + 1:]
    ):
        return failure("progress_assessment_required", "targeted convergence needs lexicographic progress evidence")
    if events.value[-1].get("event_type") == "findings_stale":
        return failure("findings_stale", "stale findings cannot complete")
    return ok({"event_type": "review-complete", "verdict": "pass"})

def load_review_binding(
    root: Path, *, review_id: str | None = None, plan_key: str | None = None, run_id: str | None = None,
) -> RuntimeResult:
    if plan_key is not None or run_id is not None:
        if not plan_key or not run_id:
            return failure("review_selector_invalid", "plan key and run id must be supplied together")
        path = root.resolve() / ".agents/evidence" / plan_key / run_id / "review/binding.json"
    elif review_id:
        path = root.resolve() / ".agents/evidence/reviews" / review_id / "binding.json"
    else:
        return failure("review_selector_invalid", "review id or implementation run is required")
    if path.is_symlink() or not path.is_file():
        return failure("review_not_bound", "review binding is unavailable")
    try:
        return ok(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return failure("review_not_bound", "review binding is invalid")

def _selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True)
    parser.add_argument("--review-id")
    parser.add_argument("--plan-key")
    parser.add_argument("--run-id")

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
    bind.add_argument("--pull-request-target")
    bind.add_argument("--spec-path", action="append", default=[])
    bind.add_argument("--model", required=True)
    bind.add_argument("--reviewer-context", required=True)
    begin = commands.add_parser("begin")
    _selector(begin)
    begin.add_argument("--reviewer-context", required=True)
    findings = commands.add_parser("record-findings")
    _selector(findings)
    findings.add_argument("--stage", choices=("initial", "final"), required=True)
    findings.add_argument("--reviewer-context", required=True)
    findings.add_argument("--findings-file", required=True)
    additions = commands.add_parser("add-findings")
    _selector(additions)
    additions.add_argument("--findings-file", required=True)
    additions.add_argument("--related-id", action="append", default=[])
    close = commands.add_parser("close-finding")
    _selector(close)
    close.add_argument("--finding-id", required=True)
    close.add_argument("--oracle-exit-code", type=int, required=True)
    close.add_argument("--fix-commit", action="append", default=[])
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
    args = parser.parse_args(argv)
    root = Path(args.repo)
    if args.command == "bind":
        binding = resolve_input(
            root, review_id=args.review_id, plan_key=args.plan_key, run_id=args.run_id,
            branch=args.branch, base=args.base, head=args.head, pull_request_target=args.pull_request_target,
            spec_paths=args.spec_path,
        )
        if not binding.ok:
            parser.error(binding.error.message)
        bound = bind_review(root, binding.value, model=args.model)
        if not bound.ok:
            parser.error(bound.error.message)
        stage = begin_stage(root, binding.value, reviewer_context=args.reviewer_context)
        if not stage.ok:
            parser.error(stage.error.message)
        print(json.dumps({"input": binding.value, "stage": stage.value}, ensure_ascii=False))
        return 0
    binding = load_review_binding(
        root, review_id=args.review_id, plan_key=args.plan_key, run_id=args.run_id,
    )
    if not binding.ok:
        parser.error(binding.error.message)
    if args.command == "begin":
        result = begin_stage(root, binding.value, reviewer_context=args.reviewer_context)
    elif args.command == "record-findings":
        result = record_findings(
            root, binding.value, stage=args.stage,
            findings=json.loads(Path(args.findings_file).read_text(encoding="utf-8")),
            safety_check=True, reviewer_context=args.reviewer_context,
        )
    elif args.command == "add-findings":
        result = add_findings(
            root, binding.value,
            candidates=json.loads(Path(args.findings_file).read_text(encoding="utf-8")),
            related_ids=set(args.related_id),
        )
    elif args.command == "close-finding":
        result = close_finding(
            root, binding.value, args.finding_id,
            oracle_exit_code=args.oracle_exit_code, fix_commits=args.fix_commit,
        )
    elif args.command == "progress":
        result = record_progress(root, binding.value)
    elif args.command == "stale":
        result = mark_stale(root, binding.value, reason=args.reason)
    elif args.command == "rebound":
        result = rebound_findings(root, binding.value, spec_commit=args.spec_commit, reason=args.reason)
    else:
        result = complete_review(root, binding.value)
    if not result.ok:
        parser.error(result.error.message)
    print(json.dumps(result.value, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
