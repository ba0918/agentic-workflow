#!/usr/bin/env python3
"""Filesystem, Git, and process boundaries for a normal Cycle execution."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import subprocess
from typing import Any, Callable, NamedTuple


SCRIPT_DIR = Path(__file__).resolve().parent


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


execution_model = _load_module("ba0918_cycle_execution_model", SCRIPT_DIR / "execution_model.py")
plan_artifact = _load_module(
    "ba0918_plan_artifact_consumer",
    SCRIPT_DIR.parents[1] / "ba0918-plan/scripts/plan_artifact.py",
)


PLAN_ID_HEADER = re.compile(r"^\*\*Plan ID:\*\* `([0-9]{14})`\s*$", re.MULTILINE)
PLAN_REVISION_HEADER = re.compile(r"^\*\*Plan revision:\*\* `([0-9]+)`\s*$", re.MULTILINE)
SPEC_ENTRY = re.compile(
    r"^- `([^`]+)`\s*\n\s+- 内容identity: `(sha256:[0-9a-f]{64})`\s*$",
    re.MULTILINE,
)
CREDENTIAL_ASSIGNMENT = re.compile(
    rb"(?i)(api[_-]?key|secret|token|password|credential)\s*[=:]\s*[^<\s][^\s]*"
)


class RuntimeFailure(NamedTuple):
    code: str
    message: str
    detail: str | None = None


class RuntimeResult(NamedTuple):
    value: Any | None
    error: RuntimeFailure | None

    @property
    def ok(self) -> bool:
        return self.error is None


class ResolvedPlan(NamedTuple):
    plan_id: str
    path: str
    revision: int
    content_identity: str
    text: str
    specs: tuple[tuple[str, str], ...]
    write_scope: tuple[str, ...]
    human_gates: tuple[dict[str, Any], ...]


class RepositoryInfo(NamedTuple):
    main_checkout: Path
    common_directory: Path
    checkout: Path
    base_head: str
    repository_identity: str


class Attempt(NamedTuple):
    attempt_id: str
    plan_id: str
    branch: str
    worktree: Path
    binding_path: Path
    evidence_path: Path
    runtime_path: Path
    tmp_path: Path
    main_checkout: Path


def _ok(value: Any = None) -> RuntimeResult:
    return RuntimeResult(value, None)


def _failure(code: str, message: str, detail: str | None = None) -> RuntimeResult:
    return RuntimeResult(None, RuntimeFailure(code, message, detail))


def _git(checkout: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )


def discover_repository(checkout: Path) -> RuntimeResult:
    candidate = checkout.resolve()
    bare = _git(candidate, "rev-parse", "--is-bare-repository")
    if bare.returncode != 0:
        return _failure("repository_unavailable", "path is not a Git repository", bare.stderr.strip())
    if bare.stdout.strip() == "true":
        return _failure("bare_repository", "bare repositories cannot host Cycle worktrees")

    superproject = _git(candidate, "rev-parse", "--show-superproject-working-tree")
    if superproject.returncode == 0 and superproject.stdout.strip():
        return _failure("submodule_repository", "submodules are not accepted as Cycle repositories")
    top = _git(candidate, "rev-parse", "--show-toplevel")
    common = _git(candidate, "rev-parse", "--path-format=absolute", "--git-common-dir")
    head = _git(candidate, "rev-parse", "HEAD")
    if any(result.returncode != 0 for result in (top, common, head)):
        return _failure("repository_unavailable", "Git metadata is incomplete")

    checkout_root = Path(top.stdout.strip()).resolve()
    common_directory = Path(common.stdout.strip()).resolve()
    if common_directory.name != ".git" or not common_directory.is_dir():
        return _failure("repository_identity_invalid", "Git common directory is not a main checkout .git")
    main_checkout = common_directory.parent.resolve()
    repository_identity = execution_model.content_identity(
        {"git_common_directory": str(common_directory)}
    )
    return _ok(
        RepositoryInfo(
            main_checkout=main_checkout,
            common_directory=common_directory,
            checkout=checkout_root,
            base_head=head.stdout.strip(),
            repository_identity=repository_identity,
        )
    )


def _parse_plan(text: str) -> RuntimeResult:
    plan_id = PLAN_ID_HEADER.search(text)
    revision = PLAN_REVISION_HEADER.search(text)
    if plan_id is None or revision is None:
        return _failure("plan_metadata_missing", "plan ID or revision header is missing")
    target_marker = "**対象仕様:**"
    if target_marker not in text:
        return _failure("plan_specs_missing", "plan does not identify its approved specs")
    target_section = text.split(target_marker, 1)[1]
    if "**実装境界資料:**" in target_section:
        target_section = target_section.split("**実装境界資料:**", 1)[0]
    elif "## 目的" in target_section:
        target_section = target_section.split("## 目的", 1)[0]
    specs = tuple(SPEC_ENTRY.findall(target_section))
    if not specs:
        return _failure("plan_specs_missing", "plan does not contain spec identities")
    write_scope = _parse_write_scope(text)
    if not write_scope:
        return _failure("plan_write_scope_missing", "plan does not contain a mechanical write scope")
    return _ok((plan_id.group(1), int(revision.group(1)), specs, write_scope))


def _parse_write_scope(text: str) -> tuple[str, ...]:
    marker = "## 変更するもの"
    if marker not in text:
        return ()
    section = text.split(marker, 1)[1]
    match = re.search(r"```text\n(.*?)\n```", section, re.DOTALL)
    if match is None:
        return ()

    directories: list[tuple[int, PurePosixPath]] = []
    leaves: list[str] = []
    pending_directories: set[str] = set()
    directories_with_leaves: set[str] = set()
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip() or "（" in raw_line or "）" in raw_line:
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        name = raw_line.strip()
        while directories and indent <= directories[-1][0]:
            directories.pop()
        parent = directories[-1][1] if directories else PurePosixPath()
        path = parent / name.rstrip("/")
        if name.endswith("/"):
            directories.append((indent, path))
            pending_directories.add(path.as_posix())
            continue
        if ".." in path.parts or path.is_absolute():
            return ()
        leaves.append(path.as_posix())
        for _, directory in directories:
            directories_with_leaves.add(directory.as_posix())
    leaves.extend(sorted(pending_directories - directories_with_leaves))
    return tuple(dict.fromkeys(leaves))


def _raw_identity(text: str) -> str:
    return plan_artifact.content_identity(text)


def _human_gate_value(gate: Any) -> dict[str, Any]:
    target = {"kind": gate.target.kind}
    if gate.target.kind == "files":
        target["paths"] = list(gate.target.paths)
    else:
        target["content_identity"] = gate.target.content_identity
    return {
        "gate_id": gate.gate_id,
        "step_id": gate.step_id,
        "clauses": list(gate.clauses),
        "criterion": gate.criterion,
        "target": target,
        "timing": gate.timing,
        "allowed_results": list(gate.allowed_results),
    }


def resolve_plan(
    project_root: Path,
    *,
    explicit_path: str | None = None,
    receipt: dict[str, str] | None = None,
) -> RuntimeResult:
    if receipt is not None and explicit_path is not None and receipt.get("path") != explicit_path:
        return _failure("plan_candidate_conflict", "explicit path and publication receipt disagree")
    selected_path = explicit_path
    if selected_path is None and receipt is not None:
        selected_path = receipt.get("path")
    try:
        registered = plan_artifact.read_registered_plan(project_root, selected_path)
    except plan_artifact.PlanRegistrationMissing as error:
        return _failure("plan_registration_missing", str(error))
    except plan_artifact.RegisteredPlanMismatch as error:
        return _failure("plan_identity_drift", str(error))
    except plan_artifact.UnsafePlanPath as error:
        return _failure("unsafe_path", str(error))
    except plan_artifact.PlanArtifactError as error:
        return _failure("plan_locator_invalid", str(error))

    if receipt is not None:
        if receipt.get("content_identity") != registered.content_identity:
            if explicit_path is not None:
                return _failure(
                    "plan_candidate_conflict",
                    "explicit path and publication receipt disagree",
                )
            return _failure("plan_identity_drift", "publication receipt differs from the locator")
    parsed = _parse_plan(registered.text)
    if not parsed.ok:
        return parsed
    try:
        human_gates = tuple(
            _human_gate_value(gate)
            for gate in plan_artifact.read_plan_human_gates(registered.text)
        )
    except plan_artifact.InvalidHumanGateDeclaration as error:
        return _failure("human_gate_declaration_invalid", str(error))
    header_id, header_revision, specs, write_scope = parsed.value
    if header_id != registered.plan_id:
        return _failure("plan_id_drift", "plan header and locator disagree")
    if header_revision != registered.revision:
        return _failure("plan_revision_drift", "plan revision header and locator disagree")

    repository = discover_repository(project_root)
    if not repository.ok:
        return repository
    for spec_path, expected_identity in specs:
        path = repository.value.main_checkout.joinpath(*PurePosixPath(spec_path).parts)
        if path.is_symlink() or not path.is_file():
            return _failure("spec_unavailable", f"approved spec is unavailable: {spec_path}")
        current_identity = _raw_identity(path.read_text(encoding="utf-8"))
        if current_identity != expected_identity:
            return _failure("spec_identity_drift", f"approved spec bytes changed: {spec_path}")
        committed = _git(repository.value.main_checkout, "show", f"{repository.value.base_head}:{spec_path}")
        if committed.returncode != 0 or _raw_identity(committed.stdout) != expected_identity:
            return _failure("spec_identity_drift", f"approved spec is not present at base HEAD: {spec_path}")

    return _ok(
        ResolvedPlan(
            plan_id=registered.plan_id,
            path=registered.path,
            revision=registered.revision,
            content_identity=registered.content_identity,
            text=registered.text,
            specs=specs,
            write_scope=write_scope,
            human_gates=human_gates,
        )
    )


def _classify_write_error(error: OSError) -> str:
    if isinstance(error, PermissionError) or error.errno in {errno.EACCES, errno.EPERM}:
        return "permission_required"
    if error.errno in {errno.EROFS, errno.ENOSPC, errno.EIO, errno.EDQUOT}:
        return "persistence_unavailable"
    if error.errno == errno.EEXIST:
        return "write_collision"
    return "persistence_unavailable"


def write_once(
    path: Path,
    data: bytes,
    *,
    opener: Callable[..., int] = os.open,
) -> RuntimeResult:
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}"
        descriptor = opener(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(temporary, path)
        return _ok(path)
    except OSError as error:
        return _failure(_classify_write_error(error), f"cannot persist {path.name}", str(error))
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _safe_agent_roots(main_checkout: Path) -> RuntimeResult:
    root = main_checkout.resolve()
    paths = [
        root / ".agents",
        root / ".agents/artifacts",
        root / ".agents/runtime",
        root / ".agents/tmp",
    ]
    for path in paths:
        if path.is_symlink():
            return _failure("unsafe_path", f"symlink is not allowed: {path}")
        resolved = path.resolve(strict=False)
        try:
            if os.path.commonpath((str(root), str(resolved))) != str(root):
                return _failure("unsafe_path", f"agent path escapes repository: {path}")
        except ValueError:
            return _failure("unsafe_path", f"agent path escapes repository: {path}")
    return _ok(paths)


def _preflight(main_checkout: Path, common_directory: Path) -> RuntimeResult:
    probes = [
        main_checkout / ".agents/artifacts/executions/.preflight",
        main_checkout / ".agents/runtime/cycles/.preflight",
        main_checkout / ".agents/tmp/cycles/.preflight",
        common_directory / ".cycle-preflight",
    ]
    for probe in probes:
        result = write_once(probe, b"preflight\n")
        if not result.ok:
            return result
        probe.unlink()
    return _ok()


def bootstrap_attempt(
    project_root: Path,
    resolved_plan: ResolvedPlan | None,
    *,
    worktree_path: Path,
    attempt_id_factory: Callable[[], str],
    executor: dict[str, str],
) -> RuntimeResult:
    safe_roots = _safe_agent_roots(project_root)
    if not safe_roots.ok:
        return safe_roots
    repository = discover_repository(project_root)
    if not repository.ok:
        return repository
    main_checkout = repository.value.main_checkout
    claim_path = main_checkout / ".agents/runtime/cycles/current.claim"
    if claim_path.exists() or claim_path.is_symlink():
        return _failure("cycle_claimed", "another normal Cycle claim already exists")
    if resolved_plan is None:
        return _failure("plan_registration_missing", "a validated plan is required")
    if worktree_path.exists() or worktree_path.is_symlink():
        return _failure("worktree_collision", "requested worktree path already exists")

    preflight = _preflight(main_checkout, repository.value.common_directory)
    if not preflight.ok:
        return preflight
    attempt_id = attempt_id_factory()
    if not execution_model.ATTEMPT_ID.fullmatch(attempt_id):
        return _failure("attempt_id_invalid", "generated attempt id is not path-safe")
    branch = f"cycle/{attempt_id}"
    evidence_path = (
        main_checkout
        / ".agents/artifacts/executions"
        / resolved_plan.plan_id
        / attempt_id
    )
    runtime_path = main_checkout / ".agents/runtime/cycles" / attempt_id
    tmp_path = main_checkout / ".agents/tmp/cycles" / attempt_id
    if any(path.exists() or path.is_symlink() for path in (evidence_path, runtime_path, tmp_path)):
        claim = {
            "version": 1,
            "attempt_id": attempt_id,
            "plan_id": resolved_plan.plan_id,
            "plan_identity": resolved_plan.content_identity,
            "branch": branch,
            "worktree": str(worktree_path.resolve(strict=False)),
            "executor": executor,
        }
        claim_result = write_once(claim_path, execution_model.canonical_json(claim))
        if not claim_result.ok:
            return claim_result
        return _failure("attempt_collision", "generated attempt id is already in use")

    claim = {
        "version": 1,
        "attempt_id": attempt_id,
        "plan_id": resolved_plan.plan_id,
        "plan_identity": resolved_plan.content_identity,
        "branch": branch,
        "worktree": str(worktree_path.resolve(strict=False)),
        "executor": executor,
    }
    claim_result = write_once(claim_path, execution_model.canonical_json(claim))
    if not claim_result.ok:
        if claim_result.error.code == "write_collision":
            return _failure("cycle_claimed", "another Cycle acquired the repository claim")
        return claim_result

    try:
        evidence_path.mkdir(parents=True, exist_ok=False)
        runtime_path.mkdir(parents=True, exist_ok=False)
        tmp_path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return _failure("attempt_collision", "generated attempt id collided during bootstrap")
    except OSError as error:
        return _failure(_classify_write_error(error), "attempt directories could not be created", str(error))

    binding = {
        "version": 1,
        "attempt_id": attempt_id,
        "plan": {
            "id": resolved_plan.plan_id,
            "path": resolved_plan.path,
            "revision": resolved_plan.revision,
            "content_identity": resolved_plan.content_identity,
        },
        "specs": [
            {"path": path, "content_identity": identity}
            for path, identity in resolved_plan.specs
        ],
        "repository_identity": repository.value.repository_identity,
        "base_head": repository.value.base_head,
        "branch": branch,
        "write_scope": list(resolved_plan.write_scope),
        "human_gates": list(resolved_plan.human_gates),
        "executor": executor,
    }
    binding_validation = execution_model.validate_binding(binding)
    if not binding_validation.ok:
        return _failure(binding_validation.error.code, binding_validation.error.message)
    binding_path = evidence_path / "binding.json"
    binding_result = write_once(binding_path, execution_model.canonical_json(binding))
    if not binding_result.ok:
        return binding_result

    created = _git(
        main_checkout,
        "worktree",
        "add",
        "-b",
        branch,
        str(worktree_path),
        repository.value.base_head,
    )
    if created.returncode != 0:
        return _failure("worktree_create_failed", "Git could not create the linked worktree", created.stderr.strip())
    observed = discover_repository(worktree_path)
    if (
        not observed.ok
        or observed.value.common_directory != repository.value.common_directory
        or observed.value.base_head != repository.value.base_head
        or observed.value.checkout != worktree_path.resolve()
    ):
        return _failure("worktree_identity_drift", "created worktree does not match its binding")
    observed_branch = _git(worktree_path, "branch", "--show-current")
    if observed_branch.returncode != 0 or observed_branch.stdout.strip() != branch:
        return _failure("worktree_identity_drift", "created worktree branch does not match its binding")

    event = execution_model.seal_event(
        {
            "version": 1,
            "sequence": 1,
            "event_type": "worktree-bound",
            "attempt_id": attempt_id,
            "plan_identity": resolved_plan.content_identity,
            "spec_identities": dict(resolved_plan.specs),
            "previous_identity": None,
            "outcome": "bound",
            "repository_identity": repository.value.repository_identity,
            "base_head": repository.value.base_head,
            "branch": branch,
            "worktree_identity": execution_model.content_identity(
                {"path": str(worktree_path.resolve()), "common_directory": str(repository.value.common_directory)}
            ),
        }
    )
    if not event.ok:
        return _failure(event.error.code, event.error.message)
    event_result = write_once(
        evidence_path / "000001-worktree-bound.json",
        execution_model.canonical_json(event.value),
    )
    if not event_result.ok:
        return event_result
    return _ok(
        Attempt(
            attempt_id=attempt_id,
            plan_id=resolved_plan.plan_id,
            branch=branch,
            worktree=worktree_path.resolve(),
            binding_path=binding_path,
            evidence_path=evidence_path,
            runtime_path=runtime_path,
            tmp_path=tmp_path,
            main_checkout=main_checkout,
        )
    )


def _read_json(path: Path) -> RuntimeResult:
    if path.is_symlink() or not path.is_file():
        return _failure("artifact_unavailable", f"artifact is unavailable: {path.name}")
    try:
        return _ok(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        return _failure("artifact_invalid", f"artifact is invalid: {path.name}", str(error))


def load_current_attempt(project_root: Path) -> RuntimeResult:
    safe = _safe_agent_roots(project_root)
    if not safe.ok:
        return safe
    repository = discover_repository(project_root)
    if not repository.ok:
        return repository
    main_checkout = repository.value.main_checkout
    claim_result = _read_json(main_checkout / ".agents/runtime/cycles/current.claim")
    if not claim_result.ok:
        return _failure("cycle_claim_missing", "no readable current Cycle claim exists")
    claim = claim_result.value
    required = {"attempt_id", "plan_id", "plan_identity", "branch", "worktree"}
    if not isinstance(claim, dict) or not required.issubset(claim):
        return _failure("cycle_claim_invalid", "current Cycle claim fields are invalid")
    attempt_id = claim["attempt_id"]
    plan_id = claim["plan_id"]
    if not execution_model.ATTEMPT_ID.fullmatch(attempt_id) or not plan_artifact.PLAN_ID.fullmatch(plan_id):
        return _failure("cycle_claim_invalid", "claim identity is invalid")
    evidence_path = main_checkout / ".agents/artifacts/executions" / plan_id / attempt_id
    runtime_path = main_checkout / ".agents/runtime/cycles" / attempt_id
    tmp_path = main_checkout / ".agents/tmp/cycles" / attempt_id
    binding_path = evidence_path / "binding.json"
    binding_result = _read_json(binding_path)
    if not binding_result.ok:
        return binding_result
    validation = execution_model.validate_binding(binding_result.value)
    if not validation.ok:
        return _failure(validation.error.code, validation.error.message)
    binding = binding_result.value
    if (
        binding["attempt_id"] != attempt_id
        or binding["plan"]["id"] != plan_id
        or binding["plan"]["content_identity"] != claim["plan_identity"]
        or binding["branch"] != claim["branch"]
    ):
        return _failure("binding_identity_drift", "claim and immutable binding disagree")
    return _ok(
        Attempt(
            attempt_id=attempt_id,
            plan_id=plan_id,
            branch=claim["branch"],
            worktree=Path(claim["worktree"]).resolve(),
            binding_path=binding_path,
            evidence_path=evidence_path,
            runtime_path=runtime_path,
            tmp_path=tmp_path,
            main_checkout=main_checkout,
        )
    )


def _changed_paths(worktree: Path) -> RuntimeResult:
    status = _git(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return _failure("git_status_failed", "Git status could not be observed", status.stderr.strip())
    paths: list[str] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            before, after = path.split(" -> ", 1)
            paths.extend((before, after))
        else:
            paths.append(path)
    return _ok(tuple(paths))


def validate_context(attempt: Attempt, *, step_id: str) -> RuntimeResult:
    binding_result = _read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    validation = execution_model.validate_binding(binding)
    if not validation.ok:
        return _failure(validation.error.code, validation.error.message)
    if binding["attempt_id"] != attempt.attempt_id or binding["branch"] != attempt.branch:
        return _failure("binding_identity_drift", "attempt and binding disagree")

    try:
        registered = plan_artifact.read_registered_plan(
            attempt.main_checkout,
            binding["plan"]["path"],
        )
    except plan_artifact.PlanArtifactError as error:
        return _failure("plan_identity_drift", "registered plan is no longer valid", str(error))
    if (
        registered.plan_id != binding["plan"]["id"]
        or registered.revision != binding["plan"]["revision"]
        or registered.content_identity != binding["plan"]["content_identity"]
    ):
        return _failure("plan_identity_drift", "registered plan differs from the binding")
    step_number = step_id.removeprefix("step-")
    if not step_number.isdigit() or re.search(
        rf"^### {re.escape(step_number)}\.", registered.text, re.MULTILINE
    ) is None:
        return _failure("step_missing", "current step does not exist in the bound plan")

    repository = discover_repository(attempt.worktree)
    if not repository.ok:
        return _failure("worktree_identity_drift", "bound worktree is not a valid linked worktree")
    if (
        repository.value.main_checkout != attempt.main_checkout.resolve()
        or repository.value.checkout != attempt.worktree.resolve()
        or repository.value.repository_identity != binding["repository_identity"]
    ):
        return _failure("worktree_identity_drift", "worktree Git identity differs from the binding")
    branch = _git(attempt.worktree, "branch", "--show-current")
    ancestor = _git(
        attempt.worktree,
        "merge-base",
        "--is-ancestor",
        binding["base_head"],
        "HEAD",
    )
    if branch.returncode != 0 or branch.stdout.strip() != binding["branch"] or ancestor.returncode != 0:
        return _failure("worktree_identity_drift", "worktree branch or base HEAD differs from the binding")

    for spec in binding["specs"]:
        path = attempt.worktree.joinpath(*PurePosixPath(spec["path"]).parts)
        if path.is_symlink() or not path.is_file():
            return _failure("spec_identity_drift", f"bound spec is unavailable: {spec['path']}")
        if _raw_identity(path.read_text(encoding="utf-8")) != spec["content_identity"]:
            return _failure("spec_identity_drift", f"bound spec changed: {spec['path']}")

    changed = _changed_paths(attempt.worktree)
    if not changed.ok:
        return changed
    for path in changed.value:
        scope = execution_model.validate_write_path(path, binding["write_scope"])
        if not scope.ok:
            return _failure(scope.error.code, scope.error.message, path)
    return _ok(binding)


def _load_events(attempt: Attempt) -> RuntimeResult:
    events: list[dict] = []
    for path in sorted(attempt.evidence_path.glob("0*.json")):
        loaded = _read_json(path)
        if not loaded.ok:
            return loaded
        event = loaded.value
        previous = events[-1] if events else None
        unsigned = {key: value for key, value in event.items() if key != "content_identity"}
        sealed = execution_model.seal_event(unsigned, previous_event=previous)
        if not sealed.ok or sealed.value != event:
            return _failure("stale_event_chain", "durable event chain is invalid", path.name)
        events.append(event)
    return _ok(events)


def append_event(
    attempt: Attempt,
    event_type: str,
    details: dict[str, Any],
    *,
    sequence: int | None = None,
) -> RuntimeResult:
    binding_result = _read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    loaded = _load_events(attempt)
    if not loaded.ok:
        return loaded
    events = loaded.value
    next_sequence = sequence if sequence is not None else len(events) + 1
    previous = next((event for event in events if event["sequence"] == next_sequence - 1), None)
    if next_sequence == 1:
        previous = None
    candidate = {
        "version": 1,
        "sequence": next_sequence,
        "event_type": event_type,
        "attempt_id": attempt.attempt_id,
        "plan_identity": binding["plan"]["content_identity"],
        "spec_identities": {
            item["path"]: item["content_identity"] for item in binding["specs"]
        },
        "previous_identity": previous["content_identity"] if previous is not None else None,
        **details,
    }
    sealed = execution_model.seal_event(candidate, previous_event=previous)
    if not sealed.ok:
        return _failure(sealed.error.code, sealed.error.message)
    existing_paths = list(attempt.evidence_path.glob(f"{next_sequence:06d}-*.json"))
    if existing_paths:
        if len(existing_paths) != 1:
            return _failure("event_identity_collision", "multiple events occupy the same sequence")
        existing = _read_json(existing_paths[0])
        if not existing.ok:
            return existing
        compared = execution_model.compare_event_retry(existing.value, sealed.value)
        if not compared.ok:
            return _failure(compared.error.code, compared.error.message)
        return _ok(existing.value)
    target = attempt.evidence_path / f"{next_sequence:06d}-{event_type}.json"
    persisted = write_once(target, execution_model.canonical_json(sealed.value))
    if not persisted.ok:
        if persisted.error.code == "write_collision":
            return _failure("event_identity_collision", "event sequence was acquired concurrently")
        return persisted
    return _ok(sealed.value)


def derive_attempt_result(attempt: Attempt) -> dict:
    loaded = _load_events(attempt)
    if not loaded.ok:
        return {
            "state": "stopped",
            "reason": loaded.error.code,
            "attempt_id": attempt.attempt_id,
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "evidence_path": str(attempt.evidence_path),
        }
    result = execution_model.derive_result(loaded.value)
    result.update(
        {
            "branch": attempt.branch,
            "worktree": str(attempt.worktree),
            "evidence_path": str(attempt.evidence_path),
        }
    )
    commits = [event["commit_sha"] for event in loaded.value if event["event_type"] == "commit"]
    if commits and "commits" not in result:
        result["commits"] = commits
    return result


def _stop(attempt: Attempt, error: RuntimeFailure, step_id: str) -> RuntimeResult:
    append_event(
        attempt,
        "stopped",
        {"reason": error.code, "step_id": step_id},
    )
    return RuntimeResult(None, error)


def _permission_required(
    attempt: Attempt,
    error: RuntimeFailure,
    step_id: str,
    operation_identity: str,
) -> RuntimeResult:
    append_event(
        attempt,
        "permission_required",
        {
            "step_id": step_id,
            "operation_identity": operation_identity,
            "outcome": "permission_required",
        },
    )
    return RuntimeResult(None, error)


def _bounded_observation(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
    diagnostic = re.compile(
        r"(?i)(modulenotfounderror|importerror|permissionerror|permission denied|"
        r"assertionerror|fixture|collection error|network|connection)"
    )
    observation = next((line for line in reversed(lines) if diagnostic.search(line)), None)
    if observation is None:
        observation = lines[-1] if lines else "no output"
    observation = re.sub(
        r"(?i)\b(token|password|secret|credential)\s*[=:]\s*\S+",
        r"\1=<redacted>",
        observation,
    )
    return observation[:512]


def _classify_process_failure(stdout: str, stderr: str) -> str:
    lowered = (stdout + "\n" + stderr).lower()
    if "modulenotfounderror" in lowered or "importerror" in lowered:
        return "import_failure"
    if "permissionerror" in lowered or "permission denied" in lowered:
        return "permission_failure"
    if "fixture" in lowered or "collection error" in lowered:
        return "fixture_failure"
    if "network" in lowered or "connection" in lowered:
        return "network_failure"
    return "behavior_failure"


def _test_summary(stdout: str, stderr: str) -> dict[str, Any]:
    output = stdout + "\n" + stderr
    totals = re.findall(r"^Ran ([0-9]+) tests? in [^\n]+$", output, re.MULTILINE)
    failures = re.findall(r"^FAILED \(([^\n]+)\)$", output, re.MULTILINE)
    successes = re.findall(r"^OK(?: \(skipped=([0-9]+)\))?$", output, re.MULTILINE)
    if len(totals) == 1 and len(successes) == 1 and not failures:
        total = int(totals[0])
        skipped = int(successes[0] or 0)
        if skipped <= total:
            return {
                "status": "complete",
                "passed": total - skipped,
                "failed": 0,
                "skipped": skipped,
            }
    if len(totals) == 1 and len(failures) == 1:
        values = {"failures": 0, "errors": 0, "skipped": 0}
        for raw_item in failures[0].split(","):
            match = re.fullmatch(r"\s*(failures|errors|skipped)=([0-9]+)\s*", raw_item)
            if match is None:
                break
            values[match.group(1)] = int(match.group(2))
        else:
            total = int(totals[0])
            failed = values["failures"] + values["errors"]
            passed = total - failed - values["skipped"]
            if passed >= 0:
                return {
                    "status": "complete",
                    "passed": passed,
                    "failed": failed,
                    "skipped": values["skipped"],
                }
    return {
        "status": "unavailable",
        "reason": "runner did not expose one supported structured summary",
    }


def _oracle_cwd(attempt: Attempt, relative_path: str) -> RuntimeResult:
    if not execution_model.validate_relative_path(relative_path).ok:
        return _failure("unsafe_path", "oracle cwd is not a safe relative path")
    root = attempt.worktree.resolve()
    parts = () if relative_path == "." else PurePosixPath(relative_path).parts
    candidate = attempt.worktree
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return _failure("unsafe_path", "oracle cwd contains a symlink", relative_path)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        return _failure("cwd_unavailable", "oracle cwd is unavailable", str(error))
    if (resolved != root and root not in resolved.parents) or not resolved.is_dir():
        return _failure("unsafe_path", "oracle cwd escapes the bound worktree", relative_path)
    return _ok(resolved)


def _execute_oracle(attempt: Attempt, oracle: dict) -> RuntimeResult:
    cwd_result = _oracle_cwd(attempt, oracle["cwd"])
    if not cwd_result.ok:
        return cwd_result
    try:
        completed = subprocess.run(
            oracle["command"],
            cwd=cwd_result.value,
            text=True,
            capture_output=True,
            timeout=oracle["timeout_seconds"],
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failure("timeout", "oracle exceeded its frozen timeout")
    except FileNotFoundError:
        return _failure("command_missing", "oracle command is unavailable")
    except PermissionError:
        return _failure("permission_required", "oracle command requires additional permission")
    observation = _bounded_observation(completed.stdout, completed.stderr)
    return _ok(
        {
            "exit_code": completed.returncode,
            "observation": observation,
            "test_summary": _test_summary(completed.stdout, completed.stderr),
            "failure_kind": (
                "passed"
                if completed.returncode == 0
                else _classify_process_failure(completed.stdout, completed.stderr)
            ),
        }
    )


def _test_target_snapshot(worktree: Path, paths: list[str]) -> RuntimeResult:
    targets: list[dict[str, str]] = []
    root = worktree.resolve()
    for relative_path in paths:
        if not execution_model.validate_relative_path(relative_path).ok:
            return _failure("test_target_invalid", "test target path is unsafe", relative_path)
        path = worktree.joinpath(*PurePosixPath(relative_path).parts)
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            return _failure("test_target_unavailable", "test target is unavailable", str(error))
        if path.is_symlink() or (resolved.parent != root and root not in resolved.parents) or not resolved.is_file():
            return _failure("test_target_invalid", "test target escapes the bound worktree", relative_path)
        try:
            identity = "sha256:" + hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError as error:
            return _failure("test_target_unavailable", "test target cannot be read", str(error))
        targets.append({"path": relative_path, "content_identity": identity})
    return _ok(targets)


def _validate_frozen_test_targets(attempt: Attempt, oracle: dict) -> RuntimeResult:
    expected = oracle["test_targets"]
    observed = _test_target_snapshot(attempt.worktree, [item["path"] for item in expected])
    if not observed.ok:
        return observed
    if observed.value != expected:
        return _failure("test_identity_drift", "frozen test target bytes changed")
    return _ok(expected)


def _validate_step_test_targets(attempt: Attempt, step_id: str) -> RuntimeResult:
    oracle_result = _read_json(attempt.evidence_path / "oracles" / f"{step_id}.json")
    if not oracle_result.ok:
        return _failure("oracle_missing", "frozen oracle is unavailable")
    validation = execution_model.validate_oracle(oracle_result.value)
    if not validation.ok:
        return _failure(validation.error.code, validation.error.message)
    return _validate_frozen_test_targets(attempt, oracle_result.value)


def _human_gate_target_identities(
    attempt: Attempt,
    binding: dict,
    *,
    step_id: str,
    timing: str,
) -> RuntimeResult:
    identities: dict[str, str] = {}
    boundary = execution_model.HUMAN_GATE_TIMINGS[timing]
    for gate in binding["human_gates"]:
        if gate["step_id"] != step_id:
            continue
        if execution_model.HUMAN_GATE_TIMINGS[gate["timing"]] > boundary:
            continue
        target = gate["target"]
        if target["kind"] == "event":
            identities[gate["gate_id"]] = target["content_identity"]
            continue
        observed = _test_target_snapshot(attempt.worktree, target["paths"])
        if not observed.ok:
            return observed
        identities[gate["gate_id"]] = execution_model.content_identity(observed.value)
    return _ok(identities)


def check_human_gates(attempt: Attempt, *, step_id: str, timing: str) -> RuntimeResult:
    binding_result = _read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding_validation = execution_model.validate_binding(binding_result.value)
    if not binding_validation.ok:
        return _failure(binding_validation.error.code, binding_validation.error.message)
    if timing not in execution_model.HUMAN_GATE_TIMINGS:
        return _failure("human_gate_timing_invalid", "human gate timing is invalid")
    events = _load_events(attempt)
    if not events.ok:
        return events
    identities = _human_gate_target_identities(
        attempt,
        binding_result.value,
        step_id=step_id,
        timing=timing,
    )
    if not identities.ok:
        return identities
    result = execution_model.validate_human_gate_boundary(
        binding_result.value,
        events.value,
        step_id=step_id,
        timing=timing,
        target_identities=identities.value,
    )
    if not result.ok:
        return _failure(result.error.code, result.error.message, result.error.field)
    return _ok(identities.value)


def record_human_gate(
    attempt: Attempt,
    *,
    step_id: str,
    gate_id: str,
    result: str,
) -> RuntimeResult:
    binding_result = _read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    validation = execution_model.validate_binding(binding)
    if not validation.ok:
        return _failure(validation.error.code, validation.error.message)
    declaration = next(
        (
            gate
            for gate in binding["human_gates"]
            if gate["gate_id"] == gate_id and gate["step_id"] == step_id
        ),
        None,
    )
    if declaration is None:
        return _failure("human_gate_undeclared", "human gate is not declared for this step")
    if result not in declaration["allowed_results"]:
        return _failure("human_gate_event_invalid", "human gate result is invalid")
    identities = _human_gate_target_identities(
        attempt,
        binding,
        step_id=step_id,
        timing=declaration["timing"],
    )
    if not identities.ok:
        return identities
    recorded = append_event(
        attempt,
        "human_gate",
        {
            "gate_id": gate_id,
            "step_id": step_id,
            "target_identity": identities.value[gate_id],
            "result": result,
        },
    )
    if not recorded.ok:
        return recorded
    if result == "rejected":
        return _stop(
            attempt,
            RuntimeFailure("human_gate_rejected", "human gate was rejected", gate_id),
            step_id,
        )
    return recorded


def accept_red(attempt: Attempt, oracle: dict) -> RuntimeResult:
    validation = execution_model.validate_oracle_candidate(oracle)
    if not validation.ok:
        return _stop(
            attempt,
            RuntimeFailure(validation.error.code, validation.error.message),
            oracle.get("step_id", "unknown"),
        )
    step_id = oracle["step_id"]
    before = validate_context(attempt, step_id=step_id)
    if not before.ok:
        return _stop(attempt, before.error, step_id)
    targets_before = _test_target_snapshot(attempt.worktree, oracle["test_targets"])
    if not targets_before.ok:
        return _stop(attempt, targets_before.error, step_id)
    executed = _execute_oracle(attempt, oracle)
    if not executed.ok:
        if executed.error.code == "permission_required":
            return _permission_required(
                attempt,
                executed.error,
                step_id,
                execution_model.content_identity(oracle),
            )
        return _stop(attempt, executed.error, step_id)
    after = validate_context(attempt, step_id=step_id)
    if not after.ok:
        return _stop(attempt, after.error, step_id)
    targets_after = _test_target_snapshot(attempt.worktree, oracle["test_targets"])
    if not targets_after.ok:
        return _stop(attempt, targets_after.error, step_id)
    if targets_after.value != targets_before.value:
        return _stop(
            attempt,
            RuntimeFailure("test_identity_drift", "test target changed during RED execution"),
            step_id,
        )
    observation = executed.value
    if (
        observation["exit_code"] == 0
        or observation["failure_kind"] != oracle["expected_failure_kind"]
        or oracle["failure_signature"] not in observation["observation"]
    ):
        return _stop(
            attempt,
            RuntimeFailure("unintended_red", "RED did not fail for the approved missing behavior"),
            step_id,
        )
    frozen = dict(oracle)
    frozen["test_targets"] = targets_before.value
    frozen["observed_failure_kind"] = observation["failure_kind"]
    frozen_validation = execution_model.validate_oracle(frozen)
    if not frozen_validation.ok:
        return _stop(
            attempt,
            RuntimeFailure(frozen_validation.error.code, frozen_validation.error.message),
            step_id,
        )
    oracle_identity = execution_model.content_identity(frozen)
    oracle_path = attempt.evidence_path / "oracles" / f"{step_id}.json"
    persisted = write_once(oracle_path, execution_model.canonical_json(frozen))
    if not persisted.ok:
        if persisted.error.code == "write_collision":
            existing = _read_json(oracle_path)
            if not existing.ok or execution_model.content_identity(existing.value) != oracle_identity:
                return _stop(
                    attempt,
                    RuntimeFailure("oracle_identity_collision", "frozen oracle differs from existing evidence"),
                    step_id,
                )
        else:
            return _stop(attempt, persisted.error, step_id)
    return append_event(
        attempt,
        "red",
        {
            "step_id": step_id,
            "oracle_identity": oracle_identity,
            "outcome": "expected_failure",
            "exit_code": observation["exit_code"],
            "observation": observation["observation"],
            "test_summary": observation["test_summary"],
        },
    )


def run_frozen_oracle(attempt: Attempt, step_id: str, phase: str) -> RuntimeResult:
    if phase not in {"green", "refactor"}:
        return _failure("phase_invalid", "frozen oracle phase must be green or refactor")
    oracle_result = _read_json(attempt.evidence_path / "oracles" / f"{step_id}.json")
    if not oracle_result.ok:
        return _stop(attempt, RuntimeFailure("oracle_missing", "frozen oracle is unavailable"), step_id)
    oracle = oracle_result.value
    validation = execution_model.validate_oracle(oracle)
    if not validation.ok:
        return _stop(attempt, RuntimeFailure(validation.error.code, validation.error.message), step_id)
    target_validation = _validate_frozen_test_targets(attempt, oracle)
    if not target_validation.ok:
        return _stop(attempt, target_validation.error, step_id)
    events_result = _load_events(attempt)
    if not events_result.ok:
        return RuntimeResult(None, events_result.error)
    red_events = [
        event
        for event in events_result.value
        if event["event_type"] == "red" and event.get("step_id") == step_id
    ]
    if len(red_events) != 1 or red_events[0]["oracle_identity"] != execution_model.content_identity(
        oracle
    ):
        return _stop(
            attempt,
            RuntimeFailure("oracle_identity_drift", "frozen oracle differs from the accepted RED"),
            step_id,
        )
    before = validate_context(attempt, step_id=step_id)
    if not before.ok:
        return _stop(attempt, before.error, step_id)
    executed = _execute_oracle(attempt, oracle)
    if not executed.ok:
        return _stop(attempt, executed.error, step_id)
    after = validate_context(attempt, step_id=step_id)
    if not after.ok:
        return _stop(attempt, after.error, step_id)
    target_validation = _validate_frozen_test_targets(attempt, oracle)
    if not target_validation.ok:
        return _stop(attempt, target_validation.error, step_id)
    if executed.value["exit_code"] != 0:
        return _stop(
            attempt,
            RuntimeFailure(f"{phase}_failed", f"frozen oracle did not pass during {phase}"),
            step_id,
        )
    return append_event(
        attempt,
        phase,
        {
            "step_id": step_id,
            "oracle_identity": execution_model.content_identity(oracle),
            "outcome": "passed",
            "exit_code": executed.value["exit_code"],
            "test_summary": executed.value["test_summary"],
            "observation": executed.value["observation"],
        },
    )


def stage_paths(attempt: Attempt, paths: list[str], *, step_id: str) -> RuntimeResult:
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return context
    scopes = context.value["write_scope"]
    for path in paths:
        validation = execution_model.validate_write_path(path, scopes)
        if not validation.ok:
            return _failure(validation.error.code, validation.error.message, path)
    for path in paths:
        candidate = attempt.worktree.joinpath(*PurePosixPath(path).parts)
        try:
            content = candidate.read_bytes() if candidate.is_file() else b""
        except OSError as error:
            return _failure("stage_failed", "approved path could not be inspected", str(error))
        if CREDENTIAL_ASSIGNMENT.search(content):
            return _failure("secret_detected", "candidate content resembles a credential assignment")
    targets = _validate_step_test_targets(attempt, step_id)
    if not targets.ok:
        return targets
    gates = check_human_gates(attempt, step_id=step_id, timing="before_commit")
    if not gates.ok:
        return gates
    for path in paths:
        staged = _git(attempt.worktree, "add", "--", path)
        if staged.returncode != 0:
            return _failure("stage_failed", "Git could not stage an approved path", staged.stderr.strip())
    observed = _git(attempt.worktree, "diff", "--cached", "--name-only", "--diff-filter=AM")
    if observed.returncode != 0:
        return _failure("stage_failed", "staged paths could not be observed", observed.stderr.strip())
    staged_paths = tuple(line for line in observed.stdout.splitlines() if line)
    if set(staged_paths) != set(paths):
        return _failure("stage_scope_mismatch", "staging contains missing or additional paths")
    for path in staged_paths:
        validation = execution_model.validate_write_path(path, scopes)
        if not validation.ok:
            return _failure(validation.error.code, validation.error.message, path)
    staged_diff = _git(attempt.worktree, "diff", "--cached", "--")
    if CREDENTIAL_ASSIGNMENT.search(staged_diff.stdout.encode("utf-8")):
        return _failure("secret_detected", "staged content resembles a credential assignment")
    return _ok(staged_paths)


def record_commit(attempt: Attempt, step_id: str, previous_head: str) -> RuntimeResult:
    current = _git(attempt.worktree, "rev-parse", "HEAD")
    current_head = current.stdout.strip()
    if (
        current.returncode != 0
        or not execution_model.COMMIT_SHA.fullmatch(previous_head)
        or current_head == previous_head
    ):
        return _failure("commit_missing", "commit did not advance HEAD")
    commit_range = _git(
        attempt.worktree,
        "rev-list",
        "--reverse",
        "--parents",
        f"{previous_head}..{current_head}",
    )
    rows = [line.split() for line in commit_range.stdout.splitlines() if line]
    if (
        commit_range.returncode != 0
        or len(rows) != 1
        or len(rows[0]) != 2
        or rows[0][0] != current_head
        or rows[0][1] != previous_head
    ):
        return _failure(
            "commit_range_invalid",
            "recorded operation must produce exactly one non-merge commit from previous HEAD",
        )
    status = _git(attempt.worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return _failure("git_status_failed", "post-commit status could not be observed")
    if status.stdout.strip():
        return _failure("post_commit_dirty", "worktree changed during or after commit")
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return context
    targets = _validate_step_test_targets(attempt, step_id)
    if not targets.ok:
        return targets
    changed = _git(
        attempt.worktree,
        "diff",
        "--name-only",
        previous_head,
        current_head,
    )
    if changed.returncode != 0:
        return _failure("commit_invalid", "committed paths could not be observed")
    for path in changed.stdout.splitlines():
        validation = execution_model.validate_write_path(path, context.value["write_scope"])
        if not validation.ok:
            return _failure(validation.error.code, validation.error.message, path)
    return append_event(
        attempt,
        "commit",
        {
            "step_id": step_id,
            "commit_sha": current_head,
            "outcome": "committed",
        },
    )


def mark_implementation_green(attempt: Attempt) -> RuntimeResult:
    loaded = _load_events(attempt)
    if not loaded.ok:
        return loaded
    commits = [event["commit_sha"] for event in loaded.value if event["event_type"] == "commit"]
    if not commits:
        return _failure("commit_missing", "implementation green requires at least one commit")
    binding_result = _read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    try:
        registered = plan_artifact.read_registered_plan(
            attempt.main_checkout,
            binding_result.value["plan"]["path"],
        )
    except (KeyError, TypeError, plan_artifact.PlanArtifactError) as error:
        return _failure("plan_identity_drift", "bound plan cannot be verified", str(error))
    implementation = registered.text.split("## 実装手順", 1)
    if len(implementation) != 2:
        return _failure("step_evidence_missing", "bound plan has no implementation steps")
    step_ids = tuple(
        f"step-{number}"
        for number in re.findall(r"^### ([0-9]+)\.", implementation[1], re.MULTILINE)
    )
    if not step_ids:
        return _failure("step_evidence_missing", "bound plan has no implementation steps")
    for step_id in step_ids:
        state = "red"
        for event in loaded.value:
            if event.get("step_id") != step_id:
                continue
            event_type = event["event_type"]
            if event_type == "red":
                if state not in {"red", "complete"}:
                    return _failure("step_evidence_missing", f"incomplete TDD evidence: {step_id}")
                state = "green"
            elif event_type == "green":
                if state != "green":
                    return _failure("step_evidence_missing", f"incomplete TDD evidence: {step_id}")
                state = "refactor"
            elif event_type == "refactor":
                if state != "refactor":
                    return _failure("step_evidence_missing", f"incomplete TDD evidence: {step_id}")
                state = "commit"
            elif event_type == "commit":
                if state == "commit":
                    state = "complete"
                elif state != "complete":
                    return _failure("step_evidence_missing", f"incomplete TDD evidence: {step_id}")
        if state != "complete":
            return _failure("step_evidence_missing", f"incomplete TDD evidence: {step_id}")
        targets = _validate_step_test_targets(attempt, step_id)
        if not targets.ok:
            return targets
    final_step = step_ids[-1]
    context = validate_context(attempt, step_id=final_step)
    if not context.ok:
        return _stop(attempt, context.error, final_step)
    changed = _changed_paths(attempt.worktree)
    if not changed.ok:
        return _stop(attempt, changed.error, final_step)
    if changed.value:
        return _stop(
            attempt,
            RuntimeFailure(
                "post_verification_dirty",
                "final verification left the bound worktree dirty",
            ),
            final_step,
        )
    head = _git(attempt.worktree, "rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != commits[-1]:
        return _stop(
            attempt,
            RuntimeFailure(
                "commit_identity_drift",
                "worktree HEAD differs from the last durable commit event",
            ),
            final_step,
        )
    history = _git(
        attempt.worktree,
        "rev-list",
        "--reverse",
        f"{binding_result.value['base_head']}..{head.stdout.strip()}",
    )
    observed_commits = [line for line in history.stdout.splitlines() if line]
    if history.returncode != 0 or observed_commits != commits:
        return _stop(
            attempt,
            RuntimeFailure(
                "commit_history_mismatch",
                "base-to-HEAD commits differ from durable commit events",
            ),
            final_step,
        )
    history_paths = _git(
        attempt.worktree,
        "diff",
        "--name-only",
        binding_result.value["base_head"],
        head.stdout.strip(),
    )
    if history_paths.returncode != 0:
        return _stop(
            attempt,
            RuntimeFailure("commit_history_mismatch", "base-to-HEAD paths cannot be observed"),
            final_step,
        )
    for path in history_paths.stdout.splitlines():
        scope = execution_model.validate_write_path(path, binding_result.value["write_scope"])
        if not scope.ok:
            return _stop(attempt, RuntimeFailure(scope.error.code, scope.error.message), final_step)
    for step_id in step_ids:
        gates = check_human_gates(
            attempt,
            step_id=step_id,
            timing="before_implementation_green",
        )
        if not gates.ok:
            return gates
    return append_event(attempt, "implementation_green", {"commits": commits})


def generate_attempt_id(
    *,
    now: Callable[[], str] | None = None,
    random_suffix: Callable[[], str] | None = None,
) -> str:
    timestamp = (
        now()
        if now is not None
        else datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")
    )
    suffix = random_suffix() if random_suffix is not None else secrets.token_hex(4)
    return f"{timestamp}-{suffix}"


def _attempt_payload(attempt: Attempt) -> dict[str, Any]:
    return {
        "attempt_id": attempt.attempt_id,
        "plan_id": attempt.plan_id,
        "branch": attempt.branch,
        "worktree": str(attempt.worktree),
        "binding_path": str(attempt.binding_path),
        "evidence_path": str(attempt.evidence_path),
    }


def _print_failure(result: RuntimeResult, *, state: str) -> int:
    payload = {
        "state": state,
        "reason": result.error.code,
        "message": result.error.message,
    }
    if result.error.detail:
        payload["detail"] = result.error.detail
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 2


def _load_for_command(repo: Path) -> RuntimeResult:
    return load_current_attempt(repo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bind and verify one normal Cycle execution")
    commands = parser.add_subparsers(dest="command", required=True)

    resolve = commands.add_parser("resolve", help="resolve and validate a registered plan")
    resolve.add_argument("--repo", required=True)
    resolve.add_argument("--plan-path")
    resolve.add_argument("--receipt-path")
    resolve.add_argument("--receipt-identity")

    bootstrap = commands.add_parser("bootstrap", help="claim a repository and create a worktree")
    bootstrap.add_argument("--repo", required=True)
    bootstrap.add_argument("--plan-path")
    bootstrap.add_argument("--receipt-path")
    bootstrap.add_argument("--receipt-identity")
    bootstrap.add_argument("--worktree", required=True)
    bootstrap.add_argument("--executor", required=True)
    bootstrap.add_argument("--backend", default="unavailable")
    bootstrap.add_argument("--session-id", default="unavailable")

    load = commands.add_parser("load", help="reconstruct the current attempt")
    load.add_argument("--repo", required=True)

    context = commands.add_parser("context", help="revalidate the current execution boundary")
    context.add_argument("--repo", required=True)
    context.add_argument("--step", required=True)

    red = commands.add_parser("accept-red", help="run and freeze an expected RED oracle")
    red.add_argument("--repo", required=True)
    red.add_argument("--oracle", required=True)

    run = commands.add_parser("run-oracle", help="run the frozen GREEN or REFACTOR oracle")
    run.add_argument("--repo", required=True)
    run.add_argument("--step", required=True)
    run.add_argument("--phase", choices=("green", "refactor"), required=True)

    stage = commands.add_parser("stage", help="stage approved files individually")
    stage.add_argument("--repo", required=True)
    stage.add_argument("--step", required=True)
    stage.add_argument("--path", action="append", required=True)

    record = commands.add_parser("record-commit", help="verify and record an existing commit")
    record.add_argument("--repo", required=True)
    record.add_argument("--step", required=True)
    record.add_argument("--previous-head", required=True)

    human_gate = commands.add_parser("human-gate", help="record a declared human gate decision")
    human_gate.add_argument("--repo", required=True)
    human_gate.add_argument("--step", required=True)
    human_gate.add_argument("--gate", required=True)
    human_gate.add_argument("--result", choices=("approved", "rejected"), required=True)

    check_gates = commands.add_parser(
        "check-gates",
        help="verify declared human gates before crossing a boundary",
    )
    check_gates.add_argument("--repo", required=True)
    check_gates.add_argument("--step", required=True)
    check_gates.add_argument(
        "--timing",
        choices=tuple(execution_model.HUMAN_GATE_TIMINGS),
        required=True,
    )

    stop = commands.add_parser("stop", help="record a blocking stop")
    stop.add_argument("--repo", required=True)
    stop.add_argument("--step", required=True)
    stop.add_argument("--reason", required=True)

    green = commands.add_parser(
        "implementation-green",
        help="record the Phase 3 terminal event",
    )
    green.add_argument("--repo", required=True)

    result = commands.add_parser("result", help="derive the current result from events")
    result.add_argument("--repo", required=True)

    args = parser.parse_args(argv)
    repo = Path(args.repo)
    if args.command in {"resolve", "bootstrap"}:
        receipt = None
        if args.receipt_path is not None or args.receipt_identity is not None:
            if args.receipt_path is None or args.receipt_identity is None:
                incomplete = _failure(
                    "publication_receipt_invalid",
                    "receipt path and identity must be supplied together",
                )
                return _print_failure(incomplete, state="not_started")
            receipt = {
                "path": args.receipt_path,
                "content_identity": args.receipt_identity,
            }
        resolved = resolve_plan(repo, explicit_path=args.plan_path, receipt=receipt)
        if not resolved.ok:
            return _print_failure(resolved, state="not_started")
        if args.command == "resolve":
            print(
                json.dumps(
                    {
                        "plan_id": resolved.value.plan_id,
                        "path": resolved.value.path,
                        "revision": resolved.value.revision,
                        "content_identity": resolved.value.content_identity,
                        "specs": [
                            {"path": path, "content_identity": identity}
                            for path, identity in resolved.value.specs
                        ],
                        "write_scope": list(resolved.value.write_scope),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        executor = {
            "executor": args.executor,
            "backend": args.backend,
            "session_id": args.session_id,
        }
        if args.backend == "unavailable" or args.session_id == "unavailable":
            executor["reason"] = "not exposed safely"
        bootstrapped = bootstrap_attempt(
            repo,
            resolved.value,
            worktree_path=Path(args.worktree),
            attempt_id_factory=generate_attempt_id,
            executor=executor,
        )
        if not bootstrapped.ok:
            return _print_failure(bootstrapped, state="not_started")
        payload = _attempt_payload(bootstrapped.value)
        payload["state"] = "stopped"
        payload["reason"] = "terminal_event_missing"
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    loaded = _load_for_command(repo)
    if not loaded.ok:
        return _print_failure(loaded, state="not_started")
    attempt = loaded.value
    if args.command == "load":
        print(json.dumps(_attempt_payload(attempt), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "context":
        operation = validate_context(attempt, step_id=args.step)
    elif args.command == "accept-red":
        oracle_path = Path(args.oracle)
        oracle_result = _read_json(oracle_path)
        operation = oracle_result if not oracle_result.ok else accept_red(attempt, oracle_result.value)
    elif args.command == "run-oracle":
        operation = run_frozen_oracle(attempt, args.step, args.phase)
    elif args.command == "stage":
        operation = stage_paths(attempt, args.path, step_id=args.step)
    elif args.command == "record-commit":
        operation = record_commit(attempt, args.step, args.previous_head)
    elif args.command == "human-gate":
        operation = record_human_gate(
            attempt,
            step_id=args.step,
            gate_id=args.gate,
            result=args.result,
        )
    elif args.command == "check-gates":
        checked = check_human_gates(attempt, step_id=args.step, timing=args.timing)
        operation = checked if not checked.ok else _ok(
            {
                "state": "approved",
                "step_id": args.step,
                "timing": args.timing,
                "target_identities": checked.value,
            }
        )
    elif args.command == "stop":
        operation = append_event(
            attempt,
            "stopped",
            {"reason": args.reason, "step_id": args.step},
        )
    elif args.command == "implementation-green":
        operation = mark_implementation_green(attempt)
    else:
        print(json.dumps(derive_attempt_result(attempt), ensure_ascii=False, sort_keys=True))
        return 0

    if not operation.ok:
        return _print_failure(operation, state="stopped")
    print(json.dumps(operation.value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
