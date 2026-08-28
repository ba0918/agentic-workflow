#!/usr/bin/env python3
"""Read the machine-shaped parts of an approved plan."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import difflib
import json
import os
import re
import subprocess
from typing import NamedTuple

PLAN_STORE = PurePosixPath("docs/plans")
TREE_ENTRY = re.compile(r"[^\s/#][^\s]*")
COVERAGE_ROW = re.compile(
    r"^- `([^`]+)` / `([^`]+)` -> `([1-9][0-9]*):(test|check|artifact|external)`$"
)
STEP_HEADING = re.compile(r"^## Step ([1-9][0-9]*): (\S.*)$", re.MULTILINE)
CHECK_ROW = re.compile(r"^- `([^`]+)`$")
GATE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
GATE_TIMINGS = {"before_edit", "before_commit", "before_implementation_green"}
GATE_RESULTS = {"approved", "rejected"}

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

class VerificationCoverage(NamedTuple):
    path: str
    section: str
    step_id: str
    completion: str

class StepContract(NamedTuple):
    id: str
    completion: str
    checks: tuple[str, ...]
    human_gates: tuple[dict[str, object], ...] = ()

class PlanHeader(NamedTuple):
    specifications: tuple[TargetSpecification, ...]
    coverage: tuple[VerificationCoverage, ...]
    steps: tuple[StepContract, ...]

class ApprovedPlan(NamedTuple):
    path: str
    text: str
    approval_commit: str
    specifications: tuple[TargetSpecification, ...]
    coverage: tuple[VerificationCoverage, ...]
    steps: tuple[StepContract, ...]
    scope: tuple[str, ...]
    specification_changes: tuple["SpecificationChange", ...]

class SpecificationChange(NamedTuple):
    path: str
    approved_text: str
    current_text: str
    diff: str
    current_commit: str

def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)

def _run_git_bytes(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)

def _coverage_block(text: str) -> str:
    if re.search(r"^\*\*Target specifications:\*\*", text, re.MULTILINE):
        raise InvalidPlanFormat("legacy **Target specifications:** is not supported")
    if len(re.findall(r"^\*\*Verification coverage:\*\*[ \t]*$", text, re.MULTILINE)) != 1:
        raise InvalidPlanFormat("plan needs exactly one **Verification coverage:** block")
    match = re.search(r"^\*\*Verification coverage:\*\*[ \t]*\n+(.*?)(?=\n\s*\n|\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        return ""
    remainder = text[:match.start()] + text[match.end():]
    if any(COVERAGE_ROW.fullmatch(line) for line in remainder.splitlines()):
        raise InvalidPlanFormat("verification coverage rows must form one contiguous block")
    return match.group(1)

def _read_coverage(text: str) -> tuple[VerificationCoverage, ...]:
    block = _coverage_block(text)
    if not block:
        raise InvalidPlanFormat("**Verification coverage:** must list at least one specification section")
    coverage: list[VerificationCoverage] = []
    for line in block.splitlines():
        match = COVERAGE_ROW.fullmatch(line)
        if match is None:
            raise InvalidPlanFormat(f"invalid verification coverage row: {line!r}")
        path, section, step_id, completion = match.groups()
        candidate = PurePosixPath(path)
        if (
            candidate.is_absolute() or ".." in candidate.parts
            or candidate.parts[:2] != ("docs", "spec") or candidate.suffix != ".md"
            or not section.strip()
        ):
            raise InvalidPlanFormat(f"unsafe verification coverage address: {path} / {section}")
        coverage.append(VerificationCoverage(path, section, step_id, completion))
    return tuple(coverage)

def _checks(body: str, *, step_id: str, completion: str) -> tuple[str, ...]:
    label = re.search(r"^\*\*Checks:\*\*[ \t]*$", body, re.MULTILINE)
    if completion != "check":
        if label is not None:
            raise InvalidPlanFormat(f"non-check Step {step_id} cannot declare **Checks:**")
        return ()
    if label is None:
        raise InvalidPlanFormat(f"check Step {step_id} needs **Checks:**")
    tail = body[label.end():].lstrip("\n")
    block = tail.split("\n\n", 1)[0]
    checks: list[str] = []
    for line in block.splitlines():
        match = CHECK_ROW.fullmatch(line)
        if match is None:
            raise InvalidPlanFormat(f"invalid check command in Step {step_id}: {line!r}")
        checks.append(match.group(1))
    if not checks:
        raise InvalidPlanFormat(f"check Step {step_id} needs at least one command")
    return tuple(checks)

def _safe_gate_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts

def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return list(value)

def _gate_target(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return None
    if value.get("kind") == "files" and set(value) == {"kind", "paths"}:
        paths = _string_list(value.get("paths"))
        if (
            paths and len(paths) == len(set(paths))
            and all(_safe_gate_path(path) for path in paths)
        ):
            return {"kind": "files", "paths": list(paths)}
    sequence = value.get("sequence")
    if (
        value.get("kind") == "event" and set(value) == {"kind", "sequence"}
        and isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0
    ):
        return {"kind": "event", "sequence": sequence}
    return None

def _gate(value: object, *, step_id: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "gate_id", "sections", "criterion", "target", "timing", "allowed_results",
    }:
        raise InvalidPlanFormat(f"invalid Human gate in Step {step_id}")
    gate_id = value.get("gate_id")
    sections = _string_list(value.get("sections"))
    criterion = value.get("criterion")
    target = _gate_target(value.get("target"))
    timing = value.get("timing")
    results = _string_list(value.get("allowed_results"))
    valid = (
        isinstance(gate_id, str) and GATE_ID.fullmatch(gate_id) is not None
        and sections is not None and bool(sections)
        and all(section.strip() for section in sections)
        and len(sections) == len(set(sections))
        and isinstance(criterion, str) and bool(criterion.strip())
        and target is not None and timing in GATE_TIMINGS
        and results is not None and bool(results)
        and len(results) == len(set(results))
        and all(result in GATE_RESULTS for result in results)
    )
    if not valid or sections is None or results is None:
        raise InvalidPlanFormat(f"invalid Human gate in Step {step_id}")
    return {
        "gate_id": gate_id,
        "sections": list(sections),
        "criterion": criterion,
        "target": target,
        "timing": timing,
        "allowed_results": list(results),
    }

def _human_gates(body: str, *, step_id: str) -> tuple[dict[str, object], ...]:
    labels = list(re.finditer(r"^\*\*Human gates:\*\*[ \t]*$", body, re.MULTILINE))
    if not labels:
        return ()
    if len(labels) != 1:
        raise InvalidPlanFormat(f"Step {step_id} has multiple **Human gates:** blocks")
    tail = body[labels[0].end():].lstrip("\n")
    match = re.match(r"```json[ \t]*\n(.*?)\n```", tail, re.DOTALL)
    if match is None:
        raise InvalidPlanFormat(f"Step {step_id} has an invalid **Human gates:** block")
    try:
        document: object = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise InvalidPlanFormat(f"Step {step_id} has invalid Human gate JSON") from error
    if not isinstance(document, dict) or set(document) != {"version", "gates"}:
        raise InvalidPlanFormat(f"Step {step_id} has an invalid Human gate document")
    values = document.get("gates")
    if document.get("version") != 1 or not isinstance(values, list) or not values:
        raise InvalidPlanFormat(f"Step {step_id} has an invalid Human gate document")
    return tuple(_gate(value, step_id=step_id) for value in values)

def _read_steps(text: str, coverage: tuple[VerificationCoverage, ...]) -> tuple[StepContract, ...]:
    matches = list(STEP_HEADING.finditer(text))
    numbers = [int(match.group(1)) for match in matches]
    if numbers != list(range(1, len(matches) + 1)) or not matches:
        raise InvalidPlanFormat("Step headings must be unique and contiguous from 1")
    completions: dict[str, set[str]] = {}
    for item in coverage:
        completions.setdefault(item.step_id, set()).add(item.completion)
    expected = {str(number) for number in numbers}
    if set(completions) != expected:
        raise InvalidPlanFormat("verification coverage and Step headings must cover each other")
    if any(len(values) != 1 for values in completions.values()):
        raise InvalidPlanFormat("each Step needs exactly one completion kind")
    steps: list[StepContract] = []
    for match in matches:
        step_id = match.group(1)
        following_section = re.search(r"^## ", text[match.end():], re.MULTILINE)
        body_end = (
            match.end() + following_section.start()
            if following_section is not None else len(text)
        )
        body = text[match.end():body_end]
        completion = next(iter(completions[step_id]))
        steps.append(StepContract(
            step_id,
            completion,
            _checks(body, step_id=step_id, completion=completion),
            _human_gates(body, step_id=step_id),
        ))
    gate_ids = [
        gate["gate_id"] for step in steps for gate in step.human_gates
    ]
    if len(gate_ids) != len(set(gate_ids)):
        raise InvalidPlanFormat("Human gate ids must be unique across the plan")
    return tuple(steps)

def _specifications(coverage: tuple[VerificationCoverage, ...]) -> tuple[TargetSpecification, ...]:
    grouped: dict[str, list[str]] = {}
    for item in coverage:
        sections = grouped.setdefault(item.path, [])
        if item.section not in sections:
            sections.append(item.section)
    return tuple(TargetSpecification(path, tuple(sections)) for path, sections in grouped.items())

def read_plan_header(text: str) -> PlanHeader:
    coverage = _read_coverage(text)
    return PlanHeader(_specifications(coverage), coverage, _read_steps(text, coverage))

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

def _heading_count(text: str, heading: str) -> int:
    return len(re.findall(rf"^#+\s+{re.escape(heading)}\s*$", text, re.MULTILINE))

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
            if _heading_count(committed.stdout, section) != 1:
                raise TargetSpecificationMismatch(f"target section is not unique: {specification.path}#{section}")

def _approved_specifications(
    project_root: Path, approval_commit: str, specifications: tuple[TargetSpecification, ...]
) -> tuple[SpecificationChange, ...]:
    head = _run_git(project_root, "rev-parse", "HEAD")
    current_commit = head.stdout.strip() if head.returncode == 0 else ""
    changes: list[SpecificationChange] = []
    for specification in specifications:
        approved = _run_git(project_root, "show", f"{approval_commit}:{specification.path}")
        if approved.returncode != 0:
            raise TargetSpecificationMismatch(f"target specification is not committed: {specification.path}")
        for section in specification.sections:
            if _heading_count(approved.stdout, section) != 1:
                raise TargetSpecificationMismatch(f"target section is not unique: {specification.path}#{section}")
        current = _run_git(project_root, "show", f"HEAD:{specification.path}")
        current_text = current.stdout if current.returncode == 0 else ""
        if current_text != approved.stdout:
            difference = "".join(difflib.unified_diff(
                approved.stdout.splitlines(keepends=True),
                current_text.splitlines(keepends=True),
                fromfile=f"{approval_commit}:{specification.path}",
                tofile=f"{current_commit}:{specification.path}",
            ))
            changes.append(SpecificationChange(
                specification.path, approved.stdout, current_text, difference, current_commit
            ))
    return tuple(changes)

def read_plan(project_root: Path, relative_path: str) -> ApprovedPlan:
    target = _safe_plan_path(project_root, relative_path)
    if not target.is_file():
        raise PlanArtifactError(f"plan does not exist: {relative_path}")
    approval = _run_git(project_root, "log", "-1", "--format=%H", "--", relative_path)
    commit = approval.stdout.strip()
    if approval.returncode != 0 or not commit:
        raise PlanArtifactError("plan has not been approved in Git")
    committed = _run_git_bytes(project_root, "show", f"{commit}:{relative_path}")
    if committed.returncode != 0:
        raise PlanArtifactError("approved plan cannot be read from Git")
    if target.read_bytes() != committed.stdout:
        raise PlanArtifactError("working plan bytes differ from the approval commit")
    try:
        text = committed.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PlanArtifactError("approved plan is not UTF-8") from error
    header = read_plan_header(text)
    scope = read_plan_scope(text)
    changes = _approved_specifications(project_root, commit, header.specifications)
    return ApprovedPlan(
        relative_path, text, commit, header.specifications, header.coverage, header.steps, scope, changes,
    )
