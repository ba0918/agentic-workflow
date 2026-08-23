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
GATE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SECTION_NAME = re.compile(r"「([^「」]+)」")
PLAN_STORE = PurePosixPath(".agents/artifacts/plans")
DRAFT_STORE = PurePosixPath(".agents/tmp/plans")
DRAFT_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
INDEX_NAME = "open-plans.json"
HUMAN_GATE_TIMINGS = {"before_edit", "before_commit", "before_implementation_green"}
HUMAN_GATE_RESULTS = ("approved", "rejected")


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


class InvalidHumanGateDeclaration(PlanArtifactError):
    """A plan step contains a malformed human-gate declaration."""


class DraftConflict(PlanArtifactError):
    """A draft already exists and the caller did not name its identity."""


class DraftReceipt(NamedTuple):
    path: Path
    content_identity: str


class RegisteredPlan(NamedTuple):
    plan_id: str
    path: str
    revision: int
    content_identity: str
    state: str
    text: str


class HumanGateTarget(NamedTuple):
    kind: str
    paths: tuple[str, ...]
    content_identity: str | None


class HumanGateDeclaration(NamedTuple):
    gate_id: str
    step_id: str
    sections: tuple[str, ...]
    criterion: str
    target: HumanGateTarget
    timing: str
    allowed_results: tuple[str, ...]


def content_identity(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _target_specification_block(text: str) -> str:
    match = re.search(r"^\*\*対象仕様:\*\*[ \t]*\n+(.*?)(?=\n\s*\n|\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        return ""
    return match.group(1)


def _target_specification_sections(text: str) -> set[str]:
    sections: set[str] = set()
    for line in re.finditer(r"^\s*- 該当する節:(.*)$", _target_specification_block(text), re.MULTILINE):
        sections.update(SECTION_NAME.findall(line.group(1)))
    return sections


def _human_gate_target(value: object) -> HumanGateTarget:
    if not isinstance(value, dict) or value.get("kind") not in {"files", "event"}:
        raise InvalidHumanGateDeclaration("human gate target kind is invalid")
    if value["kind"] == "files":
        if set(value) != {"kind", "paths"}:
            raise InvalidHumanGateDeclaration("human gate target has unknown or missing fields")
        paths = value["paths"]
        if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
            raise InvalidHumanGateDeclaration("human gate file paths must be a non-empty unique list")
        for path in paths:
            if not isinstance(path, str):
                raise InvalidHumanGateDeclaration("human gate file path must be a string")
            candidate = PurePosixPath(path)
            if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
                raise InvalidHumanGateDeclaration("human gate file path must be repository-relative")
        return HumanGateTarget(kind="files", paths=tuple(paths), content_identity=None)

    if set(value) != {"kind", "content_identity"}:
        raise InvalidHumanGateDeclaration("human gate target has unknown or missing fields")
    identity = value["content_identity"]
    if not isinstance(identity, str) or IDENTITY.fullmatch(identity) is None:
        raise InvalidHumanGateDeclaration("human gate event identity must be immutable")
    return HumanGateTarget(kind="event", paths=(), content_identity=identity)


def read_plan_human_gates(text: str) -> tuple[HumanGateDeclaration, ...]:
    step_matches = list(re.finditer(r"^### ([1-9][0-9]*)\.[^\n]*$", text, re.MULTILINE))
    declarations: list[HumanGateDeclaration] = []
    gate_ids: set[str] = set()
    listed_sections = _target_specification_sections(text)
    for position, step_match in enumerate(step_matches):
        end = step_matches[position + 1].start() if position + 1 < len(step_matches) else len(text)
        step_text = text[step_match.end() : end]
        block = re.search(
            r"^\*\*Human gates:\*\*\s*\n+```json\n(.*?)\n```",
            step_text,
            re.MULTILINE | re.DOTALL,
        )
        if block is None:
            continue
        try:
            value = json.loads(block.group(1))
        except json.JSONDecodeError as error:
            raise InvalidHumanGateDeclaration("human gate declaration is not valid JSON") from error
        if not isinstance(value, dict) or set(value) != {"version", "gates"}:
            raise InvalidHumanGateDeclaration("human gate declaration has unknown or missing fields")
        if value["version"] != 1 or not isinstance(value["gates"], list) or not value["gates"]:
            raise InvalidHumanGateDeclaration("human gate declaration has an invalid version or gates")

        step_id = f"step-{step_match.group(1)}"
        for gate in value["gates"]:
            if not isinstance(gate, dict) or set(gate) != {
                "gate_id",
                "sections",
                "criterion",
                "target",
                "timing",
                "allowed_results",
            }:
                raise InvalidHumanGateDeclaration("human gate has unknown or missing fields")
            gate_id = gate["gate_id"]
            if (
                not isinstance(gate_id, str)
                or GATE_ID.fullmatch(gate_id) is None
                or gate_id in gate_ids
            ):
                raise InvalidHumanGateDeclaration("human gate ids must be unique safe identifiers")
            sections = gate["sections"]
            if (
                not isinstance(sections, list)
                or not sections
                or len(sections) != len(set(sections))
                or any(not isinstance(section, str) for section in sections)
            ):
                raise InvalidHumanGateDeclaration("human gate sections must be a non-empty unique list")
            unlisted = [section for section in sections if section not in listed_sections]
            if unlisted:
                raise InvalidHumanGateDeclaration(
                    "human gate sections must be listed under the plan's target specifications: "
                    + ", ".join(unlisted)
                )
            criterion = gate["criterion"]
            if not isinstance(criterion, str) or not criterion.strip() or len(criterion) > 500:
                raise InvalidHumanGateDeclaration("human gate criterion must be bounded text")
            if gate["timing"] not in HUMAN_GATE_TIMINGS:
                raise InvalidHumanGateDeclaration("human gate timing is invalid")
            if gate["allowed_results"] != list(HUMAN_GATE_RESULTS):
                raise InvalidHumanGateDeclaration("human gate results are invalid")
            gate_ids.add(gate_id)
            declarations.append(
                HumanGateDeclaration(
                    gate_id=gate_id,
                    step_id=step_id,
                    sections=tuple(sections),
                    criterion=criterion,
                    target=_human_gate_target(gate["target"]),
                    timing=gate["timing"],
                    allowed_results=tuple(gate["allowed_results"]),
                )
            )
    return tuple(declarations)


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
    if not _is_within(target, store):
        raise UnsafePlanPath("plan path escapes the plan store")
    return target


def _is_within(path: Path, store: Path) -> bool:
    resolved_store = str(store.resolve(strict=False))
    try:
        return os.path.commonpath((str(path.resolve(strict=False)), resolved_store)) == resolved_store
    except ValueError:
        return False


def _validate_plan_identity(plan_id: str, revision: int) -> None:
    if PLAN_ID.fullmatch(plan_id) is None:
        raise PlanArtifactError("plan id must contain exactly 14 digits")
    if not isinstance(revision, int) or revision < 1:
        raise PlanArtifactError("plan revision must be a positive integer")


def _draft_path(project_root: Path, plan_id: str, revision: int, slug: str) -> Path:
    _validate_plan_identity(plan_id, revision)
    if DRAFT_SLUG.fullmatch(slug) is None:
        raise UnsafePlanPath("draft slug must be lowercase words joined by hyphens")
    root = project_root.resolve()
    store = root.joinpath(*DRAFT_STORE.parts)
    target = store / f"{plan_id}_{slug}_r{revision}_draft.md"
    for path in (root / ".agents", root / ".agents/tmp", store, target):
        if path.is_symlink():
            raise UnsafePlanPath(f"symlink is not allowed: {path}")
    return target


def save_draft(
    project_root: Path,
    *,
    plan_id: str,
    revision: int,
    slug: str,
    text: str,
    replace_identity: str | None = None,
) -> DraftReceipt:
    target = _draft_path(project_root, plan_id, revision, slug)
    if target.exists():
        existing_identity = content_identity(target.read_text(encoding="utf-8"))
        if replace_identity is None:
            raise DraftConflict("a draft already exists; name its identity to replace it")
        if existing_identity != replace_identity:
            raise DraftConflict("the existing draft differs from the identity named for replacement")
    _atomic_write(target, text)
    return DraftReceipt(target, content_identity(text))


def _approved_draft(project_root: Path, source: Path) -> Path:
    root = project_root.resolve()
    store = root.joinpath(*DRAFT_STORE.parts)
    candidate = Path(source)
    if candidate.is_symlink():
        raise UnsafePlanPath(f"symlink is not allowed: {candidate}")
    resolved = candidate.resolve(strict=False)
    if not _is_within(resolved, store) or resolved.parent != store.resolve(strict=False):
        raise UnsafePlanPath("an approved draft must live directly under the temporary plan store")
    if not resolved.is_file():
        raise PlanArtifactError(f"approved draft does not exist: {candidate}")
    return resolved


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
    source: Path,
    approved_identity: str,
    switch_confirmed: bool,
    worktree_dirty: bool,
) -> Path:
    _validate_plan_identity(plan_id, revision)
    draft = _approved_draft(project_root, source)
    text = draft.read_text(encoding="utf-8")
    actual_identity = content_identity(text)
    if IDENTITY.fullmatch(approved_identity) is None or actual_identity != approved_identity:
        raise IdentityMismatch("approved content identity does not match the draft bytes")

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

    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(draft, target)
    try:
        if content_identity(target.read_text(encoding="utf-8")) != approved_identity:
            raise IdentityMismatch("published plan bytes differ from the approved identity")
        _atomic_write(index_path, _encode_index(index))
    except Exception:
        os.replace(target, draft)
        raise
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a human-approved implementation plan")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("identity", help="read an unwritten draft from stdin and print its identity")

    draft = commands.add_parser("draft", help="save the draft from stdin under .agents/tmp/plans")
    draft.add_argument("--repo", required=True)
    draft.add_argument("--plan-id", required=True)
    draft.add_argument("--revision", required=True, type=int)
    draft.add_argument("--slug", required=True)
    draft.add_argument("--replace-identity")

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
    if args.command == "draft":
        root = Path(args.repo)
        receipt = save_draft(
            root,
            plan_id=args.plan_id,
            revision=args.revision,
            slug=args.slug,
            text=sys.stdin.read(),
            replace_identity=args.replace_identity,
        )
        print(
            json.dumps(
                {
                    "path": receipt.path.relative_to(root.resolve()).as_posix(),
                    "content_identity": receipt.content_identity,
                },
                ensure_ascii=False,
            )
        )
        return 0

    published = publish_plan(
        Path(args.repo),
        plan_id=args.plan_id,
        revision=args.revision,
        relative_path=args.path,
        source=Path(args.source),
        approved_identity=args.approved_identity,
        switch_confirmed=args.switch_confirmed,
        worktree_dirty=args.worktree_dirty,
    )
    print(published)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
