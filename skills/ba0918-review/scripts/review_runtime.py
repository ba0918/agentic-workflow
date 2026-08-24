#!/usr/bin/env python3
"""Review runtime: verifies the implement hand-off and keeps the review's own evidence."""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shlex
import subprocess
import sys
from typing import Any, NamedTuple


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCRIPT_DIR = Path(__file__).resolve().parent
review_model = _load_module("review_model", SCRIPT_DIR / "review_model.py")

EXECUTIONS = PurePosixPath(".agents/artifacts/executions")
REVIEW_SCRATCH = PurePosixPath(".agents/tmp/reviews")
REVIEW_DIR = "review"
IMPLEMENT_TERMINAL_EVENT = "implementation_green"
DEFAULT_PROFILE_DIR = SCRIPT_DIR.parent / "references" / "profile"
SKILL_PROFILE = "skill"
DEFAULT_PROFILE = "default"
LIGHT_SEVERITIES = {"security", "critical"}
CREDENTIAL_ASSIGNMENT = re.compile(
    rb"(?i)(api[_-]?key|secret|token|password|credential)\s*[=:]\s*[^<\s][^\s]*"
)
ORACLE_TIMEOUT_SECONDS = 600


class RuntimeFailure(NamedTuple):
    code: str
    message: str
    detail: Any = None


class RuntimeResult(NamedTuple):
    value: Any | None
    error: RuntimeFailure | None

    @property
    def ok(self) -> bool:
        return self.error is None


def _ok(value: Any = None) -> RuntimeResult:
    return RuntimeResult(value, None)


def _failure(code: str, message: str, detail: Any = None) -> RuntimeResult:
    return RuntimeResult(None, RuntimeFailure(code, message, detail))


class Review(NamedTuple):
    main_checkout: Path
    plan_id: str
    attempt_id: str
    evidence_path: Path
    review_path: Path
    binding: dict
    implement_events: list[dict]
    worktree: Path


# ---------------------------------------------------------------- small helpers


def _git(checkout: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=checkout, text=True, capture_output=True, check=False)


def _file_identity(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> RuntimeResult:
    try:
        return _ok(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        return _failure("evidence_unreadable", f"cannot read {path.name}", str(error))


def _events_in(directory: Path) -> list[dict]:
    events: list[dict] = []
    if not directory.is_dir():
        return events
    for path in sorted(directory.glob("0*.json")):
        loaded = _read_json(path)
        if loaded.ok and isinstance(loaded.value, dict):
            events.append(loaded.value)
    return events


def write_once(path: Path, data: bytes) -> RuntimeResult:
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}"
        descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(temporary, path)
        return _ok(path)
    except FileExistsError:
        return _failure("event_identity_collision", "event sequence was acquired concurrently")
    except OSError as error:
        return _failure("persistence_unavailable", f"cannot persist {path.name}", str(error))
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def generate_review_id() -> str:
    stamp = _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    return f"{stamp}-{secrets.token_hex(4)}"


# ---------------------------------------------------------------- implement hand-off


def _main_checkout(repo: Path) -> RuntimeResult:
    common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0:
        return _failure("repository_unavailable", "path is not a Git repository", common.stderr.strip())
    common_directory = Path(common.stdout.strip()).resolve()
    if common_directory.name != ".git":
        return _failure("repository_identity_invalid", "Git common directory is not a main checkout .git")
    return _ok(common_directory.parent)


def load_review(repo: Path, *, plan_id: str, attempt_id: str) -> RuntimeResult:
    """Read the implement evidence of one execution; nothing is written here."""
    checkout = _main_checkout(repo)
    if not checkout.ok:
        return checkout
    main_checkout = checkout.value
    evidence_path = main_checkout.joinpath(*EXECUTIONS.parts, plan_id, attempt_id)
    if not evidence_path.is_dir():
        return _failure("evidence_missing", "implement evidence directory does not exist", str(evidence_path))
    binding = _read_json(evidence_path / "binding.json")
    if not binding.ok:
        return binding
    events = _events_in(evidence_path)
    if not events:
        return _failure("evidence_missing", "implement evidence has no events")
    return _ok(
        Review(
            main_checkout=main_checkout,
            plan_id=plan_id,
            attempt_id=attempt_id,
            evidence_path=evidence_path,
            review_path=evidence_path / REVIEW_DIR,
            binding=binding.value,
            implement_events=events,
            worktree=Path(binding.value["worktree"]),
        )
    )


def verify_hand_off(review: Review, *, check_specs: bool = True) -> RuntimeResult:
    """The checks review.md requires before any finding is written.

    Re-review passes check_specs=False: a spec revision there must reach the durable
    findings_stale event instead of dying as a plain command error.
    """
    last = review.implement_events[-1]
    if last.get("event_type") != IMPLEMENT_TERMINAL_EVENT:
        return _failure(
            "implementation_incomplete",
            "the last implement event is not implementation_green",
            last.get("event_type"),
        )
    plan = review.binding["plan"]
    plan_path = review.main_checkout.joinpath(*PurePosixPath(plan["path"]).parts)
    if not plan_path.is_file() or _file_identity(plan_path) != plan["content_identity"]:
        return _failure("plan_drift", "the plan differs from the one the implementation was bound to", plan["path"])
    if check_specs:
        for spec in review.binding["specs"]:
            spec_path = review.main_checkout.joinpath(*PurePosixPath(spec["path"]).parts)
            if not spec_path.is_file() or _file_identity(spec_path) != spec["content_identity"]:
                return _failure("spec_drift", "a specification differs from the approved version", spec["path"])
    if not review.worktree.is_dir():
        return _failure("worktree_missing", "the implement worktree does not exist", str(review.worktree))
    branch = _git(review.worktree, "rev-parse", "--abbrev-ref", "HEAD")
    if branch.returncode != 0 or branch.stdout.strip() != review.binding["branch"]:
        return _failure(
            "branch_mismatch",
            "the worktree is not on the bound branch",
            {"expected": review.binding["branch"], "observed": branch.stdout.strip()},
        )
    return _ok(last)


# ---------------------------------------------------------------- review evidence


def review_events(review: Review) -> list[dict]:
    return _events_in(review.review_path)


def append_review_event(review: Review, event_type: str, details: dict[str, Any]) -> RuntimeResult:
    events = review_events(review)
    previous = events[-1] if events else None
    if previous is None and event_type != "review-bound":
        return _failure("review_not_bound", "the review has not been bound yet")
    candidate = {
        "version": 1,
        "sequence": len(events) + 1,
        "event_type": event_type,
        "review_id": previous["review_id"] if previous else details.pop("review_id"),
        "plan_identity": review.binding["plan"]["content_identity"],
        "spec_identities": {spec["path"]: spec["content_identity"] for spec in review.binding["specs"]},
        "previous_identity": previous["content_identity"] if previous else None,
        **details,
    }
    sealed = review_model.seal_review_event(candidate, previous)
    if not sealed.ok:
        return _failure(sealed.error.code, sealed.error.message, sealed.error.field)
    target = review.review_path / f"{candidate['sequence']:06d}-{event_type}.json"
    persisted = write_once(target, review_model.canonical_json(sealed.value))
    if not persisted.ok:
        return persisted
    return _ok(sealed.value)


def review_facts(review: Review) -> dict[str, Any]:
    events = review_events(review)
    return {
        "review_id": events[0]["review_id"] if events else None,
        "events": len(events),
        "last_event": events[-1]["event_type"] if events else None,
        "path": str(review.review_path),
    }


def _review_is_finished(events: list[dict]) -> bool:
    return bool(events) and events[-1]["event_type"] in review_model.TERMINAL_EVENT_TYPES


def bind_review(
    review: Review, *, model: str, model_source: str, continue_existing: bool
) -> RuntimeResult:
    if not review_model._matches(review_model.MODEL_ID, model):
        return _failure("model_id_invalid", "model must be a full model id, not an alias", model)
    if model_source not in review_model.MODEL_SOURCES:
        return _failure("model_source_invalid", f"model source must be one of {review_model.MODEL_SOURCES}", model_source)
    verified = verify_hand_off(review)
    if not verified.ok:
        return verified
    existing = review_events(review)
    if existing:
        facts = review_facts(review)
        if _review_is_finished(existing):
            return _failure("review_finished", "this execution's review already ended", facts)
        if not continue_existing:
            return _failure("review_in_progress", "an unfinished review exists; the human decides whether to continue", facts)
        return _ok(facts)
    bound = append_review_event(
        review,
        "review-bound",
        {"review_id": generate_review_id(), "implement_event_identity": verified.value["content_identity"]},
    )
    if not bound.ok:
        return bound
    selected = append_review_event(review, "model-selected", {"model": model, "model_source": model_source})
    if not selected.ok:
        return selected
    return _ok(review_facts(review))


# ---------------------------------------------------------------- first review inputs


def _diff_paths(review: Review) -> RuntimeResult:
    base = review.binding["base_head"]
    names = _git(review.worktree, "diff", "--name-only", f"{base}..HEAD")
    if names.returncode != 0:
        return _failure("diff_unavailable", "the implementation diff could not be read", names.stderr.strip())
    return _ok(sorted(line for line in names.stdout.splitlines() if line))


def _diff_line_count(review: Review) -> int:
    base = review.binding["base_head"]
    numstat = _git(review.worktree, "diff", "--numstat", f"{base}..HEAD")
    total = 0
    for line in numstat.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            total += sum(int(part) for part in parts[:2] if part.isdigit())
    return total


def _profile_for(path: str) -> str:
    return SKILL_PROFILE if PurePosixPath(path).parts[:1] == ("skills",) else DEFAULT_PROFILE


def _profile_identities(profile_dir: Path, names: list[str]) -> RuntimeResult:
    identities: dict[str, str] = {}
    for name in sorted(names):
        candidate = profile_dir / f"{name}.md"
        if not candidate.is_file():
            return _failure("profile_missing", "the selected profile file does not exist", str(candidate))
        identities[name] = _file_identity(candidate)
    return _ok(identities)


def review_inputs(
    review: Review,
    *,
    level: str,
    profile: str | None,
    max_diff_lines: int | None,
    profile_dir: Path,
) -> RuntimeResult:
    """What the first review reads: the diff, grouped by the profile that applies to each file."""
    if level not in review_model.LEVELS:
        return _failure("level_invalid", f"level must be one of {review_model.LEVELS}", level)
    verified = verify_hand_off(review)
    if not verified.ok:
        return verified
    paths = _diff_paths(review)
    if not paths.ok:
        return paths
    if max_diff_lines is not None:
        lines = _diff_line_count(review)
        if lines > max_diff_lines:
            return _failure(
                "input_too_large",
                "the diff exceeds the threshold; split the plan instead of the review",
                {"lines": lines, "max_diff_lines": max_diff_lines},
            )
    profiles: dict[str, list[str]] = {}
    for path in paths.value:
        profiles.setdefault(profile or _profile_for(path), []).append(path)
    identities = _profile_identities(profile_dir, list(profiles))
    if not identities.ok:
        return identities
    head = _git(review.worktree, "rev-parse", "HEAD").stdout.strip()
    return _ok(
        {
            "level": level,
            "base": review.binding["base_head"],
            "head": head,
            "paths": paths.value,
            "profiles": {name: sorted(files) for name, files in sorted(profiles.items())},
            "profile_identities": identities.value,
            "profile_dir": str(profile_dir),
        }
    )


# ---------------------------------------------------------------- oracles


def _oracle_command(oracle: dict) -> list[str]:
    if oracle["kind"] == "test":
        return ["python3", "-m", "unittest", oracle["test"]]
    return shlex.split(oracle["command"])


def _oracle_unsafe_reason(command: list[str]) -> str | None:
    for part in command:
        if CREDENTIAL_ASSIGNMENT.search(part.encode("utf-8")):
            return "a credential-shaped argument"
        if part.startswith("/") or part.startswith("~"):
            return f"an absolute path: {part}"
        if ".." in PurePosixPath(part).parts:
            return f"a path leaving the worktree: {part}"
    return None


def run_oracle(review: Review, oracle: dict) -> RuntimeResult:
    """Run one finding's oracle inside the worktree; only the exit code and a short tail survive."""
    command = _oracle_command(oracle)
    unsafe = _oracle_unsafe_reason(command)
    if unsafe is not None:
        return _failure("oracle_command_unsafe", f"the oracle command carries {unsafe}")
    cwd = review.worktree.joinpath(*PurePosixPath(oracle.get("cwd", ".")).parts)
    try:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=ORACLE_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return _failure("oracle_not_executable", "the oracle could not be executed", str(error))
    tail = (completed.stdout + completed.stderr).strip().splitlines()[-1:] or [""]
    return _ok({"exit_code": completed.returncode, "passed": completed.returncode == 0, "tail": tail[0][:200]})


# ---------------------------------------------------------------- fixing the findings set


def _fixed_findings_event(events: list[dict]) -> dict | None:
    return next((event for event in events if event["event_type"] == "findings-fixed"), None)


def _model_selection(events: list[dict]) -> dict | None:
    return next((event for event in reversed(events) if event["event_type"] == "model-selected"), None)


def _read_findings_input(path: Path) -> RuntimeResult:
    loaded = _read_json(path)
    if not loaded.ok:
        return loaded
    value = loaded.value
    if not isinstance(value, dict) or not isinstance(value.get("findings"), list):
        return _failure("findings_input_invalid", "the findings file needs a findings list")
    return _ok(value)


def admit_findings(review: Review, findings: list[dict], *, level: str) -> RuntimeResult:
    """Validate findings and keep only those whose oracle fails now (or that a human must judge)."""
    validated: list[dict] = []
    for raw in findings:
        checked = review_model.validate_finding(raw)
        if not checked.ok:
            return _failure(checked.error.code, checked.error.message, checked.error.field)
        if level == "light" and checked.value["severity"] not in LIGHT_SEVERITIES:
            return _failure(
                "level_excludes_severity",
                "a light review collects only security and critical findings",
                checked.value["severity"],
            )
        validated.append(checked.value)
    for finding in validated:
        if finding["action"] != "human_judgment":
            unsafe = _oracle_unsafe_reason(_oracle_command(finding["oracle"]))
            if unsafe is not None:
                return _failure("oracle_command_unsafe", f"the oracle command carries {unsafe}", finding["id"])
    admitted: list[dict] = []
    not_admitted: list[dict] = []
    for finding in validated:
        if finding["action"] == "human_judgment":
            admitted.append(finding)
            continue
        outcome = run_oracle(review, finding["oracle"])
        if not outcome.ok:
            return outcome
        if outcome.value["passed"]:
            not_admitted.append({"id": finding["id"], "reason": "oracle_already_passing"})
        else:
            admitted.append(finding)
    return _ok({"admitted": admitted, "not_admitted": not_admitted})


def register_findings(
    review: Review,
    *,
    findings_path: Path,
    level: str,
    profile: str | None,
    profile_dir: Path,
) -> RuntimeResult:
    if level not in review_model.LEVELS:
        return _failure("level_invalid", f"level must be one of {review_model.LEVELS}", level)
    verified = verify_hand_off(review)
    if not verified.ok:
        return verified
    events = review_events(review)
    if not events:
        return _failure("review_not_bound", "bind the review before registering findings")
    if _review_is_finished(events):
        return _failure("review_finished", "this execution's review already ended", review_facts(review))
    if _fixed_findings_event(events) is not None:
        return _failure("findings_already_fixed", "the findings set is fixed; re-review with reverify")
    selection = _model_selection(events)
    if selection is None:
        return _failure("model_not_selected", "the reviewing model was not recorded")
    inputs = review_inputs(review, level=level, profile=profile, max_diff_lines=None, profile_dir=profile_dir)
    if not inputs.ok:
        return inputs
    loaded = _read_findings_input(findings_path)
    if not loaded.ok:
        return loaded
    admitted = admit_findings(review, loaded.value["findings"], level=level)
    if not admitted.ok:
        return admitted
    security = loaded.value.get("security_check")
    if not isinstance(security, dict) or security.get("completed") is not True:
        incomplete = append_review_event(review, "review-incomplete", {"reason": "security_check_incomplete"})
        if not incomplete.ok:
            return incomplete
        return _failure(
            "security_check_incomplete",
            "the mandatory security check is not finished; the review stays incomplete and resumable",
        )
    findings = admitted.value["admitted"]
    fixed = append_review_event(
        review,
        "findings-fixed",
        {
            "findings": findings,
            "findings_identity": review_model.findings_identity(findings),
            "model": selection["model"],
            "model_source": selection["model_source"],
            "level": level,
            "profile_identities": inputs.value["profile_identities"],
            "reviewed_paths": inputs.value["paths"],
        },
    )
    if not fixed.ok:
        return fixed
    return _ok(
        {
            "findings_identity": fixed.value["findings_identity"],
            "admitted": [finding["id"] for finding in findings],
            "not_admitted": admitted.value["not_admitted"],
            "groups": review_model.group_by_root_cause(findings),
        }
    )


# ---------------------------------------------------------------- second reviewer


def _second_reviewer_package(review: Review) -> RuntimeResult:
    plan_path = review.main_checkout.joinpath(*PurePosixPath(review.binding["plan"]["path"]).parts)
    base = review.binding["base_head"]
    diff = _git(review.worktree, "diff", f"{base}..HEAD")
    if diff.returncode != 0:
        return _failure("diff_unavailable", "the implementation diff could not be read", diff.stderr.strip())
    package = (
        "# Second reviewer input\n\n"
        "Review the change below against the plan. Report problems only; do not fix.\n\n"
        "## Plan\n\n" + plan_path.read_text(encoding="utf-8") + "\n\n## Diff\n\n```diff\n" + diff.stdout + "\n```\n"
    )
    if CREDENTIAL_ASSIGNMENT.search(package.encode("utf-8")):
        return _failure("secret_detected", "the package resembles a credential assignment; nothing was sent")
    return _ok(package)


def second_opinion(
    review: Review, *, second_reviewer: str, second_model: str, command: str
) -> RuntimeResult:
    if review_model.MODEL_ID.fullmatch(second_model) is None:
        return _failure("model_id_invalid", "second model must be a full model id, not an alias", second_model)
    verified = verify_hand_off(review)
    if not verified.ok:
        return verified
    events = review_events(review)
    if not events:
        return _failure("review_not_bound", "bind the review before asking a second reviewer")
    if _fixed_findings_event(events) is not None:
        return _failure("findings_already_fixed", "a second reviewer runs only alongside the first review")
    package = _second_reviewer_package(review)
    if not package.ok:
        return package
    scratch = review.main_checkout.joinpath(*REVIEW_SCRATCH.parts, events[0]["review_id"])
    scratch.mkdir(parents=True, exist_ok=True)
    package_path = scratch / f"second-reviewer-{second_reviewer}-input.md"
    output_path = scratch / f"second-reviewer-{second_reviewer}-output.txt"
    package_path.write_text(package.value, encoding="utf-8")
    try:
        completed = subprocess.run(
            [*shlex.split(command), str(package_path)],
            cwd=review.worktree,
            capture_output=True,
            text=True,
            timeout=ORACLE_TIMEOUT_SECONDS,
            check=False,
        )
        available = completed.returncode == 0
        output = completed.stdout
    except (OSError, subprocess.TimeoutExpired):
        available = False
        output = ""
    if not available:
        warned = append_review_event(review, "warning", {"reason": "second_reviewer_unavailable"})
        if not warned.ok:
            return warned
        return _ok({"warning": "second_reviewer_unavailable", "package": str(package_path)})
    output_path.write_text(output, encoding="utf-8")
    return _ok(
        {
            "second_reviewer": second_reviewer,
            "second_model": second_model,
            "package": str(package_path),
            "output": str(output_path),
        }
    )


# ---------------------------------------------------------------- re-review of the diff


def _reverify_boundary(review: Review, events: list[dict]) -> str:
    """The last commit any earlier round has seen; fixes after it are the new input."""
    for event in reversed(events):
        if event["event_type"] in {"reverify", "findings-added"} and event["commits"]:
            return event["commits"][-1]
    return review.implement_events[-1]["commits"][-1]


def _fix_commits(review: Review, boundary: str) -> RuntimeResult:
    listed = _git(review.worktree, "rev-list", "--reverse", f"{boundary}..HEAD")
    if listed.returncode != 0:
        return _failure("fix_commits_unavailable", "fix commits could not be listed", listed.stderr.strip())
    commits = []
    for sha in (line for line in listed.stdout.splitlines() if line):
        trailers = _git(review.worktree, "show", "-s", "--format=%(trailers:key=Finding,valueonly)", sha)
        paths = _git(review.worktree, "show", "--name-only", "--format=", sha)
        if trailers.returncode != 0 or paths.returncode != 0:
            return _failure("fix_commits_unavailable", "a fix commit could not be read", sha)
        commits.append(
            {
                "sha": sha,
                "finding_ids": [line.strip() for line in trailers.stdout.splitlines() if line.strip()],
                "paths": [line for line in paths.stdout.splitlines() if line],
            }
        )
    return _ok(commits)


def _current_findings(events: list[dict]) -> dict[str, dict]:
    """The set as of the latest event: fixed findings plus introduced ones, states applied."""
    findings: dict[str, dict] = {}
    for event in events:
        if event["event_type"] in {"findings-fixed", "findings-added"}:
            for finding in event["findings"]:
                findings[finding["id"]] = dict(finding)
        elif event["event_type"] == "reverify":
            for verdict in event["verdicts"]:
                finding = findings.get(verdict["finding_id"])
                if finding is None:
                    continue
                finding["state"] = verdict["state"]
                finding["oracle_failures"] = verdict.get("oracle_failures", finding.get("oracle_failures", 0))
                if verdict.get("escalated"):
                    finding["action"] = "human_judgment"
        elif event["event_type"] == "decision":
            finding = findings.get(event["finding_id"])
            if finding is not None:
                finding["state"] = "closed"
    return findings


def _reviewing_context(review: Review) -> RuntimeResult:
    verified = verify_hand_off(review, check_specs=False)
    if not verified.ok:
        return verified
    events = review_events(review)
    if not events:
        return _failure("review_not_bound", "bind the review first")
    if _review_is_finished(events):
        return _failure("review_finished", "this execution's review already ended", review_facts(review))
    if _fixed_findings_event(events) is None:
        return _failure("findings_not_fixed", "fix the findings set before re-reviewing")
    return _ok(events)


def _open_human_decisions(findings: dict[str, dict]) -> list[str]:
    return [
        finding["id"]
        for finding in findings.values()
        if finding["state"] == "open" and finding["action"] == "human_judgment"
    ]


def reverify(review: Review, *, max_failures: int | None) -> RuntimeResult:
    context = _reviewing_context(review)
    if not context.ok:
        return context
    status = _git(review.worktree, "status", "--porcelain")
    if status.returncode != 0:
        return _failure("repository_unavailable", "the worktree state could not be read", status.stderr.strip())
    if status.stdout.strip():
        return _failure(
            "worktree_dirty",
            "uncommitted changes in the worktree; commit them so every verdict attaches to a commit",
        )
    events = context.value
    fixed = _fixed_findings_event(events)
    observed = {
        spec["path"]: _file_identity(review.main_checkout.joinpath(*PurePosixPath(spec["path"]).parts))
        for spec in review.binding["specs"]
    }
    findings = _current_findings(events)
    if observed != fixed["spec_identities"]:
        stale_verdicts = []
        for finding in findings.values():
            if finding["state"] != "open":
                continue
            staled = review_model.transition(finding, "stale", cause="spec_revised")
            if not staled.ok:
                return _failure(staled.error.code, staled.error.message, staled.error.field)
            stale_verdicts.append({"finding_id": finding["id"], "state": staled.value["state"]})
        recorded = append_review_event(
            review, "findings_stale", {"observed_spec_identities": observed, "verdicts": stale_verdicts}
        )
        if not recorded.ok:
            return recorded
        return _failure("findings_stale", "a specification the set relies on was revised; the human decides")
    commits = _fix_commits(review, _reverify_boundary(review, events))
    if not commits.ok:
        return commits
    for commit in commits.value:
        if not commit["finding_ids"]:
            return _failure(
                "commit_without_finding_trailer",
                "a fix commit names no finding; the related diff is not guessed",
                commit["sha"],
            )
        for finding_id in commit["finding_ids"]:
            if finding_id not in findings:
                return _failure("finding_not_in_set", "the fixed set gains no findings during re-review", finding_id)
    reviewed = set(fixed["reviewed_paths"])
    outside = sorted({path for commit in commits.value for path in commit["paths"] if path not in reviewed})
    shas = [commit["sha"] for commit in commits.value]
    if outside:
        candidate = append_review_event(review, "rereview-candidate", {"commits": shas, "paths": outside})
        if not candidate.ok:
            return candidate
    verdicts: list[dict[str, Any]] = []
    for finding in findings.values():
        if finding["state"] != "open":
            continue
        if finding["action"] == "human_judgment":
            verdicts.append(
                {"finding_id": finding["id"], "state": "open", "oracle_failures": finding.get("oracle_failures", 0)}
            )
            continue
        outcome = run_oracle(review, finding["oracle"])
        if not outcome.ok:
            return outcome
        if outcome.value["passed"]:
            closed = review_model.transition(finding, "closed", cause="oracle_passed")
            if not closed.ok:
                return _failure(closed.error.code, closed.error.message, closed.error.field)
            verdicts.append(
                {"finding_id": finding["id"], "state": "closed", "oracle_failures": finding.get("oracle_failures", 0)}
            )
            continue
        failures = finding.get("oracle_failures", 0) + 1
        verdict = {"finding_id": finding["id"], "state": "open", "oracle_failures": failures}
        if max_failures is not None and failures >= max_failures:
            # Not "no convergence" but "not fixed": the finding is promoted to a human decision.
            verdict["escalated"] = True
        verdicts.append(verdict)
    recorded = append_review_event(review, "reverify", {"commits": shas, "verdicts": verdicts})
    if not recorded.ok:
        return recorded
    after = _current_findings(review_events(review))
    result: dict[str, Any] = {
        "verdicts": verdicts,
        "open": sorted(f["id"] for f in after.values() if f["state"] == "open"),
        "closed": sorted(f["id"] for f in after.values() if f["state"] == "closed"),
        "human_decisions": _open_human_decisions(after),
    }
    if outside:
        result["rereview_candidates"] = {"commits": shas, "paths": outside}
    return _ok(result)


def _join_frozen_set(review: Review, events: list[dict], findings: list[dict]) -> RuntimeResult:
    """Late findings join the set under the same fails-now admission as the first review."""
    level = _fixed_findings_event(events)["level"]
    admitted = admit_findings(review, findings, level=level)
    if not admitted.ok:
        return admitted
    head = _git(review.worktree, "rev-parse", "HEAD").stdout.strip()
    added = append_review_event(
        review, "findings-added", {"findings": admitted.value["admitted"], "commits": [head]}
    )
    if not added.ok:
        return added
    return _ok(
        {
            "added": [finding["id"] for finding in admitted.value["admitted"]],
            "not_added": admitted.value["not_admitted"],
        }
    )


def merge_findings(review: Review, *, findings_path: Path) -> RuntimeResult:
    """A finishing review's findings merge into the frozen set and close by re-review."""
    context = _reviewing_context(review)
    if not context.ok:
        return context
    loaded = _read_findings_input(findings_path)
    if not loaded.ok:
        return loaded
    return _join_frozen_set(review, context.value, loaded.value["findings"])


def defer_findings(review: Review, *, findings_path: Path, introduced: bool) -> RuntimeResult:
    context = _reviewing_context(review)
    if not context.ok:
        return context
    events = context.value
    loaded = _read_findings_input(findings_path)
    if not loaded.ok:
        return loaded
    if introduced:
        return _join_frozen_set(review, events, loaded.value["findings"])
    deferred: list[dict] = []
    for raw in loaded.value["findings"]:
        checked = review_model.validate_finding(raw)
        if not checked.ok:
            return _failure(checked.error.code, checked.error.message, checked.error.field)
        moved = review_model.transition(checked.value, "deferred", cause="deferred")
        if not moved.ok:
            return _failure(moved.error.code, moved.error.message, moved.error.field)
        deferred.append(moved.value)
    recorded = append_review_event(review, "deferred", {"findings": deferred})
    if not recorded.ok:
        return recorded
    return _ok({"deferred": [finding["id"] for finding in deferred]})


def decide_finding(review: Review, *, finding_id: str, result: str) -> RuntimeResult:
    context = _reviewing_context(review)
    if not context.ok:
        return context
    findings = _current_findings(context.value)
    finding = findings.get(finding_id)
    if finding is None:
        return _failure("finding_not_in_set", "no such finding in the fixed set", finding_id)
    closed = review_model.transition(finding, "closed", cause="human_decision")
    if not closed.ok:
        return _failure(closed.error.code, closed.error.message, closed.error.field)
    recorded = append_review_event(review, "decision", {"finding_id": finding_id, "result": result})
    if not recorded.ok:
        return recorded
    after = _current_findings(review_events(review))
    return _ok(
        {"finding_id": finding_id, "result": result, "remaining_human_decisions": _open_human_decisions(after)}
    )


# ---------------------------------------------------------------- command line


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _print_failure(result: RuntimeResult) -> int:
    error = result.error
    payload: dict[str, Any] = {"state": "stopped", "reason": error.code, "message": error.message}
    if error.detail is not None:
        payload["review" if error.code in {"review_in_progress", "review_finished"} else "detail"] = error.detail
    _print(payload)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review runtime")
    commands = parser.add_subparsers(dest="command", required=True)

    bind = commands.add_parser("bind", help="verify the implement hand-off and start the review record")
    bind.add_argument("--repo", required=True)
    bind.add_argument("--plan-id", required=True)
    bind.add_argument("--attempt-id", required=True)
    bind.add_argument("--model", required=True)
    bind.add_argument("--model-source", required=True)
    bind.add_argument("--continue", dest="continue_existing", action="store_true")

    inputs = commands.add_parser("inputs", help="list what the first review reads and which profile applies")
    register = commands.add_parser("register", help="admit findings whose oracle fails now and fix the set")
    for sub in (inputs, register):
        sub.add_argument("--repo", required=True)
        sub.add_argument("--plan-id", required=True)
        sub.add_argument("--attempt-id", required=True)
        sub.add_argument("--level", required=True)
        sub.add_argument("--profile")
        sub.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    inputs.add_argument("--max-diff-lines", type=int)
    register.add_argument("--findings", required=True)

    second = commands.add_parser("second-opinion", help="send the plan and diff to a second reviewer once")
    second.add_argument("--repo", required=True)
    second.add_argument("--plan-id", required=True)
    second.add_argument("--attempt-id", required=True)
    second.add_argument("--second-reviewer", required=True)
    second.add_argument("--second-model", required=True)
    second.add_argument("--command", dest="runner", required=True)

    reverify_parser = commands.add_parser("reverify", help="run the oracles of open findings against the fix commits")
    reverify_parser.add_argument("--max-failures", type=int)
    defer_parser = commands.add_parser("defer", help="record side findings apart, or add introduced risks to the set")
    defer_parser.add_argument("--findings", required=True)
    defer_parser.add_argument("--introduced", action="store_true")
    merge_parser = commands.add_parser("merge", help="merge a finishing review's findings into the frozen set")
    merge_parser.add_argument("--findings", required=True)
    decide_parser = commands.add_parser("decide", help="record the human decision that closes a human-judgment finding")
    decide_parser.add_argument("--finding", required=True)
    decide_parser.add_argument("--result", required=True, choices=["accepted", "rejected"])
    for sub in (reverify_parser, defer_parser, merge_parser, decide_parser):
        sub.add_argument("--repo", required=True)
        sub.add_argument("--plan-id", required=True)
        sub.add_argument("--attempt-id", required=True)

    args = parser.parse_args(argv)
    loaded = load_review(Path(args.repo), plan_id=args.plan_id, attempt_id=args.attempt_id)
    if not loaded.ok:
        return _print_failure(loaded)
    review = loaded.value

    if args.command == "bind":
        result = bind_review(
            review,
            model=args.model,
            model_source=args.model_source,
            continue_existing=args.continue_existing,
        )
        if not result.ok:
            return _print_failure(result)
        _print({"state": "bound", **result.value})
        return 0
    if args.command == "inputs":
        result = review_inputs(
            review,
            level=args.level,
            profile=args.profile,
            max_diff_lines=args.max_diff_lines,
            profile_dir=Path(args.profile_dir),
        )
    elif args.command == "register":
        result = register_findings(
            review,
            findings_path=Path(args.findings),
            level=args.level,
            profile=args.profile,
            profile_dir=Path(args.profile_dir),
        )
    elif args.command == "second-opinion":
        result = second_opinion(
            review,
            second_reviewer=args.second_reviewer,
            second_model=args.second_model,
            command=args.runner,
        )
    elif args.command == "reverify":
        result = reverify(review, max_failures=args.max_failures)
    elif args.command == "defer":
        result = defer_findings(review, findings_path=Path(args.findings), introduced=args.introduced)
    elif args.command == "merge":
        result = merge_findings(review, findings_path=Path(args.findings))
    elif args.command == "decide":
        result = decide_finding(review, finding_id=args.finding, result=args.result)
    else:
        return 2
    if not result.ok:
        return _print_failure(result)
    _print(result.value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
