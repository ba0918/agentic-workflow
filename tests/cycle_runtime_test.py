import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


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


def create_repository(parent: Path) -> tuple[Path, str, str]:
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
    git(root, "add", ".gitignore", "README.md", "docs/spec/feature.md")
    git(root, "commit", "-m", "fixture baseline")

    plan_id = "20260822150000"
    spec_identity = plan_artifact.content_identity(spec_text)
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


if __name__ == "__main__":
    unittest.main()
