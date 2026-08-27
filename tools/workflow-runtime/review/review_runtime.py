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
import sys

SHARED_DIR = Path(__file__).resolve().parents[1] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
import implementation_evidence

try:
    from secret_detect import contains_secret
except ModuleNotFoundError:
    IMPLEMENT_RUNTIME = Path(__file__).resolve().parents[1] / "implement/runtime"
    if str(IMPLEMENT_RUNTIME) not in sys.path:
        sys.path.insert(0, str(IMPLEMENT_RUNTIME))
    from secret_detect import contains_secret

import review_model

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
COMMIT = re.compile(r"[0-9a-f]{40,64}")
PROFILES = {"default", "document", "skill"}

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
        "version": 2, "kind": "execution", "plan_key": plan_key, "run_id": run_id,
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
        "version": 2, "kind": "standalone", "review_id": review_id,
        "input": {"kind": "branch" if branch else "commits", "branch": branch, "base": base, "head": head},
        "spec_paths": sorted(spec_paths), "spec_commit": head,
    }

def input_kind(binding: dict) -> str:
    return "execution" if binding.get("kind") == "execution" else binding.get("input", {}).get("kind", "unknown")

def _validate_review_binding(binding: object) -> RuntimeResult:
    if not isinstance(binding, dict) or binding.get("version") != 2:
        return failure("review_binding_invalid", "review binding must be a version 2 object")
    if binding.get("kind") == "execution":
        if (
            SAFE_ID.fullmatch(str(binding.get("plan_key", ""))) is None
            or SAFE_ID.fullmatch(str(binding.get("run_id", ""))) is None
            or COMMIT.fullmatch(str(binding.get("approval_commit", ""))) is None
            or not isinstance(binding.get("implement_sequence"), int)
        ):
            return failure("review_binding_invalid", "execution review binding is invalid")
        return ok(binding)
    if binding.get("kind") != "standalone" or SAFE_ID.fullmatch(str(binding.get("review_id", ""))) is None:
        return failure("review_binding_invalid", "standalone review binding is invalid")
    review_input = binding.get("input")
    if (
        not isinstance(review_input, dict) or review_input.get("kind") not in {"branch", "commits"}
        or COMMIT.fullmatch(str(review_input.get("base", ""))) is None
        or COMMIT.fullmatch(str(review_input.get("head", ""))) is None
        or COMMIT.fullmatch(str(binding.get("spec_commit", ""))) is None
        or not isinstance(binding.get("spec_paths"), list)
    ):
        return failure("review_binding_invalid", "standalone review commit binding is invalid")
    if review_input["kind"] == "branch" and not isinstance(review_input.get("branch"), str):
        return failure("review_binding_invalid", "branch review binding is invalid")
    for path in binding["spec_paths"]:
        candidate = PurePosixPath(path) if isinstance(path, str) else PurePosixPath("/")
        if candidate.is_absolute() or ".." in candidate.parts:
            return failure("review_binding_invalid", "review specification path is invalid")
    return ok(binding)

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
        if event.get("version") != 2:
            return failure("execution_input_invalid", "implementation event version must be 2")
        if event.get("sequence") != expected or not path.name.startswith(f"{expected:06d}-{event.get('event_type')}"):
            return failure("execution_input_invalid", "implementation evidence is not contiguous")
        events.append(event)
    return ok(events)

def _validate_implementation_segments(
    root: Path, start_commit: str, segments: list[dict], branch_head: str,
) -> RuntimeResult:
    history = _git(root, "rev-list", "--reverse", f"{start_commit}..{branch_head}")
    if history.returncode != 0:
        return failure("execution_input_invalid", "implementation revision range is unavailable")
    commits = [commit for segment in segments for commit in segment.get("commits", [])]
    document_boundaries = {segment.get("approval_commit") for segment in segments[1:]}
    implementation_history = [
        commit for commit in filter(None, history.stdout.splitlines()) if commit not in document_boundaries
    ]
    if implementation_history != commits:
        return failure("execution_input_invalid", "implementation revision range and evidence differ")
    return ok()

def _changed_paths(root: Path, start: str, end: str) -> RuntimeResult:
    result = _git(root, "diff", "--name-only", start, end)
    if result.returncode != 0:
        return failure("execution_input_invalid", "implementation changed paths are unavailable")
    return ok(sorted(filter(None, result.stdout.splitlines())))

def _uncommitted_paths(worktree: Path) -> RuntimeResult:
    result = _git(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if result.returncode != 0:
        return failure("execution_input_invalid", "implementation worktree status is unavailable")
    return ok(sorted({line[3:] for line in result.stdout.splitlines() if len(line) >= 4}))

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
    loaded = _implementation_events(store)
    if not loaded.ok:
        return loaded
    events = loaded.value
    if not events or events[-1].get("event_type") != "implementation_green":
        return failure("implementation_incomplete", "last implementation event is not implementation_green")
    derived = implementation_evidence.derive_implementation(binding, events[:-1])
    if not derived.ok:
        return failure(derived.error.code, derived.error.message)
    approval = _commit(root, derived.value["approval_commit"])
    if not approval.ok:
        return failure("execution_input_invalid", "effective implementation approval commit does not exist")
    step_ids = [step["id"] for step in derived.value["steps"]]
    if derived.value["resume_step"] is not None or events[-1].get("completed_steps") != step_ids:
        return failure("execution_input_invalid", "implementation_green does not cover the bound steps")
    commits = [event for event in events if event.get("event_type") == "commit"]
    worktree = Path(str(binding.get("worktree", "")))
    branch = binding.get("branch")
    if not worktree.is_dir() or _git(worktree, "branch", "--show-current").stdout.strip() != branch:
        return failure("execution_input_invalid", "implementation worktree and branch do not match")
    root_common = _git(root, "rev-parse", "--git-common-dir")
    worktree_common = _git(worktree, "rev-parse", "--git-common-dir")
    if root_common.returncode != 0 or worktree_common.returncode != 0:
        return failure("execution_input_invalid", "implementation worktree is not a Git worktree")
    root_common_path = (root / root_common.stdout.strip()).resolve()
    worktree_common_path = (worktree / worktree_common.stdout.strip()).resolve()
    if root_common_path != worktree_common_path:
        return failure("execution_input_invalid", "implementation worktree belongs to another repository")
    branch_head = _commit(root, f"refs/heads/{branch}")
    if any(not _commit(root, event.get("commit")).ok for event in commits):
        return failure("execution_input_invalid", "implementation evidence names a missing commit")
    if not branch_head.ok:
        return failure("execution_input_invalid", "implementation branch tip is unavailable")
    segment_check = _validate_implementation_segments(
        root, binding.get("approval_commit", ""), derived.value["segments"], branch_head.value,
    )
    if not segment_check.ok:
        return segment_check
    changed = _changed_paths(root, binding["approval_commit"], branch_head.value)
    dirty = _uncommitted_paths(worktree)
    if not changed.ok or not dirty.ok:
        return changed if not changed.ok else dirty
    dirty_in_scope = sorted(set(dirty.value) & set(changed.value))
    if dirty_in_scope:
        return failure("review_scope_dirty", "reviewed implementation paths have uncommitted changes")
    try:
        resolved = execution_binding(
            plan_key, run_id, approval.value, implement_sequence=events[-1]["sequence"],
            branch=branch, head=branch_head.value, worktree=str(worktree.resolve()),
        )
        resolved["uncommitted_outside_scope"] = sorted(set(dirty.value) - set(changed.value))
        return ok(resolved)
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
    checked = _validate_review_binding(binding)
    if not checked.ok:
        raise ValueError(checked.error.message)
    if binding["kind"] == "execution":
        path = repository / ".agents/evidence" / binding["plan_key"] / binding["run_id"] / "review"
    else:
        path = repository / ".agents/evidence/reviews" / binding["review_id"]
    cursor = repository
    for part in path.relative_to(repository).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"symlink is not allowed: {cursor}")
    resolved = path.resolve()
    evidence_root = (repository / ".agents/evidence").resolve()
    if not resolved.is_relative_to(evidence_root):
        raise ValueError("review directory is outside the evidence store")
    return resolved

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
    try:
        directory = review_directory(root, binding)
    except ValueError:
        return failure("review_binding_invalid", "review directory is invalid")
    loaded = load_events(root, binding)
    if not loaded.ok:
        return loaded
    if _findings_stale(loaded.value) and event_type != "findings-rebound":
        return failure("findings_stale", "stale findings allow only a human-approved rebound")
    if review_model.review_complete(loaded.value, current_findings(loaded.value)):
        return failure("review_already_completed", "completed review cannot be extended")
    safe_fields = _safe_finding_strings(fields, field="event")
    if not safe_fields.ok:
        return safe_fields
    sequence = len(loaded.value) + 1
    event = {"version": 2, "sequence": sequence, "event_type": event_type, **fields}
    if any("identity" in key.lower() for key in event):
        return failure("identity_field_forbidden", "review identity chains are not supported")
    try:
        _write_once(directory / f"{sequence:06d}-{event_type}.json", event)
    except FileExistsError:
        return failure("event_collision", "review event sequence already exists")
    return ok(event)

def load_events(root: Path, binding: dict) -> RuntimeResult:
    try:
        directory = review_directory(root, binding)
    except ValueError:
        return failure("review_binding_invalid", "review directory is invalid")
    events: list[dict] = []
    paths = sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json")) if directory.is_dir() else []
    for expected, path in enumerate(paths, 1):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return failure("review_event_invalid", f"invalid review event: {path.name}")
        if event.get("version") == 1:
            return failure("legacy_evidence_unsupported", "version 1 review evidence is unsupported")
        if event.get("version") != 2:
            return failure("review_event_invalid", "review event version must be 2")
        if event.get("sequence") != expected or not path.name.startswith(f"{expected:06d}-{event.get('event_type')}"):
            return failure("review_event_invalid", "review event sequence is invalid")
        safe_event = _safe_finding_strings(event, field="event")
        if not safe_event.ok:
            return safe_event
        events.append(event)
    reduced = review_model.reduce_review(events)
    if not reduced.ok:
        return failure(reduced.error.code, reduced.error.message)
    active_spec_commit = binding.get("spec_commit") or binding.get("approval_commit")
    for event in events:
        for item in event.get("findings", []) + event.get("terminal_observations", []):
            checked = _validate_finding_for_binding(root, binding, item, spec_commit=active_spec_commit)
            if not checked.ok:
                return checked
        if event.get("event_type") == "findings-rebound":
            active_spec_commit = event.get("spec_commit")
    return ok(events)

def _selected_profiles(root: Path, binding: dict, explicit: list[str]) -> tuple[list[str], str]:
    if explicit:
        return sorted(set(explicit)), "explicit"
    base = binding.get("input", {}).get("base") or binding.get("approval_commit")
    head = binding.get("input", {}).get("head") or binding.get("head")
    changed = _git(root, "diff", "--name-only", base, head).stdout.splitlines() if base and head else []
    profiles: set[str] = set()
    for path in changed:
        if path.startswith("skills/") or path.startswith("evals/"):
            profiles.add("skill")
        elif path.endswith(".md"):
            profiles.add("document")
        else:
            profiles.add("default")
    return sorted(profiles or {"default"}), "changed_files"

def bind_review(
    root: Path, binding: dict, *, model: str, level: str = "standard",
    profiles: list[str] | None = None, model_source: str = "explicit",
    second_reviewer: str | None = None, second_model: str | None = None,
) -> RuntimeResult:
    checked_binding = _validate_review_binding(binding)
    if not checked_binding.ok:
        return checked_binding
    if not _bounded_text(model).ok or not _bounded_text(model_source).ok:
        return failure("review_model_required", "review model must be recorded")
    if level not in {"light", "standard"}:
        return failure("review_level_invalid", "review level must be light or standard")
    selected, profile_source = _selected_profiles(root, binding, profiles or [])
    if not selected or any(profile not in PROFILES for profile in selected):
        return failure("review_profile_invalid", "review profiles must use the known profile registry")
    if bool(second_reviewer) != bool(second_model):
        return failure("second_reviewer_invalid", "second reviewer and second model must be supplied together")
    if second_reviewer and (not _bounded_text(second_reviewer).ok or not _bounded_text(second_model).ok):
        return failure("second_reviewer_invalid", "second reviewer settings must be safe bounded text")
    enriched = {**binding, "version": 2, "review_options": {
        "level": level, "profiles": selected, "profile_source": profile_source,
        "model": model, "model_source": model_source,
        "second_reviewer": second_reviewer, "second_model": second_model,
    }}
    try:
        directory = review_directory(root, enriched)
    except ValueError:
        return failure("review_binding_invalid", "review directory is invalid")
    try:
        _write_once(directory / "binding.json", enriched)
    except FileExistsError:
        return failure("review_collision", "review binding already exists")
    binding.clear()
    binding.update(enriched)
    return append_event(root, enriched, "review-bound", {
        "model": model, "model_source": model_source, "input_kind": input_kind(enriched),
        "level": level, "profiles": selected, "profile_source": profile_source,
    })

def current_findings(events: list[dict]) -> list[dict]:
    reduced = review_model.reduce_review(events)
    return reduced.value["findings"] if reduced.ok else []

def _findings_stale(events: list[dict]) -> bool:
    active = False
    for event in events:
        if event.get("event_type") == "findings_stale":
            active = True
        elif event.get("event_type") == "findings-rebound":
            active = False
    return active

def _bounded_text(value: object, *, required: bool = True) -> RuntimeResult:
    if not isinstance(value, str):
        return failure("bounded_text_invalid", "review text must be a bounded string")
    normalized = value.strip()
    if (required and not normalized) or len(normalized) > 2000 or contains_secret(normalized.encode()):
        return failure("bounded_text_invalid", "review text is empty, too long, or secret-shaped")
    return ok(normalized)

def _safe_finding_strings(value: object, *, field: str = "finding") -> RuntimeResult:
    if isinstance(value, dict):
        for key, item in value.items():
            checked = _safe_finding_strings(item, field=str(key))
            if not checked.ok:
                return checked
        return ok()
    if isinstance(value, list):
        for item in value:
            checked = _safe_finding_strings(item, field=field)
            if not checked.ok:
                return checked
        return ok()
    if isinstance(value, str):
        limit = 4096 if field == "oracle" else 512 if field == "path" else 2000
        if len(value) > limit or "\x00" in value or contains_secret(value.encode()):
            return failure("finding_content_invalid", f"finding {field} is unsafe")
        if field == "path":
            candidate = PurePosixPath(value)
            if candidate.is_absolute() or ".." in candidate.parts:
                return failure("finding_content_invalid", "finding path must be repository-relative")
    return ok()

def _validate_finding_for_binding(
    root: Path, binding: dict, item: object, *, spec_commit: str | None = None,
) -> RuntimeResult:
    checked = review_model.validate_finding(item)
    if not checked.ok:
        return failure(checked.error.code, checked.error.message)
    content = _safe_finding_strings(item)
    if not content.ok:
        return content
    assert isinstance(item, dict)
    profiles = binding.get("review_options", {}).get("profiles", [])
    spec_commit = spec_commit or binding.get("spec_commit") or binding.get("approval_commit")
    specification = item["specification"]
    allowed_paths = binding.get("spec_paths") or ["docs/spec/"]
    path = specification["path"]
    allowed = any(path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/") for prefix in allowed_paths)
    if (
        item.get("profile") not in profiles or item.get("spec_commit") != spec_commit
        or not allowed or not _commit(root, item.get("spec_commit")).ok
    ):
        return failure("finding_binding_invalid", "finding profile or specification does not match the active review")
    return ok(dict(item))

def record_second_review(
    root: Path, binding: dict, *, status: str, actual_model: str | None, summary: str,
) -> RuntimeResult:
    options = binding.get("review_options", {})
    if not options.get("second_reviewer"):
        return failure("second_reviewer_not_requested", "second review was not explicitly requested")
    checked_summary = _bounded_text(summary)
    checked_model = _bounded_text(actual_model) if actual_model is not None else None
    if (
        status not in {"completed", "unavailable"} or not checked_summary.ok
        or (status == "completed" and (checked_model is None or not checked_model.ok))
        or (status == "unavailable" and actual_model is not None)
    ):
        return failure("second_review_invalid", "second review result needs status, model, and summary")
    events = load_events(root, binding)
    if not events.ok:
        return events
    if any(event.get("event_type") == "second-review-recorded" for event in events.value):
        return failure("second_review_already_recorded", "second reviewer runs only once")
    fields = {
        "status": status, "reviewer": options["second_reviewer"],
        "requested_model": options.get("second_model"),
        "summary": checked_summary.value,
    }
    if checked_model is not None:
        fields["actual_model"] = checked_model.value
    return append_event(root, binding, "second-review-recorded", fields)

def begin_stage(root: Path, binding: dict, *, reviewer_context: str) -> RuntimeResult:
    checked_context = _bounded_text(reviewer_context)
    if not checked_context.ok:
        return failure("review_context_invalid", "reviewer context must be safe bounded text")
    reviewer_context = checked_context.value
    events_result = load_events(root, binding)
    if not events_result.ok:
        return events_result
    events = events_result.value
    state = review_model.reduce_review(events).value
    if not events or events[0].get("event_type") != "review-bound":
        return failure("review_not_bound", "review input must be bound first")
    if state["stale"]:
        return failure("findings_stale", "review findings need a human-approved rebound")
    if not state["initial_started"]:
        return append_event(root, binding, "initial-full-review-started", {"reviewer_context": reviewer_context})
    if not state["initial_done"]:
        return failure("stage_results_required", "initial full review results must be recorded")
    findings = state["findings"]
    if any(item.get("state") == "open" for item in findings):
        if state["targeted_pending"]:
            return failure("stage_results_required", "targeted review must update findings before another stage")
        return append_event(root, binding, "targeted-review-started", {
            "reviewer_context": reviewer_context,
            "finding_ids": sorted(item["id"] for item in findings if item.get("state") == "open"),
        })
    if not state["final_started"]:
        targeted_positions = [index for index, event in enumerate(events) if event.get("event_type") == "targeted-review-started"]
        if targeted_positions and not any(
            event.get("event_type") == "progress-assessed" for event in events[targeted_positions[-1] + 1:]
        ):
            return failure("progress_assessment_required", "targeted convergence needs lexicographic progress evidence")
        if reviewer_context == state["initial_context"]:
            return failure("fresh_context_required", "final full review needs a different context")
        return append_event(root, binding, "final-full-review-started", {"reviewer_context": reviewer_context})
    if not state["final_done"]:
        return failure("stage_results_required", "final full review results must be recorded")
    if any(item.get("state") == "open" for item in current_findings(events)):
        return append_event(root, binding, "targeted-review-started", {
            "reviewer_context": reviewer_context,
            "finding_ids": sorted(item["id"] for item in current_findings(events) if item.get("state") == "open"),
        })
    return ok({"event_type": "ready-to-complete"})

def record_findings(
    root: Path, binding: dict, *, stage: str, findings: list[dict], safety: dict,
    reviewer_context: str, actual_model: str | None = None,
) -> RuntimeResult:
    if actual_model is None:
        return failure("actual_model_required", "review stage result needs the actual reviewer model")
    checked_model = _bounded_text(actual_model)
    checked_summary = _bounded_text(safety.get("summary") if isinstance(safety, dict) else None)
    if (
        stage not in {"initial", "final"} or not isinstance(safety, dict)
        or safety.get("completed") is not True or not checked_summary.ok or not checked_model.ok
        or safety.get("unresolved") != []
    ):
        code = "bounded_text_invalid" if not checked_summary.ok or not checked_model.ok else "safety_check_required"
        return failure(code, "initial and final review require safe bounded model and safety results")
    events = load_events(root, binding)
    if not events.ok:
        return events
    if _findings_stale(events.value):
        return failure("findings_stale", "stale findings allow only a human-approved rebound")
    start_type = f"{stage}-full-review-started"
    result_type = f"{stage}-findings-recorded"
    start = next((event for event in reversed(events.value) if event.get("event_type") == start_type), None)
    if start is None or start.get("reviewer_context") != reviewer_context:
        return failure("review_context_mismatch", "finding results must match their review context")
    if any(event.get("event_type") == result_type for event in events.value):
        return failure("findings_already_recorded", "stage findings are append-only")
    ids: set[str] = set()
    active_spec_commit = review_model.reduce_review(events.value).value["active_spec_commit"]
    for item in findings:
        checked = _validate_finding_for_binding(root, binding, item, spec_commit=active_spec_commit)
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
        "findings": findings, "safety": {
            "completed": True, "summary": checked_summary.value, "unresolved": [],
        }, "reviewer_context": reviewer_context, "actual_model": checked_model.value,
    })

def _commit_has_trailer(root: Path, commit: str, finding_id: str) -> bool:
    resolved = _commit(root, commit)
    if not resolved.ok:
        return False
    message = _git(root, "show", "-s", "--format=%B", resolved.value).stdout
    return re.search(rf"(?m)^Finding:\s*{re.escape(finding_id)}\s*$", message) is not None

def _bound_trailer_commits(
    root: Path, binding: dict, finding_id: str, *, selected_fix_head: str | None = None,
) -> RuntimeResult:
    base = binding.get("input", {}).get("base") or binding.get("approval_commit")
    branch = binding.get("input", {}).get("branch") or binding.get("branch")
    original_head = binding.get("input", {}).get("head") or binding.get("head")
    head = f"refs/heads/{branch}" if branch else selected_fix_head or original_head
    if not base or not head:
        return failure("fix_commit_unlinked", "review input has no bounded commit range")
    if not branch and selected_fix_head:
        resolved = _commit(root, selected_fix_head)
        if not resolved.ok or not original_head or _git(
            root, "merge-base", "--is-ancestor", original_head, resolved.value,
        ).returncode != 0:
            return failure("fix_commit_unlinked", "selected fix head must descend from the reviewed head")
        base = original_head
        head = resolved.value
    history = _git(root, "rev-list", "--reverse", f"{base}..{head}")
    if history.returncode != 0:
        return failure("fix_commit_unlinked", "review commit range is unavailable")
    return ok([commit for commit in history.stdout.splitlines() if _commit_has_trailer(root, commit, finding_id)])

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
    linked = _bound_trailer_commits(
        root, binding, finding_id, selected_fix_head=fix_commits[-1] if fix_commits else None,
    )
    if not linked.ok or not fix_commits or linked.value != fix_commits:
        return failure("fix_commit_unlinked", "every fix commit must exist and carry the finding trailer")
    return append_event(root, binding, "targeted-review-result", {
        "finding_id": finding_id, "oracle_exit_code": oracle_exit_code, "fix_commits": fix_commits,
    })

def record_human_decision(
    root: Path, binding: dict, finding_id: str, *, decision: str, reason: str,
) -> RuntimeResult:
    events = load_events(root, binding)
    if not events.ok:
        return events
    if _findings_stale(events.value):
        return failure("findings_stale", "stale findings allow only a human-approved rebound")
    item = next((candidate for candidate in current_findings(events.value) if candidate["id"] == finding_id), None)
    if item is None or item.get("state") != "open":
        return failure("finding_not_open", "only an open admitted finding can receive a human decision")
    checked_decision = _bounded_text(decision)
    checked_reason = _bounded_text(reason)
    if not checked_decision.ok or not checked_reason.ok:
        return failure("human_decision_invalid", "human decision and reason must be non-empty")
    return append_event(root, binding, "human-finding-decided", {
        "finding_id": finding_id, "decision": checked_decision.value, "reason": checked_reason.value,
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
    active_spec_commit = review_model.reduce_review(events.value).value["active_spec_commit"]
    for item in candidates:
        checked = _validate_finding_for_binding(root, binding, item, spec_commit=active_spec_commit)
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
        if event.get("event_type") in {"targeted-review-result", "human-finding-decided"}
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
    state = review_model.reduce_review(events.value).value
    if state["stale"]:
        return failure("findings_stale", "stale findings cannot complete")
    if not state["final_started"]:
        return failure("final_review_required", "final full review has not started")
    if not state["final_done"]:
        return failure("final_results_required", "final full review results are missing")
    if any(item.get("state") == "open" for item in state["findings"]):
        return failure("findings_open", "all admitted findings must close")
    targeted_positions = [index for index, event in enumerate(events.value) if event.get("event_type") == "targeted-review-started"]
    if targeted_positions and not any(
        event.get("event_type") == "progress-assessed" for event in events.value[targeted_positions[-1] + 1:]
    ):
        return failure("progress_assessment_required", "targeted convergence needs lexicographic progress evidence")
    return ok({"event_type": "review-complete", "verdict": "pass"})

def load_review_binding(
    root: Path, *, review_id: str | None = None, plan_key: str | None = None, run_id: str | None = None,
) -> RuntimeResult:
    if plan_key is not None or run_id is not None:
        if not plan_key or not run_id or SAFE_ID.fullmatch(plan_key) is None or SAFE_ID.fullmatch(run_id) is None:
            return failure("review_selector_invalid", "plan key and run id must be supplied together")
        path = root.resolve() / ".agents/evidence" / plan_key / run_id / "review/binding.json"
    elif review_id and SAFE_ID.fullmatch(review_id) is not None:
        path = root.resolve() / ".agents/evidence/reviews" / review_id / "binding.json"
    else:
        return failure("review_selector_invalid", "review id or implementation run is required")
    cursor = root.resolve()
    for part in path.relative_to(root.resolve()).parts:
        cursor /= part
        if cursor.is_symlink():
            return failure("review_selector_invalid", "review selector crosses a symlink")
    if path.is_symlink() or not path.is_file():
        return failure("review_not_bound", "review binding is unavailable")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("version") == 1:
            return failure("legacy_evidence_unsupported", "version 1 review binding is unsupported")
        if value.get("version") != 2:
            return failure("review_not_bound", "review binding version is invalid")
        checked = _validate_review_binding(value)
        if not checked.ok:
            return checked
        if review_id and value.get("review_id") != review_id:
            return failure("review_selector_invalid", "review binding does not match its selector")
        if plan_key and (value.get("plan_key") != plan_key or value.get("run_id") != run_id):
            return failure("review_selector_invalid", "review binding does not match its selector")
        return ok(value)
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
    bind.add_argument("--model-source", default="explicit")
    bind.add_argument("--level", choices=("light", "standard"), default="standard")
    bind.add_argument("--profile", action="append", default=[])
    bind.add_argument("--second-reviewer")
    bind.add_argument("--second-model")
    bind.add_argument("--reviewer-context", required=True)
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
    close = commands.add_parser("close-finding")
    _selector(close)
    close.add_argument("--finding-id", required=True)
    close.add_argument("--oracle-exit-code", type=int, required=True)
    close.add_argument("--fix-commit", action="append", default=[])
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
        bound = bind_review(
            root, binding.value, model=args.model, model_source=args.model_source,
            level=args.level, profiles=args.profile, second_reviewer=args.second_reviewer,
            second_model=args.second_model,
        )
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
            safety=json.loads(Path(args.safety_file).read_text(encoding="utf-8")),
            reviewer_context=args.reviewer_context, actual_model=args.actual_model,
        )
    elif args.command == "record-second-review":
        payload = json.loads(Path(args.result_file).read_text(encoding="utf-8"))
        result = record_second_review(
            root, binding.value, status=payload.get("status", ""),
            actual_model=payload.get("actual_model", ""), summary=payload.get("summary", ""),
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
    elif args.command == "human-decision":
        result = record_human_decision(
            root, binding.value, args.finding_id, decision=args.decision, reason=args.reason,
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
