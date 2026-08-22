#!/usr/bin/env python3
"""Publish an approved plan and maintain the rebuildable open-plan locator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import NamedTuple


PLAN_ID = re.compile(r"[0-9]{14}")
IDENTITY = re.compile(r"sha256:[0-9a-f]{64}")
PLAN_STORE = PurePosixPath(".agents/artifacts/plans")
INDEX_NAME = "open-plans.json"


class PlanArtifactError(Exception):
    """Base class for plan publication failures."""


class IdentityMismatch(PlanArtifactError):
    """The approved bytes differ from the bytes being published."""


class CurrentPlanConflict(PlanArtifactError):
    """Publishing would silently replace the current plan."""


class DirtyWorktree(PlanArtifactError):
    """A dirty worktree prevents a safe current-plan switch."""


class UnsafePlanPath(PlanArtifactError):
    """The requested plan path escapes or aliases the plan store."""


class InvalidOpenPlanIndex(PlanArtifactError):
    """The open-plan locator is malformed or inconsistent."""


class PlanRegistrationMissing(PlanArtifactError):
    """No locator entry identifies the requested plan."""


class RegisteredPlanMismatch(PlanArtifactError):
    """A registered plan no longer matches its locator entry."""


class RegisteredPlan(NamedTuple):
    plan_id: str
    path: str
    revision: int
    content_identity: str
    state: str
    text: str


def content_identity(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plan_path(project_root: Path, relative_path: str, plan_id: str) -> Path:
    candidate = PurePosixPath(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise UnsafePlanPath("plan path must be repository-relative without traversal")
    if candidate.parent != PLAN_STORE or candidate.suffix != ".md":
        raise UnsafePlanPath("plan path must be a Markdown file directly under the plan store")
    if not candidate.name.startswith(plan_id + "_"):
        raise UnsafePlanPath("plan filename must start with its plan id")

    root = project_root.resolve()
    store = root.joinpath(*PLAN_STORE.parts)
    target = root.joinpath(*candidate.parts)
    for path in (root / ".agents", root / ".agents/artifacts", store, target):
        if path.is_symlink():
            raise UnsafePlanPath(f"symlink is not allowed: {path}")
    try:
        if os.path.commonpath((str(target.resolve(strict=False)), str(store.resolve(strict=False)))) != str(
            store.resolve(strict=False)
        ):
            raise UnsafePlanPath("plan path escapes the plan store")
    except ValueError as error:
        raise UnsafePlanPath("plan path escapes the plan store") from error
    return target


def _empty_index() -> dict:
    return {"version": 1, "current": None, "plans": []}


def _validate_index(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"version", "current", "plans"}:
        raise InvalidOpenPlanIndex("open-plan index has unknown or missing fields")
    if value["version"] != 1:
        raise InvalidOpenPlanIndex("unsupported open-plan index version")
    if value["current"] is not None and (
        not isinstance(value["current"], str) or PLAN_ID.fullmatch(value["current"]) is None
    ):
        raise InvalidOpenPlanIndex("current plan id is invalid")
    if not isinstance(value["plans"], list):
        raise InvalidOpenPlanIndex("plans must be a list")

    ids: set[str] = set()
    current_entries = 0
    for item in value["plans"]:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "path",
            "revision",
            "content_identity",
            "state",
        }:
            raise InvalidOpenPlanIndex("plan entry has unknown or missing fields")
        if PLAN_ID.fullmatch(item["id"]) is None or item["id"] in ids:
            raise InvalidOpenPlanIndex("plan ids must be unique 14-digit values")
        ids.add(item["id"])
        if not isinstance(item["revision"], int) or item["revision"] < 1:
            raise InvalidOpenPlanIndex("plan revision must be a positive integer")
        if not isinstance(item["path"], str):
            raise InvalidOpenPlanIndex("plan path must be a string")
        if not isinstance(item["content_identity"], str) or IDENTITY.fullmatch(
            item["content_identity"]
        ) is None:
            raise InvalidOpenPlanIndex("plan content identity is invalid")
        if item["state"] not in {"current", "held"}:
            raise InvalidOpenPlanIndex("plan state must be current or held")
        if item["state"] == "current":
            current_entries += 1
            if value["current"] != item["id"]:
                raise InvalidOpenPlanIndex("current pointer and plan entry disagree")
    if current_entries > 1 or (value["current"] is None) != (current_entries == 0):
        raise InvalidOpenPlanIndex("open-plan index has an inconsistent current plan")
    return value


def _load_index(path: Path) -> dict:
    if path.is_symlink():
        raise UnsafePlanPath(f"symlink is not allowed: {path}")
    if not path.exists():
        return _empty_index()
    try:
        return _validate_index(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as error:
        raise InvalidOpenPlanIndex("open-plan index is not valid JSON") from error


def read_registered_plan(
    project_root: Path,
    relative_path: str | None = None,
) -> RegisteredPlan:
    store = project_root.resolve().joinpath(*PLAN_STORE.parts)
    index_path = store / INDEX_NAME
    if not index_path.exists():
        raise PlanRegistrationMissing("open-plan locator does not exist")
    index = _load_index(index_path)

    if relative_path is None:
        current = index["current"]
        if current is None:
            raise PlanRegistrationMissing("open-plan locator has no current plan")
        entry = next(item for item in index["plans"] if item["id"] == current)
    else:
        entry = next(
            (item for item in index["plans"] if item["path"] == relative_path),
            None,
        )
        if entry is None:
            raise PlanRegistrationMissing("requested plan is not registered")

    target = _plan_path(project_root, entry["path"], entry["id"])
    if not target.is_file():
        raise RegisteredPlanMismatch("registered plan file does not exist")
    text = target.read_text(encoding="utf-8")
    if content_identity(text) != entry["content_identity"]:
        raise RegisteredPlanMismatch("registered plan identity does not match its bytes")
    return RegisteredPlan(
        plan_id=entry["id"],
        path=entry["path"],
        revision=entry["revision"],
        content_identity=entry["content_identity"],
        state=entry["state"],
        text=text,
    )


def _encode_index(value: dict) -> str:
    ordered = dict(value)
    ordered["plans"] = sorted(value["plans"], key=lambda item: item["id"])
    return json.dumps(ordered, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise UnsafePlanPath(f"target became a symlink: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_plan(
    project_root: Path,
    *,
    plan_id: str,
    revision: int,
    relative_path: str,
    text: str,
    approved_identity: str,
    switch_confirmed: bool,
    worktree_dirty: bool,
) -> Path:
    if PLAN_ID.fullmatch(plan_id) is None:
        raise PlanArtifactError("plan id must contain exactly 14 digits")
    if not isinstance(revision, int) or revision < 1:
        raise PlanArtifactError("plan revision must be a positive integer")
    actual_identity = content_identity(text)
    if IDENTITY.fullmatch(approved_identity) is None or actual_identity != approved_identity:
        raise IdentityMismatch("approved content identity does not match the plan bytes")

    target = _plan_path(project_root, relative_path, plan_id)
    if target.exists():
        raise PlanArtifactError("plan path already exists; revisions are never overwritten")
    store = target.parent
    index_path = store / INDEX_NAME
    index = _load_index(index_path)
    existing = next((item for item in index["plans"] if item["id"] == plan_id), None)
    if existing is not None:
        if revision != existing["revision"] + 1:
            raise PlanArtifactError("a new plan revision must increment the current revision by one")
        if relative_path == existing["path"]:
            raise PlanArtifactError("a plan revision must use a new path")

    current = index["current"]
    if existing is None and current is not None and current != plan_id:
        if not switch_confirmed:
            raise CurrentPlanConflict("switching the current plan requires human confirmation")
        if worktree_dirty:
            raise DirtyWorktree("a dirty worktree must be isolated before switching plans")
        for item in index["plans"]:
            if item["id"] == current:
                item["state"] = "held"

    candidate = {
        "id": plan_id,
        "path": relative_path,
        "revision": revision,
        "content_identity": actual_identity,
        "state": existing["state"] if existing is not None else "current",
    }
    if existing is None:
        index["plans"].append(candidate)
        index["current"] = plan_id
    else:
        index["plans"] = [candidate if item["id"] == plan_id else item for item in index["plans"]]
    _validate_index(index)

    wrote_plan = False
    try:
        _atomic_write(target, text)
        wrote_plan = True
        _atomic_write(index_path, _encode_index(index))
    except Exception:
        if wrote_plan:
            target.unlink(missing_ok=True)
        raise
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a human-approved implementation plan")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("identity", help="read an unwritten draft from stdin and print its identity")

    publish = commands.add_parser("publish", help="publish approved bytes and update the locator")
    publish.add_argument("--repo", required=True)
    publish.add_argument("--plan-id", required=True)
    publish.add_argument("--revision", required=True, type=int)
    publish.add_argument("--path", required=True)
    publish.add_argument("--source", required=True)
    publish.add_argument("--approved-identity", required=True)
    publish.add_argument("--switch-confirmed", action="store_true")
    publish.add_argument("--worktree-dirty", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "identity":
        print(content_identity(sys.stdin.read()))
        return 0

    text = Path(args.source).read_text(encoding="utf-8")
    published = publish_plan(
        Path(args.repo),
        plan_id=args.plan_id,
        revision=args.revision,
        relative_path=args.path,
        text=text,
        approved_identity=args.approved_identity,
        switch_confirmed=args.switch_confirmed,
        worktree_dirty=args.worktree_dirty,
    )
    print(published)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
