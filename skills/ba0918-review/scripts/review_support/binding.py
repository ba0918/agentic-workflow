"""Review input binding and resolution."""
from __future__ import annotations

import inspect
import json
from pathlib import Path, PurePosixPath
import sys
from typing import NamedTuple

from path_safety import safety_problem
from review_support.events import append_event
from review_support.repository import (
    changed_paths,
    commit,
    default_branch as repository_default_branch,
    git,
    review_directory,
    read_object,
    uncommitted_paths,
    write_once,
)
from review_support.types import (
    COMMIT,
    PROFILES,
    SAFE_ID,
    JsonObject,
    RuntimeResult,
    failure,
    object_value,
    object_values,
    ok,
    string_values,
)
from review_support.validation import bounded_text, validate_review_binding


SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
import implementation_evidence


def _execution_binding(
    plan_key: str,
    run_id: str,
    approval_commit: str,
    options: JsonObject,
) -> JsonObject:
    implement_sequence = options.get("implement_sequence")
    if (
        SAFE_ID.fullmatch(plan_key) is None
        or SAFE_ID.fullmatch(run_id) is None
        or COMMIT.fullmatch(approval_commit) is None
        or not isinstance(implement_sequence, int)
    ):
        raise ValueError("unsafe execution binding")
    return {
        "version": 2,
        "kind": "execution",
        "plan_key": plan_key,
        "run_id": run_id,
        "approval_commit": approval_commit,
        "implement_sequence": implement_sequence,
        "branch": options.get("branch"),
        "head": options.get("head"),
        "worktree": options.get("worktree"),
    }


class ExecutionBinding:
    """Callable adapter preserving the established seven-parameter facade."""

    __signature__ = inspect.Signature(
        parameters=(
            inspect.Parameter("plan_key", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("run_id", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("approval_commit", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("implement_sequence", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("branch", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("head", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("worktree", inspect.Parameter.KEYWORD_ONLY, default=None),
        )
    )

    def __call__(
        self,
        plan_key: str,
        run_id: str,
        approval_commit: str,
        **options: object,
    ) -> JsonObject:
        allowed = {"implement_sequence", "branch", "head", "worktree"}
        if set(options) - allowed:
            unexpected = sorted(set(options) - allowed)[0]
            raise TypeError(f"unexpected keyword argument: {unexpected}")
        if "implement_sequence" not in options:
            raise TypeError("missing required keyword-only argument: implement_sequence")
        return _execution_binding(plan_key, run_id, approval_commit, dict(options))


execution_binding = ExecutionBinding()


def standalone_binding(
    review_id: str,
    *,
    base: str,
    head: str,
    spec_paths: list[str],
    branch: str | None = None,
) -> JsonObject:
    """Build a validated standalone review binding."""

    unsafe = SAFE_ID.fullmatch(review_id) is None or COMMIT.fullmatch(base) is None
    if unsafe or COMMIT.fullmatch(head) is None:
        raise ValueError("unsafe standalone binding")
    if branch is not None and (not branch or ".." in branch or branch.startswith("-")):
        raise ValueError("unsafe branch")
    for path in spec_paths:
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("unsafe specification path")
    return {
        "version": 2,
        "kind": "standalone",
        "review_id": review_id,
        "input": {
            "kind": "branch" if branch else "commits",
            "branch": branch,
            "base": base,
            "head": head,
        },
        "spec_paths": sorted(spec_paths),
        "spec_commit": head,
    }


def input_kind(binding: JsonObject) -> str:
    """Return the review input discriminator."""

    if binding.get("kind") == "execution":
        return "execution"
    review_input = object_value(binding.get("input")) or {}
    kind = review_input.get("kind", "unknown")
    return kind if isinstance(kind, str) else "unknown"


def choose_comparison_base(
    *,
    explicit: str | None,
    pull_request_target: str | None,
    default_branch: str | None,
) -> RuntimeResult[str]:
    """Choose the first unambiguous comparison-base source."""

    for candidate in (explicit, pull_request_target, default_branch):
        if candidate:
            return ok(candidate)
    return RuntimeResult(None, failure("comparison_base_required", "branch comparison base cannot be determined uniquely").error)


def requires_full_review(changed_dimensions: set[str]) -> bool:
    """Return whether document changes invalidate a targeted review."""

    consequential = {
        "structure",
        "assumptions",
        "order",
        "dependencies",
        "completion",
        "specification",
        "scope_topology",
    }
    return bool(changed_dimensions & consequential)


def _implementation_events(store: Path) -> RuntimeResult[list[JsonObject]]:
    events: list[JsonObject] = []
    paths = sorted(store.glob("[0-9][0-9][0-9][0-9][0-9][0-9]-*.json"))
    for expected, path in enumerate(paths, 1):
        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
            event = object_value(decoded)
        except (OSError, json.JSONDecodeError):
            event = None
        if event is None:
            return RuntimeResult(None, failure("execution_input_invalid", f"invalid implementation event: {path.name}").error)
        expected_name = f"{expected:06d}-{event.get('event_type')}"
        if event.get("version") != 2:
            return RuntimeResult(None, failure("execution_input_invalid", "implementation event version must be 2").error)
        if event.get("sequence") != expected or not path.name.startswith(expected_name):
            return RuntimeResult(None, failure("execution_input_invalid", "implementation evidence is not contiguous").error)
        events.append(event)
    return ok(events)


def _validate_implementation_segments(
    root: Path,
    start_commit: str,
    segments: list[JsonObject],
    branch_head: str,
) -> RuntimeResult[None]:
    history = git(root, "rev-list", "--reverse", f"{start_commit}..{branch_head}")
    if history.returncode != 0:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation revision range is unavailable").error)
    commits = [
        commit_id
        for segment in segments
        for commit_id in string_values(segment.get("commits")) or []
    ]
    document_boundaries = {str(segment.get("approval_commit")) for segment in segments[1:]}
    implementation_history = [
        commit_id
        for commit_id in filter(None, history.stdout.splitlines())
        if commit_id not in document_boundaries
    ]
    if implementation_history != commits:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation revision range and evidence differ").error)
    return ok()


def _green_state(
    binding: JsonObject,
    events: list[JsonObject],
) -> RuntimeResult[tuple[JsonObject, JsonObject]]:
    green_index = len(events) - 1
    if binding.get("delegated"):
        if len(events) < 2 or events[-1].get("event_type") != "returned":
            return RuntimeResult(None, failure("implementation_incomplete", "delegated implementation has not returned").error)
        green_index -= 1
    if green_index < 0 or events[green_index].get("event_type") != "implementation_green":
        return RuntimeResult(None, failure("implementation_incomplete", "last implementation event is not implementation_green").error)
    green = events[green_index]
    derived = implementation_evidence.derive_implementation(binding, events[:green_index])
    if not derived.ok:
        assert derived.error is not None
        return RuntimeResult(None, failure(derived.error.code, derived.error.message).error)
    return ok((green, derived.required()))


def _validate_green_steps(green: JsonObject, derived: JsonObject) -> bool:
    steps = object_values(derived.get("steps")) or []
    step_ids = [str(step["id"]) for step in steps]
    return derived.get("resume_step") is None and green.get("completed_steps") == step_ids


def _same_git_repository(root: Path, worktree: Path) -> bool:
    root_common = git(root, "rev-parse", "--git-common-dir")
    worktree_common = git(worktree, "rev-parse", "--git-common-dir")
    if root_common.returncode != 0 or worktree_common.returncode != 0:
        return False
    root_path = (root / root_common.stdout.strip()).resolve()
    worktree_path = (worktree / worktree_common.stdout.strip()).resolve()
    return root_path == worktree_path


def _execution_worktree(
    root: Path,
    binding: JsonObject,
    derived: JsonObject,
    events: list[JsonObject],
) -> RuntimeResult[tuple[Path, str, str]]:
    worktree = Path(str(binding.get("worktree", "")))
    branch = binding.get("branch")
    if not isinstance(branch, str) or not worktree.is_dir():
        return RuntimeResult(None, failure("execution_input_invalid", "implementation worktree and branch do not match").error)
    if git(worktree, "branch", "--show-current").stdout.strip() != branch:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation worktree and branch do not match").error)
    if not _same_git_repository(root, worktree):
        return RuntimeResult(None, failure("execution_input_invalid", "implementation worktree is not a Git worktree").error)
    branch_head = commit(root, f"refs/heads/{branch}")
    commits = [event for event in events if event.get("event_type") == "commit"]
    existing = all(commit(root, str(event.get("commit", ""))).ok for event in commits)
    if not existing or not branch_head.ok:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation branch tip is unavailable").error)
    segments = object_values(derived.get("segments")) or []
    start = str(binding.get("approval_commit", ""))
    segment_check = _validate_implementation_segments(root, start, segments, branch_head.required())
    if not segment_check.ok:
        return RuntimeResult(None, segment_check.error)
    return ok((worktree, branch, branch_head.required()))


def _scope_state(
    root: Path,
    worktree: Path,
    start: str,
    branch_head: str,
) -> RuntimeResult[list[str]]:
    changed = changed_paths(root, start, branch_head)
    dirty = uncommitted_paths(worktree)
    if not changed.ok:
        return RuntimeResult(None, changed.error)
    if not dirty.ok:
        return RuntimeResult(None, dirty.error)
    dirty_paths = set(dirty.required())
    changed_set = set(changed.required())
    if dirty_paths & changed_set:
        return RuntimeResult(None, failure("review_scope_dirty", "reviewed implementation paths have uncommitted changes").error)
    outside = sorted(dirty_paths - changed_set)
    unsafe = next((path for path in outside if safety_problem(path) is not None), None)
    if unsafe is not None:
        return RuntimeResult(None, failure("dangerous_path", f"unsafe uncommitted path: {unsafe}").error)
    return ok(outside)


def _load_implementation_input(
    root: Path,
    plan_key: str,
    run_id: str,
) -> RuntimeResult[tuple[JsonObject, list[JsonObject]]]:
    if SAFE_ID.fullmatch(plan_key) is None or SAFE_ID.fullmatch(run_id) is None:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation identifiers are unsafe").error)
    store = root.resolve() / ".agents/evidence" / plan_key / run_id
    binding_path = store / "binding.json"
    if binding_path.is_symlink() or not binding_path.is_file():
        return RuntimeResult(None, failure("execution_input_unavailable", "implementation binding is unavailable").error)
    try:
        binding = object_value(json.loads(binding_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        binding = None
    if binding is None or binding.get("plan_key") != plan_key or binding.get("run_id") != run_id:
        return RuntimeResult(None, failure("execution_input_invalid", "implementation binding and path differ").error)
    loaded = _implementation_events(store)
    if not loaded.ok:
        return RuntimeResult(None, loaded.error)
    return ok((binding, loaded.required()))


def _validated_green(
    root: Path,
    binding: JsonObject,
    events: list[JsonObject],
) -> RuntimeResult[tuple[str, JsonObject]]:
    green_state = _green_state(binding, events)
    if not green_state.ok:
        return RuntimeResult(None, green_state.error)
    green, derived = green_state.required()
    approval = commit(root, str(derived.get("approval_commit", "")))
    if not approval.ok:
        return RuntimeResult(None, failure("execution_input_invalid", "effective implementation approval commit does not exist").error)
    if not _validate_green_steps(green, derived):
        return RuntimeResult(None, failure("execution_input_invalid", "implementation_green does not cover the bound steps").error)
    return ok((approval.required(), derived))


def _resolved_execution_binding(
    root: Path,
    binding: JsonObject,
    events: list[JsonObject],
    approval: str,
    derived: JsonObject,
) -> RuntimeResult[JsonObject]:
    worktree_state = _execution_worktree(root, binding, derived, events)
    if not worktree_state.ok:
        return RuntimeResult(None, worktree_state.error)
    worktree, branch, branch_head = worktree_state.required()
    outside = _scope_state(root, worktree, str(binding.get("approval_commit", "")), branch_head)
    if not outside.ok:
        return RuntimeResult(None, outside.error)
    try:
        sequence = events[-1].get("sequence")
        if not isinstance(sequence, int):
            raise ValueError("implementation sequence is invalid")
        resolved = execution_binding(
            str(binding["plan_key"]),
            str(binding["run_id"]),
            approval,
            implement_sequence=sequence,
            branch=branch,
            head=branch_head,
            worktree=str(worktree.resolve()),
        )
    except (KeyError, TypeError, ValueError):
        return RuntimeResult(None, failure("execution_input_invalid", "implementation binding cannot start review").error)
    resolved["uncommitted_outside_scope"] = outside.required()
    return ok(resolved)


def _validate_execution_input(root: Path, plan_key: str, run_id: str) -> RuntimeResult[JsonObject]:
    loaded = _load_implementation_input(root, plan_key, run_id)
    if not loaded.ok:
        return RuntimeResult(None, loaded.error)
    binding, events = loaded.required()
    green = _validated_green(root, binding, events)
    if not green.ok:
        return RuntimeResult(None, green.error)
    approval, derived = green.required()
    return _resolved_execution_binding(root, binding, events, approval, derived)


def _comparison_target(repository: Path, options: JsonObject) -> RuntimeResult[str]:
    base = options.get("base")
    target_name = options.get("pull_request_target")
    default: str | None = None
    if base is None and target_name is None:
        selected_default = repository_default_branch(repository)
        if not selected_default.ok:
            return RuntimeResult(None, selected_default.error)
        default = selected_default.required()
    selected = choose_comparison_base(
        explicit=base if isinstance(base, str) else None,
        pull_request_target=target_name if isinstance(target_name, str) else None,
        default_branch=default,
    )
    if not selected.ok:
        return RuntimeResult(None, selected.error)
    target = commit(repository, selected.required())
    if not target.ok:
        return RuntimeResult(None, target.error)
    return target


def _merge_base(repository: Path, target: str, branch_head: str) -> RuntimeResult[str]:
    merge_base = git(repository, "merge-base", target, branch_head)
    if merge_base.returncode != 0 or COMMIT.fullmatch(merge_base.stdout.strip()) is None:
        return RuntimeResult(None, failure("comparison_base_required", "branch and target have no merge base").error)
    return ok(merge_base.stdout.strip())


def _supplied_head_matches(repository: Path, options: JsonObject, branch_head: str) -> bool:
    supplied = options.get("head")
    if not isinstance(supplied, str):
        return True
    resolved = commit(repository, supplied)
    return resolved.ok and resolved.required() == branch_head


def _resolve_branch(
    repository: Path,
    review_id: str,
    branch: str,
    options: JsonObject,
) -> RuntimeResult[JsonObject]:
    branch_head = commit(repository, f"refs/heads/{branch}")
    if not branch_head.ok:
        return RuntimeResult(None, failure("branch_not_found", f"branch does not exist: {branch}").error)
    target = _comparison_target(repository, options)
    if not target.ok:
        return RuntimeResult(None, target.error)
    merge_base = _merge_base(repository, target.required(), branch_head.required())
    if not merge_base.ok:
        return RuntimeResult(None, merge_base.error)
    if not _supplied_head_matches(repository, options, branch_head.required()):
        return RuntimeResult(None, failure("branch_head_mismatch", "supplied head differs from branch tip").error)
    try:
        return ok(standalone_binding(
            review_id,
            branch=branch,
            base=merge_base.required(),
            head=branch_head.required(),
            spec_paths=string_values(options.get("spec_paths")) or ["docs/spec/"],
        ))
    except ValueError as error:
        return RuntimeResult(None, failure("standalone_input_invalid", str(error)).error)


def _resolve_commits(
    repository: Path,
    review_id: str,
    options: JsonObject,
) -> RuntimeResult[JsonObject]:
    base = options.get("base")
    head = options.get("head")
    if not isinstance(base, str) or not isinstance(head, str):
        return RuntimeResult(None, failure("commit_input_incomplete", "two-commit review needs base and head").error)
    resolved_base = commit(repository, base)
    resolved_head = commit(repository, head)
    if not resolved_base.ok:
        return RuntimeResult(None, resolved_base.error)
    if not resolved_head.ok:
        return RuntimeResult(None, resolved_head.error)
    try:
        return ok(standalone_binding(
            review_id,
            base=resolved_base.required(),
            head=resolved_head.required(),
            spec_paths=string_values(options.get("spec_paths")) or ["docs/spec/"],
        ))
    except ValueError as error:
        return RuntimeResult(None, failure("standalone_input_invalid", str(error)).error)


class ResolveInput:
    """Callable adapter preserving the established input-resolution facade."""

    __signature__ = inspect.Signature(
        parameters=(
            inspect.Parameter("root", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("review_id", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("plan_key", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("run_id", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("branch", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("base", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("head", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("pull_request_target", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("spec_paths", inspect.Parameter.KEYWORD_ONLY, default=None),
        )
    )

    def __call__(self, root: Path, **options: object) -> RuntimeResult[JsonObject]:
        review_id = options.pop("review_id", None)
        if not isinstance(review_id, str):
            raise TypeError("missing required keyword-only argument: review_id")
        allowed = {"plan_key", "run_id", "branch", "base", "head", "pull_request_target", "spec_paths"}
        if set(options) - allowed:
            unexpected = sorted(set(options) - allowed)[0]
            raise TypeError(f"unexpected keyword argument: {unexpected}")
        repository = root.resolve()
        plan_key = options.get("plan_key")
        run_id = options.get("run_id")
        if plan_key is not None or run_id is not None:
            if not isinstance(plan_key, str) or not isinstance(run_id, str):
                return RuntimeResult(None, failure("execution_input_incomplete", "plan key and run id must be supplied together").error)
            return _validate_execution_input(repository, plan_key, run_id)
        branch = options.get("branch")
        if isinstance(branch, str):
            return _resolve_branch(repository, review_id, branch, dict(options))
        return _resolve_commits(repository, review_id, dict(options))


resolve_input = ResolveInput()


def selected_profiles(root: Path, binding: JsonObject, explicit: list[str]) -> tuple[list[str], str]:
    """Select profiles from an explicit request or changed paths."""

    if explicit:
        return sorted(set(explicit)), "explicit"
    review_input = object_value(binding.get("input")) or {}
    base = review_input.get("base") or binding.get("approval_commit")
    head = review_input.get("head") or binding.get("head")
    changed = git(root, "diff", "--name-only", str(base), str(head)).stdout.splitlines() if base and head else []
    profiles: set[str] = set()
    for path in changed:
        if path.startswith(("skills/", "evals/")):
            profiles.add("skill")
        elif path.endswith(".md"):
            profiles.add("document")
        else:
            profiles.add("default")
    return sorted(profiles or {"default"}), "changed_files"


class BindingOptions(NamedTuple):
    model: str
    level: str
    profiles: list[str]
    profile_source: str
    model_source: str
    second_reviewer: str | None
    second_model: str | None


def _bind_options(options: JsonObject) -> BindingOptions:
    model = options.get("model")
    if not isinstance(model, str):
        raise TypeError("missing required keyword-only argument: model")
    level = options.get("level", "standard")
    profiles = string_values(options.get("profiles")) or []
    model_source = options.get("model_source", "explicit")
    second_reviewer = options.get("second_reviewer")
    second_model = options.get("second_model")
    return BindingOptions(
        model,
        str(level),
        profiles,
        "",
        str(model_source),
        second_reviewer if isinstance(second_reviewer, str) else None,
        second_model if isinstance(second_model, str) else None,
    )


def _validated_binding_options(
    root: Path,
    binding: JsonObject,
    options: BindingOptions,
) -> RuntimeResult[BindingOptions]:
    if not bounded_text(options.model).ok or not bounded_text(options.model_source).ok:
        return RuntimeResult(None, failure("review_model_required", "review model must be recorded").error)
    if options.level not in {"light", "standard"}:
        return RuntimeResult(None, failure("review_level_invalid", "review level must be light or standard").error)
    selected, source = selected_profiles(root, binding, options.profiles)
    if not selected or any(profile not in PROFILES for profile in selected):
        return RuntimeResult(None, failure("review_profile_invalid", "review profiles must use the known profile registry").error)
    if bool(options.second_reviewer) != bool(options.second_model):
        return RuntimeResult(None, failure("second_reviewer_invalid", "second reviewer and second model must be supplied together").error)
    if options.second_reviewer and (
        not bounded_text(options.second_reviewer).ok or not bounded_text(options.second_model).ok
    ):
        return RuntimeResult(None, failure("second_reviewer_invalid", "second reviewer settings must be safe bounded text").error)
    return ok(options._replace(profiles=selected, profile_source=source))


def _enrich_binding(binding: JsonObject, options: BindingOptions) -> JsonObject:
    return {**binding, "version": 2, "review_options": {
        "level": options.level,
        "profiles": options.profiles,
        "profile_source": options.profile_source,
        "model": options.model,
        "model_source": options.model_source,
        "second_reviewer": options.second_reviewer,
        "second_model": options.second_model,
    }}


def _persist_binding(
    root: Path,
    binding: JsonObject,
    enriched: JsonObject,
    options: BindingOptions,
) -> RuntimeResult[JsonObject]:
    try:
        directory = review_directory(root, enriched)
        write_once(directory / "binding.json", enriched)
    except ValueError:
        return RuntimeResult(None, failure("review_binding_invalid", "review directory is invalid").error)
    except FileExistsError:
        return RuntimeResult(None, failure("review_collision", "review binding already exists").error)
    binding.clear()
    binding.update(enriched)
    return append_event(root, enriched, "review-bound", {
        "model": options.model,
        "model_source": options.model_source,
        "input_kind": input_kind(enriched),
        "level": options.level,
        "profiles": options.profiles,
        "profile_source": options.profile_source,
    })


class BindReview:
    """Callable adapter preserving review binding options."""

    __signature__ = inspect.Signature(
        parameters=(
            inspect.Parameter("root", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("binding", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("model", inspect.Parameter.KEYWORD_ONLY),
            inspect.Parameter("level", inspect.Parameter.KEYWORD_ONLY, default="standard"),
            inspect.Parameter("profiles", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("model_source", inspect.Parameter.KEYWORD_ONLY, default="explicit"),
            inspect.Parameter("second_reviewer", inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("second_model", inspect.Parameter.KEYWORD_ONLY, default=None),
        )
    )

    def __call__(
        self,
        root: Path,
        binding: JsonObject,
        **options: object,
    ) -> RuntimeResult[JsonObject]:
        allowed = {"model", "level", "profiles", "model_source", "second_reviewer", "second_model"}
        if set(options) - allowed:
            unexpected = sorted(set(options) - allowed)[0]
            raise TypeError(f"unexpected keyword argument: {unexpected}")
        parsed = _bind_options(dict(options))
        checked_binding = validate_review_binding(binding)
        if not checked_binding.ok:
            return RuntimeResult(None, checked_binding.error)
        validated = _validated_binding_options(root, binding, parsed)
        if not validated.ok:
            return RuntimeResult(None, validated.error)
        values = validated.required()
        enriched = _enrich_binding(binding, values)
        return _persist_binding(root, binding, enriched, values)


bind_review = BindReview()


def _selected_binding_path(
    repository: Path,
    review_id: str | None,
    plan_key: str | None,
    run_id: str | None,
) -> RuntimeResult[Path]:
    if plan_key is not None or run_id is not None:
        invalid = not plan_key or not run_id or SAFE_ID.fullmatch(plan_key) is None or SAFE_ID.fullmatch(run_id) is None
        if invalid:
            return RuntimeResult(None, failure("review_selector_invalid", "plan key and run id must be supplied together").error)
        assert plan_key is not None and run_id is not None
        return ok(repository / ".agents/evidence" / plan_key / run_id / "review/binding.json")
    if review_id and SAFE_ID.fullmatch(review_id) is not None:
        return ok(repository / ".agents/evidence/reviews" / review_id / "binding.json")
    return RuntimeResult(None, failure("review_selector_invalid", "review id or implementation run is required").error)


def _safe_binding_path(repository: Path, path: Path) -> RuntimeResult[Path]:
    cursor = repository
    for part in path.relative_to(repository).parts:
        cursor /= part
        if cursor.is_symlink():
            return RuntimeResult(None, failure("review_selector_invalid", "review selector crosses a symlink").error)
    if path.is_symlink() or not path.is_file():
        return RuntimeResult(None, failure("review_not_bound", "review binding is unavailable").error)
    return ok(path)


def _validate_loaded_binding(
    value: JsonObject,
    review_id: str | None,
    plan_key: str | None,
    run_id: str | None,
) -> RuntimeResult[JsonObject]:
    if value.get("version") == 1:
        return RuntimeResult(None, failure("legacy_evidence_unsupported", "version 1 review binding is unsupported").error)
    checked = validate_review_binding(value)
    if not checked.ok:
        return RuntimeResult(None, checked.error)
    selector_mismatch = review_id is not None and value.get("review_id") != review_id
    execution_mismatch = plan_key is not None and (
        value.get("plan_key") != plan_key or value.get("run_id") != run_id
    )
    if selector_mismatch or execution_mismatch:
        return RuntimeResult(None, failure("review_selector_invalid", "review binding does not match its selector").error)
    return ok(value)


def load_review_binding(
    root: Path,
    *,
    review_id: str | None = None,
    plan_key: str | None = None,
    run_id: str | None = None,
) -> RuntimeResult[JsonObject]:
    """Load a review binding selected by review id or implementation run."""

    repository = root.resolve()
    selected = _selected_binding_path(repository, review_id, plan_key, run_id)
    if not selected.ok:
        return RuntimeResult(None, selected.error)
    safe_path = _safe_binding_path(repository, selected.required())
    if not safe_path.ok:
        return RuntimeResult(None, safe_path.error)
    loaded = read_object(safe_path.required(), "review_not_bound", "review binding is invalid")
    if not loaded.ok:
        return RuntimeResult(None, failure("review_not_bound", "review binding is invalid").error)
    return _validate_loaded_binding(loaded.required(), review_id, plan_key, run_id)
