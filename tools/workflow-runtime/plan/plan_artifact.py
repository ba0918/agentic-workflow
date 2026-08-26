#!/usr/bin/env python3
"""Read the two machine-shaped parts of an approved plan."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import os
import re
import subprocess
from typing import NamedTuple

PLAN_STORE = PurePosixPath("docs/plans")
SECTION_NAME = re.compile(r"`([^`]+)`")
TREE_ENTRY = re.compile(r"[^\s/#][^\s]*")

class PlanArtifactError(Exception):
    pass

class UnsafePlanPath(PlanArtifactError):
    pass

class InvalidPlanFormat(PlanArtifactError):
    pass

class TargetSpecificationMismatch(PlanArtifactError):
    pass

class TargetSpecification(NamedTuple):
    path: str
    sections: tuple[str, ...]

class PlanHeader(NamedTuple):
    specifications: tuple[TargetSpecification, ...]

class ApprovedPlan(NamedTuple):
    path: str
    text: str
    approval_commit: str
    specifications: tuple[TargetSpecification, ...]
    scope: tuple[str, ...]

def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)

def _target_specification_block(text: str) -> str:
    match = re.search(r"^\*\*Target specifications:\*\*[ \t]*\n+(.*?)(?=\n\s*\n|\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""

def read_plan_header(text: str) -> PlanHeader:
    items = re.split(r"^- ", _target_specification_block(text), flags=re.MULTILINE)[1:]
    if not items:
        raise InvalidPlanFormat("**Target specifications:** must list at least one specification")
    specifications: list[TargetSpecification] = []
    for item in items:
        head, _, details = item.partition("\n")
        path_match = re.fullmatch(r"`([^`]+)`\s*", head)
        if path_match is None:
            raise InvalidPlanFormat("each target specification needs a backquoted path")
        path = path_match.group(1)
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
            raise InvalidPlanFormat(f"unsafe target specification path: {path}")
        sections_match = re.search(r"^\s*- sections:(.*)$", details, re.MULTILINE)
        sections = tuple(SECTION_NAME.findall(sections_match.group(1))) if sections_match else ()
        if not sections:
            raise InvalidPlanFormat(f"target specification needs sections: {path}")
        specifications.append(TargetSpecification(path, sections))
    return PlanHeader(tuple(specifications))

def _section_body(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise InvalidPlanFormat(f"## {heading} is missing")
    return match.group(1)

def read_plan_scope(text: str) -> tuple[str, ...]:
    block = re.search(r"^```text[ \t]*\n(.*?)^```", _section_body(text, "Scope"), re.MULTILINE | re.DOTALL)
    if block is None:
        raise InvalidPlanFormat("## Scope needs a text code block")
    paths: list[str] = []
    stack: list[tuple[int, str]] = []
    for line in (line for line in block.group(1).splitlines() if line.strip()):
        indent = len(line) - len(line.lstrip(" "))
        entry = line.strip()
        if TREE_ENTRY.fullmatch(entry) is None or "//" in entry or ".." in entry.split("/"):
            raise InvalidPlanFormat(f"invalid Scope entry: {line!r}")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if indent and (not stack or not stack[-1][1].endswith("/")):
            raise InvalidPlanFormat(f"Scope entry has no directory parent: {line!r}")
        full = "".join(parent for _, parent in stack) + entry
        stack.append((indent, entry))
        if not entry.endswith("/"):
            paths.append(full)
    if not paths:
        raise InvalidPlanFormat("## Scope is empty")
    return tuple(paths)

def _safe_plan_path(root: Path, relative_path: str) -> Path:
    candidate = PurePosixPath(relative_path)
    if candidate.is_absolute() or candidate.parent != PLAN_STORE or candidate.suffix != ".md" or ".." in candidate.parts:
        raise UnsafePlanPath("plan must be a Markdown file directly under docs/plans")
    store = root.resolve().joinpath(*PLAN_STORE.parts)
    target = root.resolve().joinpath(*candidate.parts)
    if store.is_symlink() or target.is_symlink():
        raise UnsafePlanPath("symlinks are not allowed in the plan path")
    try:
        within = os.path.commonpath((str(target.resolve(strict=False)), str(store.resolve(strict=False)))) == str(store.resolve(strict=False))
    except ValueError:
        within = False
    if not within:
        raise UnsafePlanPath("plan path escapes docs/plans")
    return target

def _heading_exists(text: str, heading: str) -> bool:
    return re.search(rf"^#+\s+{re.escape(heading)}\s*$", text, re.MULTILINE) is not None

def validate_plan(project_root: Path, text: str, *, approval_commit: str) -> None:
    header = read_plan_header(text)
    read_plan_scope(text)
    for specification in header.specifications:
        committed = _run_git(project_root, "show", f"{approval_commit}:{specification.path}")
        if committed.returncode != 0:
            raise TargetSpecificationMismatch(f"target specification is not committed: {specification.path}")
        working = project_root.joinpath(*PurePosixPath(specification.path).parts)
        if working.is_symlink() or not working.is_file() or working.read_text(encoding="utf-8") != committed.stdout:
            raise TargetSpecificationMismatch(f"target specification differs from approval commit: {specification.path}")
        for section in specification.sections:
            if not _heading_exists(committed.stdout, section):
                raise TargetSpecificationMismatch(f"target section is missing: {specification.path}#{section}")

def read_plan(project_root: Path, relative_path: str) -> ApprovedPlan:
    target = _safe_plan_path(project_root, relative_path)
    if not target.is_file():
        raise PlanArtifactError(f"plan does not exist: {relative_path}")
    approval = _run_git(project_root, "log", "-1", "--format=%H", "--", relative_path)
    commit = approval.stdout.strip()
    if approval.returncode != 0 or not commit:
        raise PlanArtifactError("plan has not been approved in Git")
    committed = _run_git(project_root, "show", f"{commit}:{relative_path}")
    if committed.returncode != 0:
        raise PlanArtifactError("approved plan cannot be read from Git")
    text = target.read_text(encoding="utf-8")
    header = read_plan_header(text)
    scope = read_plan_scope(text)
    validate_plan(project_root, text, approval_commit=commit)
    return ApprovedPlan(relative_path, text, commit, header.specifications, scope)
