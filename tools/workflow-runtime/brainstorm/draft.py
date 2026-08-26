#!/usr/bin/env python3
"""Atomically write a brainstorm result to its canonical document."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile

class DocumentError(Exception):
    pass

class UnsafeDocumentPath(DocumentError):
    pass

def _target(project_root: Path, destination: str) -> Path:
    candidate = PurePosixPath(destination)
    allowed = (
        candidate == PurePosixPath("ROADMAP.md")
        or (
            len(candidate.parts) >= 3
            and candidate.parts[:2] == ("docs", "spec")
            and candidate.suffix == ".md"
        )
        or (
            len(candidate.parts) == 3
            and candidate.parts[:2] == ("docs", "agreements")
            and candidate.suffix == ".md"
        )
    )
    if candidate.is_absolute() or ".." in candidate.parts or not allowed:
        raise UnsafeDocumentPath(
            "destination must be docs/spec/**/*.md, docs/agreements/*.md, or repository-root ROADMAP.md"
        )
    root = project_root.resolve()
    cursor = root
    for part in candidate.parts:
        cursor /= part
        if cursor.is_symlink():
            raise UnsafeDocumentPath(f"symlink is not allowed: {cursor}")
    return root.joinpath(*candidate.parts)

def write_document(project_root: Path, *, destination: str, text: str) -> Path:
    target = _target(project_root, destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if target.is_symlink():
            raise UnsafeDocumentPath(f"target became a symlink: {target}")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a brainstorm result to its canonical document")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args(argv)
    path = write_document(Path(args.repo), destination=args.destination, text=sys.stdin.read())
    print(json.dumps({"path": path.relative_to(Path(args.repo).resolve()).as_posix()}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
