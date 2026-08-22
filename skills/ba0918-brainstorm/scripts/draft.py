#!/usr/bin/env python3
"""Save wrap drafts as temporary files the human reads, and publish the approved ones."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from typing import NamedTuple


SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
IDENTITY = re.compile(r"sha256:[0-9a-f]{64}")
DRAFT_STORE = PurePosixPath(".agents/tmp/ideas")
MANIFEST_NAME = "manifest.json"


class DraftError(Exception):
    """Base class for draft failures."""


class UnsafeDraftPath(DraftError):
    """A session id or destination escapes or aliases the allowed stores."""


class DraftConflict(DraftError):
    """A draft already exists and the caller did not name its identity."""


class IdentityMismatch(DraftError):
    """The approved identity does not match the draft or the published bytes."""


class DraftReceipt(NamedTuple):
    path: Path
    destination: str
    content_identity: str


def content_identity(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reject_symlinks(root: Path, relative: PurePosixPath) -> None:
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise UnsafeDraftPath(f"symlink is not allowed: {cursor}")


def _destination(destination: str) -> PurePosixPath:
    candidate = PurePosixPath(destination)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or ".." in candidate.parts
        or destination.endswith("/")
        or candidate.parts[0] == ".agents"
    ):
        raise UnsafeDraftPath("destination must be a repository-relative file outside .agents")
    return candidate


def _session_directory(project_root: Path, session_id: str) -> Path:
    if SESSION_ID.fullmatch(session_id) is None or session_id.startswith("."):
        raise UnsafeDraftPath("unsafe session id")
    root = project_root.resolve()
    relative = DRAFT_STORE / session_id
    _reject_symlinks(root, relative)
    return root.joinpath(*relative.parts)


def _load_manifest(directory: Path) -> dict:
    path = directory / MANIFEST_NAME
    if not path.exists():
        return {"version": 1, "drafts": {}}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or not isinstance(manifest.get("drafts"), dict):
        raise DraftError("draft manifest is malformed")
    return manifest


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
            raise UnsafeDraftPath(f"target became a symlink: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _draft_name(manifest: dict, destination: PurePosixPath) -> str:
    existing = manifest["drafts"].get(str(destination))
    if existing is not None:
        return existing["path"]
    taken = {entry["path"] for entry in manifest["drafts"].values()}
    if destination.name not in taken:
        return destination.name
    return "__".join(destination.parts)


def save_draft(
    project_root: Path,
    *,
    session_id: str,
    destination: str,
    text: str,
    replace_identity: str | None = None,
) -> DraftReceipt:
    target_destination = _destination(destination)
    directory = _session_directory(project_root, session_id)
    manifest = _load_manifest(directory)
    name = _draft_name(manifest, target_destination)
    path = directory / name
    if path.exists():
        existing_identity = content_identity(path.read_text(encoding="utf-8"))
        if replace_identity is None:
            raise DraftConflict("a draft already exists; name its identity to replace it")
        if existing_identity != replace_identity:
            raise DraftConflict("the existing draft differs from the identity named for replacement")
    _atomic_write(path, text)
    identity = content_identity(text)
    manifest["drafts"][str(target_destination)] = {"path": name, "content_identity": identity}
    _atomic_write(directory / MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return DraftReceipt(path, str(target_destination), identity)


def publish_drafts(project_root: Path, *, session_id: str, approved: dict[str, str]) -> list[str]:
    """Move every approved draft onto its destination, all or nothing.

    Existing canonical files are parked under the session directory first so that a
    failure after the first move can put them back; the session directory is removed
    only once every destination has been read back with its approved identity.
    """
    root = project_root.resolve()
    directory = _session_directory(project_root, session_id)
    manifest = _load_manifest(directory)
    if not manifest["drafts"]:
        raise DraftError("no drafts are saved for this session")
    if set(approved) != set(manifest["drafts"]):
        raise IdentityMismatch("approval must name exactly the drafts saved for this session")

    moves: list[tuple[Path, Path, str]] = []
    for destination, entry in manifest["drafts"].items():
        identity = approved[destination]
        source = directory / entry["path"]
        if IDENTITY.fullmatch(identity) is None or not source.is_file():
            raise IdentityMismatch(f"approved draft is unavailable: {destination}")
        if content_identity(source.read_text(encoding="utf-8")) != identity:
            raise IdentityMismatch(f"draft differs from the approved identity: {destination}")
        relative = _destination(destination)
        _reject_symlinks(root, relative)
        moves.append((source, root.joinpath(*relative.parts), identity))

    backups = directory / ".previous"
    completed: list[tuple[Path, Path, Path | None]] = []
    try:
        for source, target, identity in moves:
            backup = None
            if target.exists():
                backup = backups / "__".join(target.relative_to(root).parts)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            completed.append((source, target, backup))
            if content_identity(target.read_text(encoding="utf-8")) != identity:
                raise IdentityMismatch(f"published bytes differ from the approved identity: {target}")
    except Exception:
        for source, target, backup in reversed(completed):
            os.replace(target, source)
            if backup is not None:
                os.replace(backup, target)
        raise
    shutil.rmtree(directory)
    return [str(_destination(destination)) for destination in manifest["drafts"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Temporary wrap drafts for human review")
    commands = parser.add_subparsers(dest="command", required=True)

    save = commands.add_parser("save", help="save the draft from stdin for one destination")
    save.add_argument("--repo", required=True)
    save.add_argument("--session-id", required=True)
    save.add_argument("--destination", required=True)
    save.add_argument("--replace-identity")

    publish = commands.add_parser("publish", help="move the approved drafts onto their destinations")
    publish.add_argument("--repo", required=True)
    publish.add_argument("--session-id", required=True)
    publish.add_argument(
        "--approve", action="append", default=[], metavar="DESTINATION=IDENTITY", required=True
    )
    args = parser.parse_args(argv)

    root = Path(args.repo)
    if args.command == "save":
        receipt = save_draft(
            root,
            session_id=args.session_id,
            destination=args.destination,
            text=sys.stdin.read(),
            replace_identity=args.replace_identity,
        )
        print(
            json.dumps(
                {
                    "path": receipt.path.relative_to(root.resolve()).as_posix(),
                    "destination": receipt.destination,
                    "content_identity": receipt.content_identity,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "publish":
        approved: dict[str, str] = {}
        for item in args.approve:
            destination, separator, identity = item.rpartition("=")
            if not separator or not destination:
                raise DraftError(f"--approve expects DESTINATION=IDENTITY, got {item!r}")
            approved[destination] = identity
        published = publish_drafts(root, session_id=args.session_id, approved=approved)
        print(json.dumps({"published": published}, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
