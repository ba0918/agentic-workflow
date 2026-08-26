#!/usr/bin/env python3
"""Save a plan draft and publish the approved bytes as the plan of record."""

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
SECTION_NAME = re.compile(r"`([^`]+)`")
PLAN_STORE = PurePosixPath(".agents/artifacts/plans")
DRAFT_STORE = PurePosixPath(".agents/tmp/plans")
DRAFT_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TREE_ENTRY = re.compile(r"[^\s/#][^\s]*")


class PlanArtifactError(Exception):
    """Base class for plan publication failures."""


class IdentityMismatch(PlanArtifactError):
    """The approved bytes differ from the bytes being published."""


class UnsafePlanPath(PlanArtifactError):
    """The requested plan path escapes or aliases the plan store."""


class InvalidPlanFormat(PlanArtifactError):
    """A machine-read part of the plan is missing or malformed."""


class TargetSpecificationMismatch(PlanArtifactError):
    """A target specification named by the plan is missing or has different content."""


class DraftConflict(PlanArtifactError):
    """A draft already exists and the caller did not name its identity."""


class DraftReceipt(NamedTuple):
    path: Path
    content_identity: str


class TargetSpecification(NamedTuple):
    path: str
    content_identity: str
    sections: tuple[str, ...]


class PlanHeader(NamedTuple):
    plan_id: str
    revision: int
    specifications: tuple[TargetSpecification, ...]


def content_identity(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _target_specification_block(text: str) -> str:
    match = re.search(r"^\*\*Target specifications:\*\*[ \t]*\n+(.*?)(?=\n\s*\n|\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        return ""
    return match.group(1)


def _target_specifications(text: str) -> tuple[TargetSpecification, ...]:
    block = _target_specification_block(text)
    items = re.split(r"^- ", block, flags=re.MULTILINE)[1:]
    if not items:
        raise InvalidPlanFormat("**Target specifications:** must list at least one specification")
    specifications = []
    for item in items:
        head, _, details = item.partition("\n")
        path_match = re.fullmatch(r"`([^`]+)`\s*", head)
        if path_match is None:
            raise InvalidPlanFormat(f"Target specifications item must start with a backquoted path: {head.strip()}")
        path = path_match.group(1)
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
            raise InvalidPlanFormat(f"Target specifications path must be repository-relative: {path}")
        identity_match = re.search(r"^\s*- content identity: `([^`]*)`\s*$", details, re.MULTILINE)
        if identity_match is None or IDENTITY.fullmatch(identity_match.group(1)) is None:
            raise InvalidPlanFormat(f"Target specifications item needs a sha256 content identity: {path}")
        sections_match = re.search(r"^\s*- sections:(.*)$", details, re.MULTILINE)
        sections = tuple(SECTION_NAME.findall(sections_match.group(1))) if sections_match else ()
        if not sections:
            raise InvalidPlanFormat(f"Target specifications item needs at least one backquoted name under sections: {path}")
        specifications.append(TargetSpecification(path, identity_match.group(1), sections))
    return tuple(specifications)


def _target_specification_sections(text: str) -> set[str]:
    return {section for spec in _target_specifications(text) for section in spec.sections}


def read_plan_header(text: str) -> PlanHeader:
    plan_id = re.search(r"^\*\*Plan ID:\*\* `([^`]*)`", text, re.MULTILINE)
    if plan_id is None or PLAN_ID.fullmatch(plan_id.group(1)) is None:
        raise InvalidPlanFormat("**Plan ID:** with a 14-digit id is missing")
    revision = re.search(r"^\*\*Plan revision:\*\* `([^`]*)`", text, re.MULTILINE)
    if revision is None or re.fullmatch(r"[1-9][0-9]*", revision.group(1)) is None:
        raise InvalidPlanFormat("**Plan revision:** with a positive integer is missing")
    if re.search(r"^\*\*Target specifications:\*\*", text, re.MULTILINE) is None:
        raise InvalidPlanFormat("**Target specifications:** is missing")
    return PlanHeader(plan_id.group(1), int(revision.group(1)), _target_specifications(text))


def _section_body(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise InvalidPlanFormat(f"## {heading} is missing")
    return match.group(1)


def read_plan_scope(text: str) -> tuple[str, ...]:
    body = _section_body(text, "Scope")
    block = re.search(r"^```text[ \t]*\n(.*?)^```", body, re.MULTILINE | re.DOTALL)
    if block is None:
        raise InvalidPlanFormat("## Scope needs a text code block holding the file tree")
    lines = [line for line in block.group(1).splitlines() if line.strip()]
    if not lines:
        raise InvalidPlanFormat("## Scope file tree is empty")

    paths: list[str] = []
    stack: list[tuple[int, str]] = []
    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        entry = line.strip()
        if TREE_ENTRY.fullmatch(entry) is None or "//" in entry or ".." in entry.split("/"):
            raise InvalidPlanFormat(f"## Scope tree line is not a plain relative path: {line!r}")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if indent > 0 and (not stack or not stack[-1][1].endswith("/")):
            raise InvalidPlanFormat(f"## Scope tree line has no parent directory: {line!r}")
        full = "".join(parent for _, parent in stack) + entry
        stack.append((indent, entry))
        if not entry.endswith("/"):
            paths.append(full)
    return tuple(paths)


def verify_target_specifications(project_root: Path, header: PlanHeader) -> None:
    root = project_root.resolve()
    for spec in header.specifications:
        target = root.joinpath(*PurePosixPath(spec.path).parts)
        if not target.is_file():
            raise TargetSpecificationMismatch(f"target specification does not exist: {spec.path}")
        actual = content_identity(target.read_text(encoding="utf-8"))
        if actual != spec.content_identity:
            raise TargetSpecificationMismatch(
                f"target specification content differs from the plan: {spec.path} (now {actual})"
            )


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


def validate_plan(project_root: Path, text: str) -> None:
    """Reject a plan whose two machine-read parts are unreadable or whose specifications moved.

    The specifications it stands on and the files it may touch are the whole of it
    (docs/spec/plan.md, "機械が決まった書き方で読む箇所は 2 つだけ"). The steps, the completion
    kinds, the human decisions, the id and the revision are prose the agent reads and declares,
    so nothing here compares them with anything.
    """
    read_plan_scope(text)
    verify_target_specifications(project_root, read_plan_header(text))


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
    validate_plan(project_root, text)
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
) -> Path:
    _validate_plan_identity(plan_id, revision)
    draft = _approved_draft(project_root, source)
    text = draft.read_text(encoding="utf-8")
    actual_identity = content_identity(text)
    if IDENTITY.fullmatch(approved_identity) is None or actual_identity != approved_identity:
        raise IdentityMismatch("approved content identity does not match the draft bytes")
    validate_plan(project_root, text)

    target = _plan_path(project_root, relative_path, plan_id)
    if target.exists():
        raise PlanArtifactError("plan path already exists; revisions are never overwritten")

    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(draft, target)
    try:
        if content_identity(target.read_text(encoding="utf-8")) != approved_identity:
            raise IdentityMismatch("published plan bytes differ from the approved identity")
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

    publish = commands.add_parser("publish", help="publish the approved bytes as the plan of record")
    publish.add_argument("--repo", required=True)
    publish.add_argument("--plan-id", required=True)
    publish.add_argument("--revision", required=True, type=int)
    publish.add_argument("--path", required=True)
    publish.add_argument("--source", required=True)
    publish.add_argument("--approved-identity", required=True)
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except PlanArtifactError as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
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
    )
    print(published)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
