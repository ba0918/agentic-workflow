#!/usr/bin/env python3
"""Filesystem, Git, and process boundaries for a normal Cycle execution."""

from __future__ import annotations

import errno
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


def resolve_plan(
    project_root: Path,
    *,
    explicit_path: str | None = None,
    receipt: dict[str, str] | None = None,
) -> RuntimeResult:
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

    if receipt is not None and explicit_path is None:
        if receipt.get("content_identity") != registered.content_identity:
            return _failure("plan_identity_drift", "publication receipt differs from the locator")
    parsed = _parse_plan(registered.text)
    if not parsed.ok:
        return parsed
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}"
    descriptor: int | None = None
    try:
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
        temporary.unlink(missing_ok=True)


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
        )
    )
