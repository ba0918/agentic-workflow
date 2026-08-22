import importlib.util
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
RUNTIME_MODULE = ROOT / "skills/ba0918-cycle/scripts/cycle_runtime.py"
SPEC = importlib.util.spec_from_file_location("cycle_runtime", RUNTIME_MODULE)
cycle_runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(cycle_runtime)


PLAN_ARTIFACT_MODULE = ROOT / "skills/ba0918-plan/scripts/plan_artifact.py"
PLAN_SPEC = importlib.util.spec_from_file_location("plan_artifact_for_runtime_test", PLAN_ARTIFACT_MODULE)
plan_artifact = importlib.util.module_from_spec(PLAN_SPEC)
assert PLAN_SPEC.loader is not None
PLAN_SPEC.loader.exec_module(plan_artifact)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def create_repository(
    parent: Path,
    *,
    human_gate: bool = False,
    human_gate_timing: str = "before_implementation_green",
) -> tuple[Path, str, str]:
    root = parent / "repository"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture User")
    (root / ".gitignore").write_text("/.agents/\n", encoding="utf-8")
    spec_text = "# Fixture specification\n\nFX-001: return a greeting.\n"
    spec_path = root / "docs/spec/feature.md"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(spec_text, encoding="utf-8")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    test_target = root / "tests/greeting_test.py"
    test_target.parent.mkdir(parents=True)
    test_target.write_text("# Cycle runtime target fixture\n", encoding="utf-8")
    git(root, "add", ".gitignore", "README.md", "docs/spec/feature.md", "tests/greeting_test.py")
    git(root, "commit", "-m", "fixture baseline")

    plan_id = "20260822150000"
    spec_identity = plan_artifact.content_identity(spec_text)
    gate_declaration = ""
    if human_gate:
        gate_declaration = """
**Human gates:**

```json
{
  "version": 1,
  "gates": [
    {
      "gate_id": "approve-greeting",
      "clauses": ["FX-001"],
      "criterion": "greeting実装が承認済みである",
      "target": {"kind": "files", "paths": ["src/greeting.py"]},
      "timing": "__HUMAN_GATE_TIMING__",
      "allowed_results": ["approved", "rejected"]
    }
  ]
}
```
""".replace("__HUMAN_GATE_TIMING__", human_gate_timing)
    plan_text = f"""# Fixture plan

**Plan ID:** `{plan_id}`
**Plan revision:** `1`
**対象仕様:**

- `docs/spec/feature.md`
  - 内容identity: `{spec_identity}`

## 変更するもの

```text
src/
  greeting.py
tests/
  greeting_test.py
```

## 実装手順

### 1. Greetingを実装する

**対応仕様:** `FX-001`
{gate_declaration}
"""
    plan_artifact.publish_plan(
        root,
        plan_id=plan_id,
        revision=1,
        relative_path=f".agents/artifacts/plans/{plan_id}_fixture.md",
        text=plan_text,
        approved_identity=plan_artifact.content_identity(plan_text),
        switch_confirmed=False,
        worktree_dirty=False,
    )
    return root, plan_id, spec_identity


def bootstrap_fixture(
    parent: Path,
    *,
    human_gate: bool = False,
    human_gate_timing: str = "before_implementation_green",
):
    root, _, _ = create_repository(
        parent,
        human_gate=human_gate,
        human_gate_timing=human_gate_timing,
    )
    resolved = cycle_runtime.resolve_plan(root).value
    result = cycle_runtime.bootstrap_attempt(
        root,
        resolved,
        worktree_path=parent / "linked-worktree",
        attempt_id_factory=lambda: "20260822t152244-a1b2c3d4",
        executor={
            "executor": "codex",
            "backend": "unavailable",
            "session_id": "unavailable",
            "reason": "not exposed safely",
        },
    )
    if not result.ok:
        raise AssertionError(result.error)
    return root, result.value


def red_oracle(command: list[str]) -> dict:
    return {
        "version": 1,
        "step_id": "step-1",
        "clauses": ["FX-001"],
        "test_targets": ["tests/greeting_test.py"],
        "command": command,
        "cwd": ".",
        "environment_names": [],
        "timeout_seconds": 10,
        "expected_failure_kind": "behavior_failure",
        "failure_signature": "greeting missing",
    }


class PlanResolutionTest(unittest.TestCase):
    def test_current_plan_metadata_and_specs_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, spec_identity = create_repository(Path(directory))

            result = cycle_runtime.resolve_plan(root)

            self.assertTrue(result.ok)
            self.assertEqual(result.value.plan_id, plan_id)
            self.assertEqual(result.value.revision, 1)
            self.assertEqual(
                result.value.specs,
                (("docs/spec/feature.md", spec_identity),),
            )
            self.assertEqual(
                result.value.write_scope,
                ("src/greeting.py", "tests/greeting_test.py"),
            )

    def test_explicit_unregistered_plan_is_rejected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = create_repository(Path(directory))
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            result = cycle_runtime.resolve_plan(
                root,
                explicit_path=".agents/artifacts/plans/20260822150001_missing.md",
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "plan_registration_missing")
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_receipt_identity_must_match_the_registered_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, _ = create_repository(Path(directory))

            result = cycle_runtime.resolve_plan(
                root,
                receipt={
                    "path": f".agents/artifacts/plans/{plan_id}_fixture.md",
                    "content_identity": "sha256:" + "0" * 64,
                },
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "plan_identity_drift")

    def test_explicit_path_and_receipt_must_not_disagree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, _ = create_repository(Path(directory))
            path = f".agents/artifacts/plans/{plan_id}_fixture.md"

            result = cycle_runtime.resolve_plan(
                root,
                explicit_path=path,
                receipt={
                    "path": path,
                    "content_identity": "sha256:" + "0" * 64,
                },
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "plan_candidate_conflict")

    def test_plan_header_revision_must_match_the_locator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, _ = create_repository(Path(directory))
            plan_path = root / f".agents/artifacts/plans/{plan_id}_fixture.md"
            index_path = plan_path.parent / "open-plans.json"
            changed = plan_path.read_text(encoding="utf-8").replace(
                "**Plan revision:** `1`",
                "**Plan revision:** `2`",
            )
            plan_path.write_text(changed, encoding="utf-8")
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["plans"][0]["content_identity"] = plan_artifact.content_identity(changed)
            index_path.write_text(json.dumps(index), encoding="utf-8")

            result = cycle_runtime.resolve_plan(root)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "plan_revision_drift")


class RepositoryDiscoveryTest(unittest.TestCase):
    def test_bare_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bare = Path(directory) / "bare.git"
            subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

            result = cycle_runtime.discover_repository(bare)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "bare_repository")

    def test_non_repository_is_rejected_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").write_text("gitdir: /definitely/missing\n", encoding="utf-8")

            result = cycle_runtime.discover_repository(root)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "repository_unavailable")

    def test_submodule_is_rejected_as_an_execution_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source = parent / "source"
            source.mkdir()
            git(source, "init", "-b", "main")
            git(source, "config", "user.email", "fixture@example.invalid")
            git(source, "config", "user.name", "Fixture User")
            (source / "source.txt").write_text("source\n", encoding="utf-8")
            git(source, "add", "source.txt")
            git(source, "commit", "-m", "source")
            superproject = parent / "superproject"
            superproject.mkdir()
            git(superproject, "init", "-b", "main")
            git(superproject, "config", "user.email", "fixture@example.invalid")
            git(superproject, "config", "user.name", "Fixture User")
            (superproject / "README.md").write_text("superproject\n", encoding="utf-8")
            git(superproject, "add", "README.md")
            git(superproject, "commit", "-m", "superproject")
            git(
                superproject,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(source),
                "nested",
            )

            result = cycle_runtime.discover_repository(superproject / "nested")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "submodule_repository")


class BootstrapTest(unittest.TestCase):
    def test_attempt_is_bound_before_a_clean_linked_worktree_is_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, plan_id, _ = create_repository(parent)
            (root / "dirty-only.txt").write_text("must stay in main\n", encoding="utf-8")
            resolved = cycle_runtime.resolve_plan(root).value
            worktree = parent / "linked-worktree"

            result = cycle_runtime.bootstrap_attempt(
                root,
                resolved,
                worktree_path=worktree,
                attempt_id_factory=lambda: "20260822t152244-a1b2c3d4",
                executor={
                    "executor": "codex",
                    "backend": "unavailable",
                    "session_id": "unavailable",
                    "reason": "not exposed safely",
                },
            )

            self.assertTrue(result.ok, result.error)
            attempt = result.value
            self.assertEqual(attempt.plan_id, plan_id)
            self.assertTrue(attempt.binding_path.is_file())
            self.assertFalse(worktree.joinpath("dirty-only.txt").exists())
            self.assertEqual(git(worktree, "rev-parse", "HEAD"), git(root, "rev-parse", "HEAD"))
            self.assertEqual(git(worktree, "rev-parse", "--show-toplevel"), str(worktree.resolve()))
            claim = json.loads(
                (root / ".agents/runtime/cycles/current.claim").read_text(encoding="utf-8")
            )
            self.assertEqual(claim["attempt_id"], attempt.attempt_id)
            self.assertEqual(claim["plan_id"], plan_id)
            events = sorted(attempt.evidence_path.glob("0*.json"))
            self.assertEqual([path.name for path in events], ["000001-worktree-bound.json"])
            self.assertLess(
                attempt.binding_path.stat().st_mtime_ns,
                events[0].stat().st_mtime_ns,
            )

    def test_existing_claim_prevents_all_attempt_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, _, _ = create_repository(parent)
            claim = root / ".agents/runtime/cycles/current.claim"
            claim.parent.mkdir(parents=True)
            claim.write_text('{"attempt_id":"existing"}\n', encoding="utf-8")
            before = claim.read_bytes()
            resolved = cycle_runtime.resolve_plan(root).value

            result = cycle_runtime.bootstrap_attempt(
                root,
                resolved,
                worktree_path=parent / "should-not-exist",
                attempt_id_factory=lambda: "20260822t152244-a1b2c3d4",
                executor={"executor": "codex", "backend": "unavailable", "session_id": "unavailable"},
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "cycle_claimed")
            self.assertEqual(claim.read_bytes(), before)
            self.assertFalse((root / ".agents/artifacts/executions").exists())
            self.assertFalse((parent / "should-not-exist").exists())

    def test_attempt_id_collision_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, plan_id, _ = create_repository(parent)
            attempt_id = "20260822t152244-a1b2c3d4"
            existing = root / f".agents/artifacts/executions/{plan_id}/{attempt_id}"
            existing.mkdir(parents=True)
            marker = existing / "marker"
            marker.write_text("keep\n", encoding="utf-8")
            resolved = cycle_runtime.resolve_plan(root).value

            result = cycle_runtime.bootstrap_attempt(
                root,
                resolved,
                worktree_path=parent / "should-not-exist",
                attempt_id_factory=lambda: attempt_id,
                executor={"executor": "codex", "backend": "unavailable", "session_id": "unavailable"},
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "attempt_collision")
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((parent / "should-not-exist").exists())

    def test_symlinked_agent_root_is_rejected_without_touching_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, _, _ = create_repository(parent)
            outside = parent / "outside"
            outside.mkdir()
            agents = root / ".agents"
            for path in sorted(agents.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            agents.rmdir()
            agents.symlink_to(outside, target_is_directory=True)
            marker = outside / "marker"
            marker.write_text("keep\n", encoding="utf-8")

            result = cycle_runtime.bootstrap_attempt(
                root,
                None,
                worktree_path=parent / "should-not-exist",
                attempt_id_factory=lambda: "20260822t152244-a1b2c3d4",
                executor={"executor": "codex", "backend": "unavailable", "session_id": "unavailable"},
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "unsafe_path")
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")


class AtomicWriteTest(unittest.TestCase):
    def test_permission_denial_is_distinct_and_leaves_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "event.json"

            def deny(*_args, **_kwargs):
                raise PermissionError("sandbox denied")

            result = cycle_runtime.write_once(target, b"candidate\n", opener=deny)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "permission_required")
            self.assertFalse(target.exists())

    def test_read_only_storage_is_persistence_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "event.json"

            def read_only(*_args, **_kwargs):
                raise OSError(30, "read-only filesystem")

            result = cycle_runtime.write_once(target, b"candidate\n", opener=read_only)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "persistence_unavailable")
            self.assertFalse(target.exists())

    def test_parent_directory_permission_denial_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "missing" / "event.json"
            with mock.patch.object(
                Path,
                "mkdir",
                side_effect=PermissionError(errno.EACCES, "denied"),
            ):
                result = cycle_runtime.write_once(target, b"evidence")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "permission_required")
            self.assertFalse(target.exists())


class FreshSessionTest(unittest.TestCase):
    def test_current_attempt_is_reconstructed_from_claim_binding_and_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))

            result = cycle_runtime.load_current_attempt(root)

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value.attempt_id, attempt.attempt_id)
            self.assertEqual(result.value.worktree, attempt.worktree)
            self.assertEqual(result.value.binding_path, attempt.binding_path)

    def test_context_rejects_spec_drift_and_scope_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            spec = attempt.worktree / "docs/spec/feature.md"
            spec.write_text(spec.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

            spec_result = cycle_runtime.validate_context(attempt, step_id="step-1")

            self.assertFalse(spec_result.ok)
            self.assertEqual(spec_result.error.code, "spec_identity_drift")
            git(attempt.worktree, "checkout", "--", "docs/spec/feature.md")
            (attempt.worktree / "outside.txt").write_text("outside\n", encoding="utf-8")

            scope_result = cycle_runtime.validate_context(attempt, step_id="step-1")

            self.assertFalse(scope_result.ok)
            self.assertEqual(scope_result.error.code, "write_scope_violation")

    def test_unregistered_worktree_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            forged = attempt._replace(worktree=Path(directory) / "repository")

            result = cycle_runtime.validate_context(forged, step_id="step-1")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "worktree_identity_drift")


class EventPersistenceTest(unittest.TestCase):
    def test_terminal_requires_current_approval_for_a_declared_human_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory), human_gate=True)
            candidate = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('src/greeting.py').is_file(); "
                        "print('green' if exists else 'greeting missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            self.assertTrue(cycle_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            self.assertTrue(
                cycle_runtime.record_commit(attempt, "step-1", previous_head).ok
            )

            missing = cycle_runtime.mark_implementation_green(attempt)
            approved = cycle_runtime.record_human_gate(
                attempt,
                step_id="step-1",
                gate_id="approve-greeting",
                result="approved",
            )
            terminal = cycle_runtime.mark_implementation_green(attempt)

            self.assertEqual(missing.error.code, "human_gate_missing")
            self.assertTrue(approved.ok, approved.error)
            self.assertTrue(terminal.ok, terminal.error)

    def test_terminal_rechecks_the_frozen_test_target_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            candidate = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('src/greeting.py').is_file(); "
                        "print('green' if exists else 'greeting missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            self.assertTrue(cycle_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            self.assertTrue(cycle_runtime.record_commit(attempt, "step-1", previous_head).ok)
            (attempt.worktree / "tests/greeting_test.py").write_text(
                "# weakened after the commit\n",
                encoding="utf-8",
            )

            result = cycle_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "test_identity_drift")
    def test_event_retry_is_idempotent_only_for_the_same_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            details = {"reason": "permission_required", "step_id": "step-1"}

            first = cycle_runtime.append_event(
                attempt,
                "stopped",
                details,
                sequence=2,
            )
            same = cycle_runtime.append_event(
                attempt,
                "stopped",
                details,
                sequence=2,
            )
            collision = cycle_runtime.append_event(
                attempt,
                "stopped",
                {"reason": "persistence_unavailable", "step_id": "step-1"},
                sequence=2,
            )

            self.assertTrue(first.ok)
            self.assertTrue(same.ok)
            self.assertEqual(first.value["content_identity"], same.value["content_identity"])
            self.assertFalse(collision.ok)
            self.assertEqual(collision.error.code, "event_identity_collision")
            events = sorted(attempt.evidence_path.glob("0*.json"))
            self.assertEqual(len(events), 2)

    def test_result_is_derived_without_a_result_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            cycle_runtime.append_event(
                attempt,
                "stopped",
                {"reason": "identity_drift", "step_id": "step-1"},
            )

            result = cycle_runtime.derive_attempt_result(attempt)

            self.assertEqual(result["state"], "stopped")
            self.assertEqual(result["reason"], "identity_drift")
            self.assertEqual(result["branch"], attempt.branch)
            self.assertFalse((attempt.evidence_path / "result.json").exists())

    def test_implementation_green_is_derived_from_a_terminal_event_after_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))

            missing = cycle_runtime.mark_implementation_green(attempt)
            self.assertFalse(missing.ok)
            self.assertEqual(missing.error.code, "commit_missing")
            candidate = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('src/greeting.py').is_file(); "
                        "print('green' if exists else 'greeting missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            self.assertTrue(cycle_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            commit_sha = git(attempt.worktree, "rev-parse", "HEAD")
            self.assertTrue(
                cycle_runtime.record_commit(attempt, "step-1", previous_head).ok
            )

            terminal = cycle_runtime.mark_implementation_green(attempt)
            result = cycle_runtime.derive_attempt_result(attempt)

            self.assertTrue(terminal.ok, terminal.error)
            self.assertEqual(terminal.value["event_type"], "implementation_green")
            self.assertEqual(result["state"], "implementation_green")
            self.assertEqual(result["commits"], [commit_sha])

    def test_implementation_green_rejects_a_committed_step_without_tdd_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            cycle_runtime.append_event(
                attempt,
                "commit",
                {"step_id": "step-1", "commit_sha": "7" * 40, "outcome": "committed"},
            )

            result = cycle_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "step_evidence_missing")

    def test_implementation_green_rejects_post_verification_dirtiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            candidate = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('src/greeting.py').is_file(); "
                        "print('green' if exists else 'greeting missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            self.assertTrue(cycle_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            self.assertTrue(
                cycle_runtime.record_commit(attempt, "step-1", previous_head).ok
            )
            production.write_text("changed after final verification\n", encoding="utf-8")

            result = cycle_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "post_verification_dirty")
            self.assertEqual(cycle_runtime.derive_attempt_result(attempt)["state"], "stopped")


class OracleExecutionTest(unittest.TestCase):
    def test_unittest_summary_reports_passed_failed_and_skipped_counts(self) -> None:
        output = """..FsE
----------------------------------------------------------------------
Ran 5 tests in 0.012s

FAILED (failures=1, errors=1, skipped=1)
"""

        summary = cycle_runtime._test_summary("", output)

        self.assertEqual(
            summary,
            {"status": "complete", "passed": 2, "failed": 2, "skipped": 1},
        )

    def test_summary_is_complete_only_for_one_consistent_supported_report(self) -> None:
        cases = {
            "unittest success": (
                "Ran 3 tests in 0.004s\n\nOK (skipped=2)\n",
                {"status": "complete", "passed": 1, "failed": 0, "skipped": 2},
            ),
            "no structured report": (
                "all checks look fine\n",
                {
                    "status": "unavailable",
                    "reason": "runner did not expose one supported structured summary",
                },
            ),
            "duplicate report": (
                "Ran 1 test in 0.1s\nOK\nRan 1 test in 0.1s\nOK\n",
                {
                    "status": "unavailable",
                    "reason": "runner did not expose one supported structured summary",
                },
            ),
            "impossible counts": (
                "Ran 1 test in 0.1s\nFAILED (failures=2)\n",
                {
                    "status": "unavailable",
                    "reason": "runner did not expose one supported structured summary",
                },
            ),
        }

        for case, (output, expected) in cases.items():
            with self.subTest(case=case):
                self.assertEqual(cycle_runtime._test_summary("", output), expected)

    def test_oracle_cwd_cannot_escape_the_worktree_through_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            _, attempt = bootstrap_fixture(parent)
            outside = parent / "outside"
            outside.mkdir()
            (attempt.worktree / "linked-cwd").symlink_to(outside, target_is_directory=True)
            oracle = red_oracle(["python3", "-c", "raise SystemExit(0)"])
            oracle["cwd"] = "linked-cwd"

            result = cycle_runtime._execute_oracle(attempt, oracle)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "unsafe_path")

    def test_expected_red_freezes_oracle_and_records_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    "import sys; print('greeting missing'); sys.exit(1)",
                ]
            )

            result = cycle_runtime.accept_red(attempt, oracle)

            self.assertTrue(result.ok, result.error)
            oracle_path = attempt.evidence_path / "oracles/step-1.json"
            self.assertTrue(oracle_path.is_file())
            event = result.value
            self.assertEqual(event["event_type"], "red")
            self.assertEqual(event["outcome"], "expected_failure")
            self.assertEqual(event["observation"], "greeting missing")

    def test_expected_red_adds_the_observed_failure_kind_after_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                ["python3", "-c", "import sys; print('greeting missing'); sys.exit(1)"]
            )
            result = cycle_runtime.accept_red(attempt, oracle)

            self.assertTrue(result.ok, result.error)
            frozen = json.loads(
                (attempt.evidence_path / "oracles/step-1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(frozen["observed_failure_kind"], "behavior_failure")

    def test_red_command_that_changes_a_spec_stops_before_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "Path('docs/spec/feature.md').write_text('changed\\n'); "
                        "print('greeting missing'); sys.exit(1)"
                    ),
                ]
            )

            result = cycle_runtime.accept_red(attempt, oracle)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "spec_identity_drift")
            self.assertFalse((attempt.evidence_path / "oracles/step-1.json").exists())
            self.assertEqual(cycle_runtime.derive_attempt_result(attempt)["state"], "stopped")

    def test_import_failure_is_not_accepted_as_red(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    "import module_that_does_not_exist_for_cycle_fixture",
                ]
            )

            result = cycle_runtime.accept_red(attempt, oracle)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "unintended_red")
            self.assertEqual(cycle_runtime.derive_attempt_result(attempt)["state"], "stopped")
            self.assertFalse((attempt.evidence_path / "oracles/step-1.json").exists())

    def test_generic_unittest_summary_is_rejected_before_red_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "import sys; "
                        "sys.stderr.write(\"ModuleNotFoundError: No module named 'src'\\n\""
                        "+ \"FAILED (errors=1)\\n\"); "
                        "sys.exit(1)"
                    ),
                ]
            )
            oracle["failure_signature"] = "FAILED (errors=1)"

            result = cycle_runtime.accept_red(attempt, oracle)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "oracle_failure_signature_invalid")
            self.assertEqual(cycle_runtime.derive_attempt_result(attempt)["state"], "stopped")
            self.assertFalse((attempt.evidence_path / "oracles/step-1.json").exists())

    def test_process_classification_uses_diagnostics_before_generic_summary(self) -> None:
        stderr = "ModuleNotFoundError: No module named 'src'\nFAILED (errors=1)\n"

        self.assertEqual(
            cycle_runtime._classify_process_failure("", stderr),
            "import_failure",
        )
        self.assertEqual(
            cycle_runtime._bounded_observation("", stderr),
            "ModuleNotFoundError: No module named 'src'",
        )

    def test_green_and_refactor_reuse_the_frozen_oracle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('src/greeting.py').is_file(); "
                        "print('green' if exists else 'greeting missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            self.assertTrue(cycle_runtime.accept_red(attempt, oracle).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")

            green = cycle_runtime.run_frozen_oracle(attempt, "step-1", "green")
            refactor = cycle_runtime.run_frozen_oracle(attempt, "step-1", "refactor")

            self.assertTrue(green.ok, green.error)
            self.assertTrue(refactor.ok, refactor.error)
            self.assertEqual(green.value["oracle_identity"], refactor.value["oracle_identity"])
            self.assertEqual(green.value["outcome"], "passed")
            self.assertEqual(refactor.value["outcome"], "passed")

    def test_changed_frozen_oracle_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    "import sys; print('greeting missing'); sys.exit(1)",
                ]
            )
            red = cycle_runtime.accept_red(attempt, oracle)
            self.assertTrue(red.ok)
            oracle_path = attempt.evidence_path / "oracles/step-1.json"
            changed = json.loads(oracle_path.read_text(encoding="utf-8"))
            changed["command"] = ["python3", "-c", "raise SystemExit(0)"]
            oracle_path.write_text(json.dumps(changed), encoding="utf-8")

            result = cycle_runtime.run_frozen_oracle(attempt, "step-1", "green")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "oracle_identity_drift")

    def test_changed_frozen_test_target_is_rejected_before_green(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            candidate = red_oracle(
                ["python3", "-c", "import sys; print('greeting missing'); sys.exit(1)"]
            )
            red = cycle_runtime.accept_red(attempt, candidate)
            self.assertTrue(red.ok, red.error)
            (attempt.worktree / "tests/greeting_test.py").write_text(
                "# weakened after RED\n",
                encoding="utf-8",
            )

            result = cycle_runtime.run_frozen_oracle(attempt, "step-1", "green")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "test_identity_drift")

    def test_permission_required_keeps_the_event_chain_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            candidate = red_oracle(
                ["python3", "-c", "import sys; print('greeting missing'); sys.exit(1)"]
            )
            denied = cycle_runtime._failure(
                "permission_required",
                "oracle command requires additional permission",
            )
            expected_red = cycle_runtime._ok(
                {
                    "exit_code": 1,
                    "observation": "greeting missing",
                    "failure_kind": "behavior_failure",
                    "test_summary": {
                        "status": "unavailable",
                        "reason": "runner did not expose one supported structured summary",
                    },
                }
            )
            with mock.patch.object(
                cycle_runtime,
                "_execute_oracle",
                side_effect=[denied, expected_red],
            ):
                first = cycle_runtime.accept_red(attempt, candidate)
                second = cycle_runtime.accept_red(attempt, candidate)

            events = cycle_runtime._load_events(attempt).value
            self.assertEqual(first.error.code, "permission_required")
            self.assertTrue(second.ok, second.error)
            self.assertEqual([event["event_type"] for event in events], [
                "worktree-bound",
                "permission_required",
                "red",
            ])


class CommitBoundaryTest(unittest.TestCase):
    def prepare_green_change(self, attempt):
        candidate = red_oracle(
            [
                "python3",
                "-c",
                (
                    "from pathlib import Path; import sys; "
                    "exists=Path('src/greeting.py').is_file(); "
                    "print('green' if exists else 'greeting missing'); "
                    "sys.exit(0 if exists else 1)"
                ),
            ]
        )
        self.assertTrue(cycle_runtime.accept_red(attempt, candidate).ok)
        production = attempt.worktree / "src/greeting.py"
        production.parent.mkdir(parents=True)
        production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
        self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
        self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
        return production

    def test_frozen_test_target_drift_blocks_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            candidate = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('src/greeting.py').is_file(); "
                        "print('green' if exists else 'greeting missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            self.assertTrue(cycle_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(cycle_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            (attempt.worktree / "tests/greeting_test.py").write_text(
                "# weakened before staging\n",
                encoding="utf-8",
            )

            result = cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "test_identity_drift")
            self.assertEqual(git(attempt.worktree, "diff", "--cached", "--name-only"), "")

    def test_only_scoped_files_can_be_staged_and_recorded_after_a_clean_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.prepare_green_change(attempt)

            staged = cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1")
            self.assertTrue(staged.ok, staged.error)
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            recorded = cycle_runtime.record_commit(attempt, "step-1", previous_head)

            self.assertTrue(recorded.ok, recorded.error)
            self.assertEqual(recorded.value["event_type"], "commit")
            self.assertEqual(recorded.value["commit_sha"], git(attempt.worktree, "rev-parse", "HEAD"))

    def test_hidden_scope_external_ancestor_commit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.prepare_green_change(attempt)
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            outside = attempt.worktree / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            git(attempt.worktree, "add", "outside.txt")
            git(attempt.worktree, "commit", "-m", "chore: hidden outside change")
            self.assertTrue(
                cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            git(attempt.worktree, "commit", "-m", "feat: add greeting")

            result = cycle_runtime.record_commit(attempt, "step-1", previous_head)

            self.assertFalse(result.ok)
            self.assertIn(result.error.code, {"commit_range_invalid", "write_scope_violation"})

    def test_terminal_rejects_a_hidden_commit_accepted_as_the_previous_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.prepare_green_change(attempt)
            outside = attempt.worktree / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            git(attempt.worktree, "add", "outside.txt")
            git(attempt.worktree, "commit", "-m", "chore: hidden outside change")
            hidden_head = git(attempt.worktree, "rev-parse", "HEAD")
            self.assertTrue(
                cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            recorded = cycle_runtime.record_commit(attempt, "step-1", hidden_head)
            self.assertTrue(recorded.ok, recorded.error)

            result = cycle_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "commit_history_mismatch")

    def test_post_commit_dirty_state_is_rejected_without_an_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            production = self.prepare_green_change(attempt)
            self.assertTrue(
                cycle_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            production.write_text("changed after commit\n", encoding="utf-8")

            result = cycle_runtime.record_commit(attempt, "step-1", previous_head)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "post_commit_dirty")

    def test_scope_violation_is_not_staged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            outside = attempt.worktree / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")

            result = cycle_runtime.stage_paths(attempt, ["outside.txt"], step_id="step-1")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "write_scope_violation")
            self.assertEqual(git(attempt.worktree, "diff", "--cached", "--name-only"), "")

    def test_scope_validation_finishes_before_any_path_is_staged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            (attempt.worktree / "outside.txt").write_text("outside\n", encoding="utf-8")

            result = cycle_runtime.stage_paths(
                attempt,
                ["src/greeting.py", "outside.txt"],
                step_id="step-1",
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "write_scope_violation")
            self.assertEqual(git(attempt.worktree, "diff", "--cached", "--name-only"), "")

    def test_secret_detection_finishes_before_any_path_is_staged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("API_TOKEN=not-a-real-token\n", encoding="utf-8")

            result = cycle_runtime.stage_paths(
                attempt,
                ["src/greeting.py"],
                step_id="step-1",
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "secret_detected")
            self.assertEqual(git(attempt.worktree, "diff", "--cached", "--name-only"), "")


class InstructionContractTest(unittest.TestCase):
    def test_instructions_describe_the_current_runtime_boundaries(self) -> None:
        skill_root = ROOT / "skills/ba0918-cycle"
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        execution = (skill_root / "references/execution.md").read_text(encoding="utf-8")
        tdd = (skill_root / "references/tdd.md").read_text(encoding="utf-8")
        evidence = (skill_root / "references/evidence.md").read_text(encoding="utf-8")

        self.assertIn("test_targets", tdd)
        self.assertNotIn("`test_identity`", tdd)
        self.assertIn("human-gate", execution)
        self.assertIn("check-gates", execution)
        self.assertIn("before_edit", execution)
        self.assertIn("complete", evidence)
        self.assertIn("unavailable", evidence)
        self.assertIn("Never start an implementation\n  subagent", skill)


class CommandLineTest(unittest.TestCase):
    def call_main(self, arguments: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cycle_runtime.main(arguments)
        return exit_code, json.loads(output.getvalue())

    def test_attempt_id_generation_is_path_safe_and_injectable(self) -> None:
        attempt_id = cycle_runtime.generate_attempt_id(
            now=lambda: "20260822t160000",
            random_suffix=lambda: "a1b2c3d4",
        )

        self.assertEqual(attempt_id, "20260822t160000-a1b2c3d4")
        self.assertIsNotNone(cycle_runtime.execution_model.ATTEMPT_ID.fullmatch(attempt_id))

    def test_help_lists_human_gate_commands_and_invalid_results_are_cli_errors(self) -> None:
        help_output = io.StringIO()
        with contextlib.redirect_stdout(help_output), self.assertRaises(SystemExit) as help_exit:
            cycle_runtime.main(["--help"])

        error_output = io.StringIO()
        with contextlib.redirect_stderr(error_output), self.assertRaises(SystemExit) as error_exit:
            cycle_runtime.main(
                [
                    "human-gate",
                    "--repo",
                    ".",
                    "--step",
                    "step-1",
                    "--gate",
                    "approve-files",
                    "--result",
                    "maybe",
                ]
            )

        self.assertEqual(help_exit.exception.code, 0)
        self.assertIn("human-gate", help_output.getvalue())
        self.assertIn("check-gates", help_output.getvalue())
        self.assertEqual(error_exit.exception.code, 2)
        self.assertIn("invalid choice", error_output.getvalue())

    def test_resolve_command_prints_metadata_without_plan_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, _ = create_repository(Path(directory))
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                exit_code = cycle_runtime.main(["resolve", "--repo", str(root)])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["plan_id"], plan_id)
            self.assertNotIn("text", payload)

    def test_human_gate_command_records_only_the_declared_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), human_gate=True)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")

            exit_code, payload = self.call_main(
                [
                    "human-gate",
                    "--repo",
                    str(root),
                    "--step",
                    "step-1",
                    "--gate",
                    "approve-greeting",
                    "--result",
                    "approved",
                ]
            )

            self.assertEqual(exit_code, 0, payload)
            self.assertEqual(payload["event_type"], "human_gate")
            self.assertEqual(payload["gate_id"], "approve-greeting")
            self.assertEqual(payload["result"], "approved")

    def test_check_gates_command_blocks_before_edit_until_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(
                Path(directory),
                human_gate=True,
                human_gate_timing="before_edit",
            )
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")

            missing_code, missing = self.call_main(
                [
                    "check-gates",
                    "--repo",
                    str(root),
                    "--step",
                    "step-1",
                    "--timing",
                    "before_edit",
                ]
            )
            self.assertEqual(missing_code, 2)
            self.assertEqual(missing["reason"], "human_gate_missing")
            self.assertTrue(
                cycle_runtime.record_human_gate(
                    attempt,
                    step_id="step-1",
                    gate_id="approve-greeting",
                    result="approved",
                ).ok
            )

            approved_code, approved = self.call_main(
                [
                    "check-gates",
                    "--repo",
                    str(root),
                    "--step",
                    "step-1",
                    "--timing",
                    "before_edit",
                ]
            )

            self.assertEqual(approved_code, 0, approved)
            self.assertEqual(approved["state"], "approved")

    def test_failure_command_returns_structured_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").write_text("gitdir: /definitely/missing\n", encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                exit_code = cycle_runtime.main(["resolve", "--repo", str(root)])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["state"], "not_started")
            self.assertEqual(payload["reason"], "plan_registration_missing")

    def test_cli_routes_a_complete_attempt_without_a_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, _, _ = create_repository(parent)
            worktree = parent / "cli-worktree"

            bootstrap_code, bootstrap = self.call_main(
                [
                    "bootstrap",
                    "--repo",
                    str(root),
                    "--worktree",
                    str(worktree),
                    "--executor",
                    "codex",
                ]
            )
            self.assertEqual(bootstrap_code, 0, bootstrap)
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('src/greeting.py').is_file(); "
                        "print('green' if exists else 'greeting missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            oracle_path = root / ".agents/tmp/oracle.json"
            oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
            self.assertEqual(
                self.call_main(
                    ["accept-red", "--repo", str(root), "--oracle", str(oracle_path)]
                )[0],
                0,
            )
            production = worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            for phase in ("green", "refactor"):
                self.assertEqual(
                    self.call_main(
                        [
                            "run-oracle",
                            "--repo",
                            str(root),
                            "--step",
                            "step-1",
                            "--phase",
                            phase,
                        ]
                    )[0],
                    0,
                )
            self.assertEqual(
                self.call_main(
                    [
                        "stage",
                        "--repo",
                        str(root),
                        "--step",
                        "step-1",
                        "--path",
                        "src/greeting.py",
                    ]
                )[0],
                0,
            )
            previous_head = git(worktree, "rev-parse", "HEAD")
            git(worktree, "commit", "-m", "feat: add greeting")
            self.assertEqual(
                self.call_main(
                    [
                        "record-commit",
                        "--repo",
                        str(root),
                        "--step",
                        "step-1",
                        "--previous-head",
                        previous_head,
                    ]
                )[0],
                0,
            )
            self.assertEqual(self.call_main(["implementation-green", "--repo", str(root)])[0], 0)

            result_code, result = self.call_main(["result", "--repo", str(root)])

            self.assertEqual(result_code, 0)
            self.assertEqual(result["state"], "implementation_green")
            self.assertFalse((Path(bootstrap["evidence_path"]) / "result.json").exists())

if __name__ == "__main__":
    unittest.main()
