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
import secrets
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
REVIEW_DIR = "review"
IMPLEMENT_TERMINAL_EVENT = "implementation_green"


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


def verify_hand_off(review: Review) -> RuntimeResult:
    """The checks review.md requires before any finding is written."""
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
    return 2


if __name__ == "__main__":
    sys.exit(main())
