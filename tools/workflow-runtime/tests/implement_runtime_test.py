import importlib.util
import itertools
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[3]
RUNTIME_MODULE = ROOT / "tools/workflow-runtime/implement/implement_runtime.py"
SPEC = importlib.util.spec_from_file_location("implement_runtime", RUNTIME_MODULE)
implement_runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(implement_runtime)


PLAN_ARTIFACT_MODULE = ROOT / "tools/workflow-runtime/plan/plan_artifact.py"
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


PASSING_CHECK = "python3 -c pass"
FAILING_CHECK = "python3 -c \"import sys; sys.exit(3)\""


def declared_checks(commands: tuple[str, ...]) -> str:
    """The **Checks:** declaration a check step needs, written as the plan specification writes it."""
    return "\n**Checks:**\n\n" + "".join(f"- `{command}`\n" for command in commands)


def create_repository(
    parent: Path,
    *,
    human_gate: bool = False,
    human_gate_timing: str = "before_implementation_green",
    step_kinds: tuple[str, ...] = ("test",),
    check_commands: tuple[str, ...] = (PASSING_CHECK,),
) -> tuple[Path, str, str]:
    root = parent / "repository"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture User")
    (root / ".gitignore").write_text("/.agents/\n", encoding="utf-8")
    spec_text = "# Fixture specification\n\n## Greeting\n\nReturn a greeting.\n"
    spec_path = root / "docs/spec/feature.md"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(spec_text, encoding="utf-8")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    test_target = root / "tests/greeting_test.py"
    test_target.parent.mkdir(parents=True)
    test_target.write_text("# implement runtime target fixture\n", encoding="utf-8")
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
      "sections": ["Greeting"],
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
**Target specifications:**

- `docs/spec/feature.md`
  - content identity: `{spec_identity}`
  - sections: `Greeting`

## Scope

```text
src/
  greeting.py
tests/
  greeting_test.py
docs/
  guide.md
```

## Steps

### 1. Greetingを実装する

**Completion:** {step_kinds[0]}
{gate_declaration}
""" + "".join(
        f"\n### {number}. 手順 {number}\n\n**Completion:** {kind}\n"
        + (declared_checks(check_commands) if kind == "check" else "")
        for number, kind in enumerate(step_kinds[1:], start=2)
    )
    publish_text(
        root,
        plan_id=plan_id,
        revision=1,
        relative_path=f".agents/artifacts/plans/{plan_id}_fixture.md",
        text=plan_text,
        approved_identity=plan_artifact.content_identity(plan_text),
        switch_confirmed=False,
    )
    return root, plan_id, spec_identity


def bootstrap_fixture(
    parent: Path,
    *,
    human_gate: bool = False,
    human_gate_timing: str = "before_implementation_green",
    step_kinds: tuple[str, ...] = ("test",),
    check_commands: tuple[str, ...] = (PASSING_CHECK,),
):
    root, _, _ = create_repository(
        parent,
        human_gate=human_gate,
        human_gate_timing=human_gate_timing,
        step_kinds=step_kinds,
        check_commands=check_commands,
    )
    resolved = implement_runtime.resolve_plan(root).value
    result = implement_runtime.bootstrap_attempt(
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


GREETING_ORACLE_COMMAND = [
    "python3",
    "-c",
    (
        "from pathlib import Path; import sys; "
        "exists=Path('src/greeting.py').is_file(); "
        "print('green' if exists else 'greeting missing'); "
        "sys.exit(0 if exists else 1)"
    ),
]


def complete_step_one(attempt) -> str:
    """Drive step 1 through RED, GREEN, REFACTOR and commit; return the commit SHA."""
    assert implement_runtime.accept_red(attempt, red_oracle(GREETING_ORACLE_COMMAND)).ok
    production = attempt.worktree / "src/greeting.py"
    production.parent.mkdir(parents=True, exist_ok=True)
    production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
    assert implement_runtime.run_frozen_oracle(attempt, "step-1", "green").ok
    assert implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok
    assert implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
    previous_head = git(attempt.worktree, "rev-parse", "HEAD")
    git(attempt.worktree, "commit", "-m", "feat: add greeting")
    assert implement_runtime.record_commit(attempt, "step-1", previous_head).ok
    return git(attempt.worktree, "rev-parse", "HEAD")


def complete_fixture(parent: Path):
    root, attempt = bootstrap_fixture(parent)
    complete_step_one(attempt)
    terminal = implement_runtime.mark_implementation_green(attempt)
    assert terminal.ok, terminal.error
    return root, attempt


def red_oracle(command: list[str]) -> dict:
    return {
        "version": 1,
        "step_id": "step-1",
        "sections": ["Greeting"],
        "test_targets": ["tests/greeting_test.py"],
        "command": command,
        "cwd": ".",
        "environment_names": [],
        "timeout_seconds": 10,
        "expected_failure_kind": "behavior_failure",
        "failure_signature": "greeting missing",
    }


_DRAFT_SEQUENCE = itertools.count(1)


def publish_text(root: Path, **kwargs):
    """Save the draft first, then publish it: the production path always starts from a draft."""
    text = kwargs.pop("text")
    plan_id = kwargs["plan_id"]
    revision = kwargs["revision"]
    slug = f"draft-{next(_DRAFT_SEQUENCE)}"
    draft = plan_artifact.save_draft(root, plan_id=plan_id, revision=revision, slug=slug, text=text)
    return plan_artifact.publish_plan(root, source=draft.path, **kwargs)


def revise_fixture_plan(root: Path, plan_id: str, *, extra_step_kind: str = "test", relative_path: str | None = None):
    """Publish revision 2 of the fixture plan: step 1 kept verbatim, one step appended."""
    current = plan_artifact.read_registered_plan(root, None)
    assert current.plan_id == plan_id
    revised = current.text.replace("**Plan revision:** `1`", "**Plan revision:** `2`")
    revised += f"\n### {len(plan_artifact.read_plan_steps(current.text)) + 1}. 追加の手順\n\n**Completion:** {extra_step_kind}\n"
    publish_text(
        root,
        plan_id=plan_id,
        revision=2,
        relative_path=relative_path or f".agents/artifacts/plans/{plan_id}_fixture-r2.md",
        text=revised,
        approved_identity=plan_artifact.content_identity(revised),
        switch_confirmed=False,
    )
    return plan_artifact.read_registered_plan(root, None)


class PlanResolutionTest(unittest.TestCase):
    def test_legacy_plan_format_is_rejected_as_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, _ = create_repository(Path(directory))
            plan_path = root / f".agents/artifacts/plans/{plan_id}_fixture.md"
            legacy = plan_path.read_text(encoding="utf-8").replace("**Target specifications:**", "**対象仕様:**")
            plan_path.write_text(legacy, encoding="utf-8")
            index_path = root / ".agents/artifacts/plans/open-plans.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["plans"][0]["content_identity"] = plan_artifact.content_identity(legacy)
            index_path.write_text(json.dumps(index), encoding="utf-8")

            result = implement_runtime.resolve_plan(root)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "plan_format_invalid")
            self.assertIn("Target specifications", result.error.message)

    def test_resolved_plan_exposes_steps_with_their_completion_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = create_repository(Path(directory))

            result = implement_runtime.resolve_plan(root)

            self.assertTrue(result.ok, result.error)
            self.assertEqual([(step.number, step.completion_kind) for step in result.value.steps], [(1, "test")])

    def test_declared_human_gate_sections_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = create_repository(Path(directory), human_gate=True)

            result = implement_runtime.resolve_plan(root)

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value.human_gates[0]["sections"], ["Greeting"])
            self.assertNotIn("clauses", result.value.human_gates[0])

    def test_current_plan_metadata_and_specs_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, spec_identity = create_repository(Path(directory))

            result = implement_runtime.resolve_plan(root)

            self.assertTrue(result.ok)
            self.assertEqual(result.value.plan_id, plan_id)
            self.assertEqual(result.value.revision, 1)
            self.assertEqual(
                result.value.specs,
                (("docs/spec/feature.md", spec_identity),),
            )
            self.assertEqual(
                result.value.write_scope,
                ("src/greeting.py", "tests/greeting_test.py", "docs/guide.md"),
            )

    def test_a_temporary_plan_draft_is_never_resolved_as_the_current_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = create_repository(Path(directory))
            registered = implement_runtime.resolve_plan(root)
            self.assertTrue(registered.ok, registered.error)
            draft = plan_artifact.save_draft(
                root,
                plan_id="20260822150001",
                revision=1,
                slug="unapproved",
                text=registered.value.text.replace("20260822150000", "20260822150001"),
            )

            result = implement_runtime.resolve_plan(
                root, explicit_path=draft.path.relative_to(root).as_posix()
            )

            self.assertFalse(result.ok)
            self.assertIn(result.error.code, {"plan_registration_missing", "unsafe_path"})
            self.assertEqual(implement_runtime.resolve_plan(root).value.plan_id, registered.value.plan_id)

    def test_explicit_unregistered_plan_is_rejected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = create_repository(Path(directory))
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            result = implement_runtime.resolve_plan(
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

            result = implement_runtime.resolve_plan(
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

            result = implement_runtime.resolve_plan(
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

            result = implement_runtime.resolve_plan(root)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "plan_revision_drift")


class RepositoryDiscoveryTest(unittest.TestCase):
    def test_bare_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bare = Path(directory) / "bare.git"
            subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

            result = implement_runtime.discover_repository(bare)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "bare_repository")

    def test_non_repository_is_rejected_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").write_text("gitdir: /definitely/missing\n", encoding="utf-8")

            result = implement_runtime.discover_repository(root)

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

            result = implement_runtime.discover_repository(superproject / "nested")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "submodule_repository")


class BranchNamingTest(unittest.TestCase):
    def test_execution_branch_is_named_implement_followed_by_the_execution_id(self) -> None:
        self.assertEqual(
            implement_runtime.execution_branch("20260822t152244-a1b2c3d4"),
            "implement/20260822t152244-a1b2c3d4",
        )


class BootstrapTest(unittest.TestCase):
    def test_attempt_is_bound_before_a_clean_linked_worktree_is_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, plan_id, _ = create_repository(parent)
            (root / "dirty-only.txt").write_text("must stay in main\n", encoding="utf-8")
            resolved = implement_runtime.resolve_plan(root).value
            worktree = parent / "linked-worktree"

            result = implement_runtime.bootstrap_attempt(
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
            self.assertFalse((root / ".agents/runtime").exists())
            binding = json.loads(attempt.binding_path.read_text(encoding="utf-8"))
            self.assertEqual(binding["worktree"], str(worktree.resolve()))
            events = sorted(attempt.evidence_path.glob("0*.json"))
            self.assertEqual([path.name for path in events], ["000001-worktree-bound.json"])
            self.assertLess(
                attempt.binding_path.stat().st_mtime_ns,
                events[0].stat().st_mtime_ns,
            )

    def test_a_second_execution_of_the_same_plan_is_not_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, _, _ = create_repository(parent)
            resolved = implement_runtime.resolve_plan(root).value
            executor = {
                "executor": "codex",
                "backend": "unavailable",
                "session_id": "unavailable",
                "reason": "not exposed safely",
            }
            first = implement_runtime.bootstrap_attempt(
                root,
                resolved,
                worktree_path=parent / "first-worktree",
                attempt_id_factory=lambda: "20260822t152244-a1b2c3d4",
                executor=executor,
            )
            self.assertTrue(first.ok, first.error)

            second = implement_runtime.bootstrap_attempt(
                root,
                resolved,
                worktree_path=parent / "second-worktree",
                attempt_id_factory=lambda: "20260822t160000-b2c3d4e5",
                executor=executor,
            )

            self.assertTrue(second.ok, second.error)
            self.assertNotEqual(first.value.branch, second.value.branch)
            self.assertTrue((parent / "first-worktree").is_dir())
            self.assertTrue((parent / "second-worktree").is_dir())

    def test_binding_requires_the_worktree_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            binding = json.loads(attempt.binding_path.read_text(encoding="utf-8"))
            del binding["worktree"]

            result = implement_runtime.execution_model.validate_binding(binding)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "binding_fields_invalid")

    def test_attempt_id_collision_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, plan_id, _ = create_repository(parent)
            attempt_id = "20260822t152244-a1b2c3d4"
            existing = root / f".agents/artifacts/executions/{plan_id}/{attempt_id}"
            existing.mkdir(parents=True)
            marker = existing / "marker"
            marker.write_text("keep\n", encoding="utf-8")
            resolved = implement_runtime.resolve_plan(root).value

            result = implement_runtime.bootstrap_attempt(
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

            result = implement_runtime.bootstrap_attempt(
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

            result = implement_runtime.write_once(target, b"candidate\n", opener=deny)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "permission_required")
            self.assertFalse(target.exists())

    def test_read_only_storage_is_persistence_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "event.json"

            def read_only(*_args, **_kwargs):
                raise OSError(30, "read-only filesystem")

            result = implement_runtime.write_once(target, b"candidate\n", opener=read_only)

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
                result = implement_runtime.write_once(target, b"evidence")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "permission_required")
            self.assertFalse(target.exists())


class FreshSessionTest(unittest.TestCase):
    def test_execution_is_reconstructed_from_its_evidence_directory_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))

            result = implement_runtime.load_current_attempt(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value.attempt_id, attempt.attempt_id)
            self.assertEqual(result.value.worktree, attempt.worktree)
            self.assertEqual(result.value.binding_path, attempt.binding_path)
            self.assertFalse((root / ".agents/runtime").exists())

    def test_the_only_unfinished_execution_of_the_current_plan_is_loaded_without_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))

            result = implement_runtime.load_current_attempt(root)

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value.attempt_id, attempt.attempt_id)

    def test_several_unfinished_executions_require_explicit_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, attempt = bootstrap_fixture(parent)
            resolved = implement_runtime.resolve_plan(root).value
            second = implement_runtime.bootstrap_attempt(
                root,
                resolved,
                worktree_path=parent / "second-worktree",
                attempt_id_factory=lambda: "20260822t160000-b2c3d4e5",
                executor={
                    "executor": "codex",
                    "backend": "unavailable",
                    "session_id": "unavailable",
                    "reason": "not exposed safely",
                },
            )
            self.assertTrue(second.ok, second.error)

            result = implement_runtime.load_current_attempt(root)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "execution_ambiguous")
            self.assertIn(attempt.attempt_id, result.error.detail)
            self.assertIn("20260822t160000-b2c3d4e5", result.error.detail)

    def test_missing_or_broken_evidence_is_reported_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            cases = {
                "missing binding": lambda: attempt.binding_path.unlink(),
                "broken binding": lambda: attempt.binding_path.write_text("{", encoding="utf-8"),
                "missing worktree": lambda: git(root, "worktree", "remove", "--force", str(attempt.worktree)),
            }
            for case, damage in cases.items():
                with self.subTest(case=case):
                    before = sorted(path.name for path in attempt.evidence_path.glob("0*.json"))
                    damage()

                    result = implement_runtime.load_current_attempt(
                        root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
                    )

                    self.assertFalse(result.ok)
                    self.assertEqual(
                        sorted(path.name for path in attempt.evidence_path.glob("0*.json")), before
                    )

    def test_plan_identity_drift_is_reported_by_context_not_by_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            binding = json.loads(attempt.binding_path.read_text(encoding="utf-8"))
            binding["plan"]["content_identity"] = "sha256:" + "0" * 64
            attempt.binding_path.write_text(json.dumps(binding), encoding="utf-8")

            loaded = implement_runtime.load_current_attempt(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertTrue(loaded.ok, loaded.error)
            context = implement_runtime.validate_context(loaded.value, step_id="step-1")
            self.assertFalse(context.ok)
            self.assertEqual(context.error.code, "plan_identity_drift")

    def test_context_rejects_spec_drift_but_reports_out_of_scope_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            spec = attempt.worktree / "docs/spec/feature.md"
            spec.write_text(spec.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

            spec_result = implement_runtime.validate_context(attempt, step_id="step-1")

            self.assertFalse(spec_result.ok)
            self.assertEqual(spec_result.error.code, "spec_identity_drift")
            git(attempt.worktree, "checkout", "--", "docs/spec/feature.md")
            (attempt.worktree / "outside.txt").write_text("outside\n", encoding="utf-8")

            scope_result = implement_runtime.validate_context(attempt, step_id="step-1")

            self.assertTrue(scope_result.ok, scope_result.error)
            self.assertEqual(scope_result.value["out_of_scope_changes"], ["outside.txt"])

    def test_unregistered_worktree_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            forged = attempt._replace(worktree=Path(directory) / "repository")

            result = implement_runtime.validate_context(forged, step_id="step-1")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "worktree_identity_drift")


class ArtifactStepTest(unittest.TestCase):
    def test_artifact_files_inside_the_scope_are_recorded_with_their_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            guide = attempt.worktree / "docs/guide.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text("# Guide\n", encoding="utf-8")

            result = implement_runtime.record_artifact(attempt, step_id="step-1", paths=["docs/guide.md"], checks=[])

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value["event_type"], "artifact")
            self.assertEqual(
                result.value["files"],
                [{"path": "docs/guide.md", "content_identity": plan_artifact.content_identity("# Guide\n")}],
            )
            self.assertEqual(result.value["checks"], [])

    def test_artifact_paths_outside_the_scope_or_missing_are_refused_without_an_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            for case, path in {"outside scope": "README.md", "missing": "docs/guide.md", "traversal": "../x"}.items():
                with self.subTest(case=case):
                    result = implement_runtime.record_artifact(attempt, step_id="step-1", paths=[path], checks=[])

                    self.assertFalse(result.ok)
            events = sorted(p.name for p in attempt.evidence_path.glob("0*.json"))
            self.assertEqual(events, ["000001-worktree-bound.json"])

    def test_format_checks_run_in_the_worktree_and_their_exit_code_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            guide = attempt.worktree / "docs/guide.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text("# Guide\n", encoding="utf-8")
            checks = [
                ["python3", "-c", "from pathlib import Path; raise SystemExit(0 if Path('docs/guide.md').is_file() else 1)"],
                ["python3", "-c", "raise SystemExit(3)"],
            ]

            result = implement_runtime.record_artifact(attempt, step_id="step-1", paths=["docs/guide.md"], checks=checks)

            self.assertTrue(result.ok, result.error)
            self.assertEqual([check["exit_code"] for check in result.value["checks"]], [0, 3])

    def test_artifact_evidence_is_refused_on_a_test_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            guide = attempt.worktree / "docs/guide.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text("# Guide\n", encoding="utf-8")

            result = implement_runtime.record_artifact(attempt, step_id="step-1", paths=["docs/guide.md"], checks=[])

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "completion_kind_mismatch")
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "stopped")


class ExternalStepTest(unittest.TestCase):
    def test_external_check_is_recorded_with_what_was_checked_and_a_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("external",))

            result = implement_runtime.record_external(
                attempt, step_id="step-1", checked="手順 1 の実機確認", summary="起動して応答した"
            )

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value["event_type"], "external")
            self.assertEqual(result.value["checked"], "手順 1 の実機確認")

    def test_external_evidence_is_refused_on_a_test_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))

            result = implement_runtime.record_external(attempt, step_id="step-1", checked="x", summary="y")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "completion_kind_mismatch")

    def test_external_summary_must_be_bounded_and_free_of_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("external",))
            for case, summary in {"too long": "x" * 501, "secret": "to" + "ken=abc123 で認証した"}.items():
                with self.subTest(case=case):
                    result = implement_runtime.record_external(attempt, step_id="step-1", checked="確認", summary=summary)

                    self.assertFalse(result.ok)
            events = sorted(p.name for p in attempt.evidence_path.glob("0*.json"))
            self.assertEqual(events, ["000001-worktree-bound.json"])

    def test_record_external_command_prints_the_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("external",))
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = implement_runtime.main(
                    ["record-external", "--repo", str(root), "--step", "step-1", "--checked", "確認", "--summary", "OK"]
                )

            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["event_type"], "external")


def record_guide(attempt, text: str = "# Guide\n"):
    guide = attempt.worktree / "docs/guide.md"
    guide.parent.mkdir(parents=True, exist_ok=True)
    guide.write_text(text, encoding="utf-8")
    result = implement_runtime.record_artifact(attempt, step_id="step-1", paths=["docs/guide.md"], checks=[])
    assert result.ok, result.error
    return result.value


class ApprovalTest(unittest.TestCase):
    def test_approval_targets_the_latest_artifact_evidence_of_the_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            artifact = record_guide(attempt)

            result = implement_runtime.record_approval(attempt, step_id="step-1", result="approved")

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value["event_type"], "approval")
            self.assertEqual(result.value["target_identity"], artifact["content_identity"])
            self.assertEqual(result.value["result"], "approved")

    def test_a_deliverable_whose_format_check_failed_cannot_be_approved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            guide = attempt.worktree / "docs/guide.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text("# Guide\n", encoding="utf-8")
            recorded = implement_runtime.record_artifact(
                attempt, step_id="step-1", paths=["docs/guide.md"], checks=[["python3", "-c", "raise SystemExit(3)"]]
            )
            self.assertTrue(recorded.ok, recorded.error)

            result = implement_runtime.record_approval(attempt, step_id="step-1", result="approved")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "format_check_failed")
            names = sorted(p.name for p in attempt.evidence_path.glob("0*.json"))
            self.assertEqual(names[-1], "000002-artifact.json")

    def test_approval_without_anything_to_approve_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))

            result = implement_runtime.record_approval(attempt, step_id="step-1", result="approved")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "approval_target_missing")

    def test_rejection_is_recorded_and_stops_the_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            record_guide(attempt)

            result = implement_runtime.record_approval(attempt, step_id="step-1", result="rejected")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "approval_rejected")
            names = sorted(p.name for p in attempt.evidence_path.glob("0*.json"))
            self.assertEqual(names[-2:], ["000003-approval.json", "000004-stopped.json"])
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "stopped")

    def test_approval_is_refused_on_a_test_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))

            result = implement_runtime.record_approval(attempt, step_id="step-1", result="approved")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "completion_kind_mismatch")

    def test_approve_command_records_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("external",))
            self.assertTrue(implement_runtime.record_external(attempt, step_id="step-1", checked="確認", summary="OK").ok)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = implement_runtime.main(["approve", "--repo", str(root), "--step", "step-1", "--result", "approved"])

            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["event_type"], "approval")


def commit_guide(attempt) -> str:
    assert implement_runtime.stage_paths(attempt, ["docs/guide.md"], step_id="step-1").ok
    previous_head = git(attempt.worktree, "rev-parse", "HEAD")
    git(attempt.worktree, "commit", "-m", "docs: add guide")
    assert implement_runtime.record_commit(attempt, "step-1", previous_head).ok
    return git(attempt.worktree, "rev-parse", "HEAD")


class CompletionByKindTest(unittest.TestCase):
    def test_artifact_step_cannot_be_staged_before_the_human_approved_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            record_guide(attempt)

            result = implement_runtime.stage_paths(attempt, ["docs/guide.md"], step_id="step-1")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "approval_missing")

    def test_a_deliverable_changed_after_approval_needs_a_new_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            record_guide(attempt)
            self.assertTrue(implement_runtime.record_approval(attempt, step_id="step-1", result="approved").ok)
            record_guide(attempt, "# Guide\n\nrevised\n")

            result = implement_runtime.stage_paths(attempt, ["docs/guide.md"], step_id="step-1")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "approval_missing")

    def test_an_artifact_only_plan_reaches_implementation_green(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            record_guide(attempt)
            self.assertTrue(implement_runtime.record_approval(attempt, step_id="step-1", result="approved").ok)
            commit_guide(attempt)

            terminal = implement_runtime.mark_implementation_green(attempt)

            self.assertTrue(terminal.ok, terminal.error)
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "implementation_green")

    def test_an_external_step_is_complete_after_approval_with_or_without_a_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact", "external"))
            record_guide(attempt)
            self.assertTrue(implement_runtime.record_approval(attempt, step_id="step-1", result="approved").ok)
            commit_guide(attempt)
            self.assertTrue(implement_runtime.record_external(attempt, step_id="step-2", checked="確認", summary="OK").ok)
            missing = implement_runtime.mark_implementation_green(attempt)
            self.assertFalse(missing.ok)
            self.assertEqual(missing.error.code, "step_evidence_missing")
            self.assertTrue(implement_runtime.record_approval(attempt, step_id="step-2", result="approved").ok)

            terminal = implement_runtime.mark_implementation_green(attempt)

            self.assertTrue(terminal.ok, terminal.error)

    def test_three_kinds_in_one_plan_reach_implementation_green(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "artifact", "external"))
            complete_step_one(attempt)
            guide = attempt.worktree / "docs/guide.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text("# Guide\n", encoding="utf-8")
            self.assertTrue(implement_runtime.record_artifact(attempt, step_id="step-2", paths=["docs/guide.md"], checks=[]).ok)
            self.assertTrue(implement_runtime.record_approval(attempt, step_id="step-2", result="approved").ok)
            self.assertTrue(implement_runtime.stage_paths(attempt, ["docs/guide.md"], step_id="step-2").ok)
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "docs: add guide")
            self.assertTrue(implement_runtime.record_commit(attempt, "step-2", previous_head).ok)
            self.assertTrue(implement_runtime.record_external(attempt, step_id="step-3", checked="確認", summary="OK").ok)
            self.assertTrue(implement_runtime.record_approval(attempt, step_id="step-3", result="approved").ok)

            terminal = implement_runtime.mark_implementation_green(attempt)

            self.assertTrue(terminal.ok, terminal.error)

    def test_evidence_of_the_wrong_kind_does_not_complete_a_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("artifact",))
            self.assertFalse(implement_runtime.accept_red(attempt, red_oracle(GREETING_ORACLE_COMMAND)).ok)

            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["reason"], "completion_kind_mismatch")


class ResidualWorkTest(unittest.TestCase):
    def test_unfinished_execution_is_reported_with_its_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))

            result = implement_runtime.residual_executions(root, plan_id=attempt.plan_id)

            self.assertTrue(result.ok, result.error)
            self.assertEqual(len(result.value), 1)
            facts = result.value[0]
            self.assertEqual(facts["execution_id"], attempt.attempt_id)
            self.assertEqual(facts["started_at"], "2026-08-22T15:22:44")
            self.assertEqual(facts["completed_steps"], 0)
            self.assertEqual(facts["last_event"], {"event_type": "worktree-bound", "reason": None})
            self.assertEqual(facts["branch"], {"name": attempt.branch, "exists": True, "extra_commits": []})
            self.assertEqual(
                facts["worktree"],
                {"path": str(attempt.worktree), "exists": True, "registered": True, "changed_files": []},
            )
            self.assertEqual(facts["resumable"], {"ok": True, "reason": None})

    def test_finished_execution_is_not_residual(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = complete_fixture(Path(directory))

            result = implement_runtime.residual_executions(root, plan_id=attempt.plan_id)

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value, [])

    def test_commits_outside_the_evidence_and_uncommitted_changes_are_shown_not_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            (attempt.worktree / "README.md").write_text("edited by hand\n", encoding="utf-8")
            git(attempt.worktree, "commit", "-am", "manual: edit readme")
            manual_sha = git(attempt.worktree, "rev-parse", "HEAD")
            (attempt.worktree / "notes.txt").write_text("scratch\n", encoding="utf-8")

            facts = implement_runtime.residual_executions(root, plan_id=attempt.plan_id).value[0]

            self.assertEqual([commit["sha"] for commit in facts["branch"]["extra_commits"]], [manual_sha])
            self.assertEqual(facts["branch"]["extra_commits"][0]["subject"], "manual: edit readme")
            self.assertEqual(facts["worktree"]["changed_files"], ["notes.txt"])
            self.assertTrue(facts["resumable"]["ok"])

    def test_every_history_commit_the_record_does_not_explain_is_shown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            (attempt.worktree / "README.md").write_text("edited by hand\n", encoding="utf-8")
            git(attempt.worktree, "commit", "-am", "manual: edit readme")
            manual_sha = git(attempt.worktree, "rev-parse", "HEAD")
            complete_step_one(attempt)

            facts = implement_runtime.residual_executions(root, plan_id=attempt.plan_id).value[0]

            self.assertEqual([commit["sha"] for commit in facts["branch"]["extra_commits"]], [manual_sha])

    def test_specification_drift_makes_the_execution_not_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            spec = root / "docs/spec/feature.md"
            spec.write_text(spec.read_text(encoding="utf-8") + "revised\n", encoding="utf-8")

            facts = implement_runtime.residual_executions(root, plan_id=attempt.plan_id).value[0]

            self.assertFalse(facts["resumable"]["ok"])
            self.assertIn("docs/spec/feature.md", facts["resumable"]["reason"])

    def test_a_branch_without_evidence_is_not_residual(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, plan_id, _ = create_repository(Path(directory))
            git(root, "branch", "implement/20260822t152244-a1b2c3d4")

            result = implement_runtime.residual_executions(root, plan_id=plan_id)

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value, [])

    def test_residual_command_prints_the_facts_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = implement_runtime.main(["residual", "--repo", str(root), "--plan-id", attempt.plan_id])

            self.assertEqual(code, 0)
            printed = json.loads(stdout.getvalue())
            self.assertEqual(printed["executions"][0]["execution_id"], attempt.attempt_id)

    def test_residual_detection_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            before = sorted(path.name for path in attempt.evidence_path.iterdir())

            implement_runtime.residual_executions(root, plan_id=attempt.plan_id)

            self.assertEqual(sorted(path.name for path in attempt.evidence_path.iterdir()), before)


class ResumeTest(unittest.TestCase):
    def test_resume_records_the_resumed_event_and_names_the_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))

            result = implement_runtime.resume_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value["next_step"], "step-1")
            self.assertFalse(result.value["redo"])
            events = sorted(path.name for path in attempt.evidence_path.glob("0*.json"))
            self.assertEqual(events[-1], "000002-resumed.json")
            resumed = json.loads((attempt.evidence_path / events[-1]).read_text(encoding="utf-8"))
            self.assertEqual(resumed["head"], git(attempt.worktree, "rev-parse", "HEAD"))
            self.assertEqual(resumed["extra_commits"], [])
            self.assertFalse(resumed["uncommitted_changes"])

    def test_resume_after_the_last_committed_step_reports_that_every_step_is_committed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            complete_step_one(attempt)

            result = implement_runtime.resume_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertTrue(result.ok, result.error)
            self.assertIsNone(result.value["next_step"])
            self.assertTrue(result.value["all_steps_committed"])
            self.assertEqual(result.value["completed_steps"], ["step-1"])

    def test_resume_after_a_stop_is_allowed_and_the_chain_continues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            stopped = implement_runtime.accept_red(attempt, red_oracle(["python3", "-c", "print('fine')"]))
            self.assertFalse(stopped.ok)
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "stopped")

            result = implement_runtime.resume_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertTrue(result.ok, result.error)
            self.assertTrue(implement_runtime.validate_context(attempt, step_id="step-1").ok)
            self.assertTrue(implement_runtime.accept_red(attempt, red_oracle(GREETING_ORACLE_COMMAND)).ok)

    def test_resume_after_an_unfinished_red_redoes_that_step_with_a_fresh_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            self.assertTrue(implement_runtime.accept_red(attempt, red_oracle(GREETING_ORACLE_COMMAND)).ok)

            result = implement_runtime.resume_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value["next_step"], "step-1")
            self.assertTrue(result.value["redo"])
            different = red_oracle(GREETING_ORACLE_COMMAND)
            different["failure_signature"] = "greeting"
            self.assertTrue(implement_runtime.accept_red(attempt, different).ok, "a new RED replaces the old freeze")

    def test_resume_records_commits_outside_the_evidence_and_uncommitted_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            (attempt.worktree / "README.md").write_text("edited by hand\n", encoding="utf-8")
            git(attempt.worktree, "commit", "-am", "manual: edit readme")
            manual_sha = git(attempt.worktree, "rev-parse", "HEAD")
            (attempt.worktree / "notes.txt").write_text("scratch\n", encoding="utf-8")

            result = implement_runtime.resume_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertTrue(result.ok, result.error)
            resumed = json.loads((attempt.evidence_path / "000002-resumed.json").read_text(encoding="utf-8"))
            self.assertEqual(resumed["extra_commits"], [manual_sha])
            self.assertTrue(resumed["uncommitted_changes"])
            self.assertTrue((attempt.worktree / "notes.txt").is_file())

    def test_a_redone_step_runs_through_green_refactor_commit_and_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            self.assertTrue(implement_runtime.accept_red(attempt, red_oracle(GREETING_ORACLE_COMMAND)).ok)

            resumed = implement_runtime.resume_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )
            self.assertTrue(resumed.ok, resumed.error)
            self.assertTrue(resumed.value["redo"])
            fresh = red_oracle(GREETING_ORACLE_COMMAND)
            fresh["failure_signature"] = "greeting"
            self.assertTrue(implement_runtime.accept_red(attempt, fresh).ok)

            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            green = implement_runtime.run_frozen_oracle(attempt, "step-1", "green")
            self.assertTrue(green.ok, green.error)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok)
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            self.assertTrue(implement_runtime.record_commit(attempt, "step-1", previous_head).ok)

            terminal = implement_runtime.mark_implementation_green(attempt)
            self.assertTrue(terminal.ok, terminal.error)
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "implementation_green")

    def test_resume_command_prints_the_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                code = implement_runtime.main(
                    ["resume", "--repo", str(root), "--plan-id", attempt.plan_id, "--execution-id", attempt.attempt_id]
                )

            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["next_step"], "step-1")

    def test_resume_refuses_an_execution_bound_to_a_changed_specification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            spec = root / "docs/spec/feature.md"
            spec.write_text(spec.read_text(encoding="utf-8") + "revised\n", encoding="utf-8")

            result = implement_runtime.resume_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "spec_identity_drift")
            self.assertEqual(
                sorted(path.name for path in attempt.evidence_path.glob("0*.json")),
                ["000001-worktree-bound.json"],
            )


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
            self.assertTrue(implement_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            self.assertTrue(
                implement_runtime.record_commit(attempt, "step-1", previous_head).ok
            )

            missing = implement_runtime.mark_implementation_green(attempt)
            approved = implement_runtime.record_human_gate(
                attempt,
                step_id="step-1",
                gate_id="approve-greeting",
                result="approved",
            )
            terminal = implement_runtime.mark_implementation_green(attempt)

            self.assertEqual(missing.error.code, "human_gate_missing")
            self.assertTrue(approved.ok, approved.error)
            self.assertTrue(terminal.ok, terminal.error)

    def test_a_test_file_rewritten_after_the_commit_still_blocks_the_hand_off(self) -> None:
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
            self.assertTrue(implement_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            self.assertTrue(implement_runtime.record_commit(attempt, "step-1", previous_head).ok)
            (attempt.worktree / "tests/greeting_test.py").write_text(
                "# weakened after the commit\n",
                encoding="utf-8",
            )

            result = implement_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            # The terminal freeze check now judges targets as of the step's commit; an
            # uncommitted rewrite is refused as a dirty worktree instead.
            self.assertEqual(result.error.code, "post_verification_dirty")
    def test_event_retry_is_idempotent_only_for_the_same_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            details = {"reason": "permission_required", "step_id": "step-1"}

            first = implement_runtime.append_event(
                attempt,
                "stopped",
                details,
                sequence=2,
            )
            same = implement_runtime.append_event(
                attempt,
                "stopped",
                details,
                sequence=2,
            )
            collision = implement_runtime.append_event(
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
            implement_runtime.append_event(
                attempt,
                "stopped",
                {"reason": "identity_drift", "step_id": "step-1"},
            )

            result = implement_runtime.derive_attempt_result(attempt)

            self.assertEqual(result["state"], "stopped")
            self.assertEqual(result["reason"], "identity_drift")
            self.assertEqual(result["branch"], attempt.branch)
            self.assertFalse((attempt.evidence_path / "result.json").exists())

    def test_implementation_green_is_derived_from_a_terminal_event_after_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))

            missing = implement_runtime.mark_implementation_green(attempt)
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
            self.assertTrue(implement_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            commit_sha = git(attempt.worktree, "rev-parse", "HEAD")
            self.assertTrue(
                implement_runtime.record_commit(attempt, "step-1", previous_head).ok
            )

            terminal = implement_runtime.mark_implementation_green(attempt)
            result = implement_runtime.derive_attempt_result(attempt)

            self.assertTrue(terminal.ok, terminal.error)
            self.assertEqual(terminal.value["event_type"], "implementation_green")
            self.assertEqual(result["state"], "implementation_green")
            self.assertEqual(result["commits"], [commit_sha])

    def test_implementation_green_rejects_a_committed_step_without_tdd_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            implement_runtime.append_event(
                attempt,
                "commit",
                {"step_id": "step-1", "commit_sha": "7" * 40, "outcome": "committed"},
            )

            result = implement_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "step_evidence_missing")

    def test_implementation_green_rejects_in_scope_post_verification_dirtiness(self) -> None:
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
            self.assertTrue(implement_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            self.assertTrue(
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            self.assertTrue(
                implement_runtime.record_commit(attempt, "step-1", previous_head).ok
            )
            production.write_text("changed after final verification\n", encoding="utf-8")

            result = implement_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "post_verification_dirty")
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "stopped")


class OracleExecutionTest(unittest.TestCase):
    def test_unittest_summary_reports_passed_failed_and_skipped_counts(self) -> None:
        output = """..FsE
----------------------------------------------------------------------
Ran 5 tests in 0.012s

FAILED (failures=1, errors=1, skipped=1)
"""

        summary = implement_runtime._test_summary("", output)

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
                self.assertEqual(implement_runtime._test_summary("", output), expected)

    def test_oracle_cwd_cannot_escape_the_worktree_through_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            _, attempt = bootstrap_fixture(parent)
            outside = parent / "outside"
            outside.mkdir()
            (attempt.worktree / "linked-cwd").symlink_to(outside, target_is_directory=True)
            oracle = red_oracle(["python3", "-c", "raise SystemExit(0)"])
            oracle["cwd"] = "linked-cwd"

            result = implement_runtime._execute_oracle(attempt, oracle)

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

            result = implement_runtime.accept_red(attempt, oracle)

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
            result = implement_runtime.accept_red(attempt, oracle)

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

            result = implement_runtime.accept_red(attempt, oracle)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "spec_identity_drift")
            self.assertFalse((attempt.evidence_path / "oracles/step-1.json").exists())
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "stopped")

    def test_import_failure_is_not_accepted_as_red(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    "import module_that_does_not_exist_for_implement_fixture",
                ]
            )

            result = implement_runtime.accept_red(attempt, oracle)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "unintended_red")
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "stopped")
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

            result = implement_runtime.accept_red(attempt, oracle)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "oracle_failure_signature_invalid")
            self.assertEqual(implement_runtime.derive_attempt_result(attempt)["state"], "stopped")
            self.assertFalse((attempt.evidence_path / "oracles/step-1.json").exists())

    def test_process_classification_uses_diagnostics_before_generic_summary(self) -> None:
        stderr = "ModuleNotFoundError: No module named 'src'\nFAILED (errors=1)\n"

        self.assertEqual(
            implement_runtime._classify_process_failure("", stderr),
            "import_failure",
        )
        self.assertEqual(
            implement_runtime._bounded_observation("", stderr),
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
            self.assertTrue(implement_runtime.accept_red(attempt, oracle).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")

            green = implement_runtime.run_frozen_oracle(attempt, "step-1", "green")
            refactor = implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor")

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
            red = implement_runtime.accept_red(attempt, oracle)
            self.assertTrue(red.ok)
            oracle_path = attempt.evidence_path / "oracles/step-1.json"
            changed = json.loads(oracle_path.read_text(encoding="utf-8"))
            changed["command"] = ["python3", "-c", "raise SystemExit(0)"]
            oracle_path.write_text(json.dumps(changed), encoding="utf-8")

            result = implement_runtime.run_frozen_oracle(attempt, "step-1", "green")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "oracle_identity_drift")

    def test_changed_frozen_test_target_is_rejected_before_green(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            candidate = red_oracle(
                ["python3", "-c", "import sys; print('greeting missing'); sys.exit(1)"]
            )
            red = implement_runtime.accept_red(attempt, candidate)
            self.assertTrue(red.ok, red.error)
            (attempt.worktree / "tests/greeting_test.py").write_text(
                "# weakened after RED\n",
                encoding="utf-8",
            )

            result = implement_runtime.run_frozen_oracle(attempt, "step-1", "green")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "test_identity_drift")

    def test_permission_required_keeps_the_event_chain_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            candidate = red_oracle(
                ["python3", "-c", "import sys; print('greeting missing'); sys.exit(1)"]
            )
            denied = implement_runtime._failure(
                "permission_required",
                "oracle command requires additional permission",
            )
            expected_red = implement_runtime._ok(
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
            # accept_red reads execute_oracle from runtime.tdd, so the double must be
            # installed where it is used, not on the facade's re-export.
            with mock.patch.object(
                implement_runtime.tdd,
                "execute_oracle",
                side_effect=[denied, expected_red],
            ):
                first = implement_runtime.accept_red(attempt, candidate)
                second = implement_runtime.accept_red(attempt, candidate)

            events = implement_runtime._load_events(attempt).value
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
        self.assertTrue(implement_runtime.accept_red(attempt, candidate).ok)
        production = attempt.worktree / "src/greeting.py"
        production.parent.mkdir(parents=True)
        production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
        self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
        self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
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
            self.assertTrue(implement_runtime.accept_red(attempt, candidate).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "green").ok)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-1", "refactor").ok)
            (attempt.worktree / "tests/greeting_test.py").write_text(
                "# weakened before staging\n",
                encoding="utf-8",
            )

            result = implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "test_identity_drift")
            self.assertEqual(git(attempt.worktree, "diff", "--cached", "--name-only"), "")

    def test_only_scoped_files_can_be_staged_and_recorded_after_a_clean_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.prepare_green_change(attempt)

            staged = implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1")
            self.assertTrue(staged.ok, staged.error)
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            recorded = implement_runtime.record_commit(attempt, "step-1", previous_head)

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
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            git(attempt.worktree, "commit", "-m", "feat: add greeting")

            result = implement_runtime.record_commit(attempt, "step-1", previous_head)

            self.assertFalse(result.ok)
            self.assertIn(result.error.code, {"commit_range_invalid", "write_scope_violation"})

    def test_terminal_lists_a_hidden_commit_accepted_as_the_previous_head_for_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.prepare_green_change(attempt)
            outside = attempt.worktree / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            git(attempt.worktree, "add", "outside.txt")
            git(attempt.worktree, "commit", "-m", "chore: hidden outside change")
            hidden_head = git(attempt.worktree, "rev-parse", "HEAD")
            self.assertTrue(
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            recorded = implement_runtime.record_commit(attempt, "step-1", hidden_head)
            self.assertTrue(recorded.ok, recorded.error)

            result = implement_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "history_approval_required")
            approved = implement_runtime.cli.approve_history(attempt)
            self.assertEqual(approved.value["unexplained_commits"], [hidden_head])
            self.assertTrue(implement_runtime.mark_implementation_green(attempt).ok)

    def test_post_commit_dirty_state_is_rejected_without_an_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            production = self.prepare_green_change(attempt)
            self.assertTrue(
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")
            production.write_text("changed after commit\n", encoding="utf-8")

            result = implement_runtime.record_commit(attempt, "step-1", previous_head)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "post_commit_dirty")

    def test_uncommitted_changes_outside_the_commit_do_not_block_recording(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.prepare_green_change(attempt)
            guide = attempt.worktree / "docs/guide.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text("# Guide\n", encoding="utf-8")
            self.assertTrue(
                implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add greeting")

            recorded = implement_runtime.record_commit(attempt, "step-1", previous_head)

            self.assertTrue(recorded.ok, recorded.error)
            self.assertEqual(recorded.value["commit_sha"], git(attempt.worktree, "rev-parse", "HEAD"))
            self.assertEqual(git(attempt.worktree, "status", "--porcelain"), "?? docs/guide.md")

    def commit_without_recording(self, attempt) -> str:
        self.prepare_green_change(attempt)
        self.assertTrue(implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1").ok)
        git(attempt.worktree, "commit", "-m", "feat: add greeting")
        return git(attempt.worktree, "rev-parse", "HEAD")

    def test_a_commit_the_record_missed_can_be_recorded_late(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            sha = self.commit_without_recording(attempt)

            recorded = implement_runtime.record_commit_late(attempt, "step-1", sha)

            self.assertTrue(recorded.ok, recorded.error)
            self.assertEqual(recorded.value["event_type"], "commit")
            self.assertEqual(recorded.value["commit_sha"], sha)
            self.assertIs(recorded.value["recorded_late"], True)
            terminal = implement_runtime.mark_implementation_green(attempt)
            self.assertTrue(terminal.ok, terminal.error)
            self.assertEqual(terminal.value["commits"], [sha])

    def test_late_recording_refuses_a_commit_outside_the_branch_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.commit_without_recording(attempt)
            base = git(attempt.worktree, "rev-parse", "HEAD~1")

            result = implement_runtime.record_commit_late(attempt, "step-1", base)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "commit_not_in_history")

    def test_late_recording_refuses_a_commit_already_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            sha = complete_step_one(attempt)

            result = implement_runtime.record_commit_late(attempt, "step-1", sha)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "commit_already_recorded")

    def test_late_recording_verifies_the_commit_paths_against_the_write_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.prepare_green_change(attempt)
            (attempt.worktree / "outside.txt").write_text("outside\n", encoding="utf-8")
            git(attempt.worktree, "add", "outside.txt")
            git(attempt.worktree, "commit", "-m", "chore: outside change")
            sha = git(attempt.worktree, "rev-parse", "HEAD")

            result = implement_runtime.record_commit_late(attempt, "step-1", sha)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "write_scope_violation")

    def test_implementation_green_accepts_a_commit_recorded_after_a_later_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "test"))
            first = self.commit_without_recording(attempt)
            guide_oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "exists=Path('docs/guide.md').is_file(); "
                        "print('green' if exists else 'guide missing'); "
                        "sys.exit(0 if exists else 1)"
                    ),
                ]
            )
            guide_oracle["step_id"] = "step-2"
            guide_oracle["failure_signature"] = "guide missing"
            self.assertTrue(implement_runtime.accept_red(attempt, guide_oracle).ok)
            guide = attempt.worktree / "docs/guide.md"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text("# Guide\n", encoding="utf-8")
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-2", "green").ok)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-2", "refactor").ok)
            self.assertTrue(implement_runtime.stage_paths(attempt, ["docs/guide.md"], step_id="step-2").ok)
            git(attempt.worktree, "commit", "-m", "docs: add guide")
            second = git(attempt.worktree, "rev-parse", "HEAD")
            self.assertTrue(implement_runtime.record_commit(attempt, "step-2", first).ok)
            self.assertTrue(implement_runtime.record_commit_late(attempt, "step-1", first).ok)

            terminal = implement_runtime.mark_implementation_green(attempt)

            self.assertTrue(terminal.ok, terminal.error)
            self.assertEqual(terminal.value["commits"], [first, second])

    def test_scope_violation_is_not_staged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            outside = attempt.worktree / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")

            result = implement_runtime.stage_paths(attempt, ["outside.txt"], step_id="step-1")

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

            result = implement_runtime.stage_paths(
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
            production.write_text("API_TO" + "KEN=not-a-real-token\n", encoding="utf-8")

            result = implement_runtime.stage_paths(
                attempt,
                ["src/greeting.py"],
                step_id="step-1",
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "secret_detected")
            self.assertEqual(git(attempt.worktree, "diff", "--cached", "--name-only"), "")


class SecretDetectionJudgmentTest(unittest.TestCase):
    """The staging scan rejects credential-looking values, not credential-looking names."""

    # Rejected fixtures are assembled by concatenation: stage scans this file's whole
    # bytes when it is ever staged, and a literal credential-shaped fixture here would
    # block every future commit touching this file.
    PASSWORD_QUOTED_FIXTURE = "pass" + 'word = "hunter2"\n'
    API_KEY_QUOTED_FIXTURE = "api" + "_key: 'sk-abc123'\n"
    ENV_TOKEN_BARE_FIXTURE = "API_TO" + "KEN=abc123def456\n"

    ORDINARY_CODE = (
        "secret = _first_secret_field(value)\n"
        "token = other_variable\n"
        "password: str\n"
        "token = os.environ\n"
    )

    def _stage_content(self, attempt, content: str):
        production = attempt.worktree / "src/greeting.py"
        production.parent.mkdir(parents=True, exist_ok=True)
        production.write_text(content, encoding="utf-8")
        return implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1")

    def test_assignments_of_calls_identifiers_and_annotations_stage_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.assertTrue(implement_runtime.accept_red(attempt, red_oracle(GREETING_ORACLE_COMMAND)).ok)
            result = self._stage_content(attempt, self.ORDINARY_CODE)
            self.assertTrue(result.ok, result.error)

    def test_quoted_credential_values_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            for content in (self.PASSWORD_QUOTED_FIXTURE, self.API_KEY_QUOTED_FIXTURE):
                result = self._stage_content(attempt, content)
                self.assertFalse(result.ok)
                self.assertEqual(result.error.code, "secret_detected")

    def test_bare_values_mixing_letters_and_digits_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            result = self._stage_content(attempt, self.ENV_TOKEN_BARE_FIXTURE)
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "secret_detected")

    def test_a_diff_removing_a_credential_like_code_line_stages_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            self.assertTrue(implement_runtime.accept_red(attempt, red_oracle(GREETING_ORACLE_COMMAND)).ok)
            production = attempt.worktree / "src/greeting.py"
            production.parent.mkdir(parents=True)
            production.write_text(self.ORDINARY_CODE, encoding="utf-8")
            git(attempt.worktree, "add", "src/greeting.py")
            git(attempt.worktree, "commit", "-m", "fixture: ordinary code")
            production.write_text("def greeting():\n    return 'hello'\n", encoding="utf-8")
            result = implement_runtime.stage_paths(attempt, ["src/greeting.py"], step_id="step-1")
            self.assertTrue(result.ok, result.error)


class MultiStepFreezeTest(unittest.TestCase):
    def test_a_later_step_may_evolve_an_earlier_steps_test_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _, _ = create_repository(Path(directory), step_kinds=("test", "test"))
            resolved = implement_runtime.resolve_plan(root).value
            attempt = implement_runtime.bootstrap_attempt(
                root,
                resolved,
                worktree_path=Path(directory) / "linked-worktree",
                attempt_id_factory=lambda: "20260824t210000-c3d4e5f6",
                executor={
                    "executor": "codex",
                    "backend": "unavailable",
                    "session_id": "unavailable",
                    "reason": "not exposed safely",
                },
            ).value
            complete_step_one(attempt)

            # Step 2 legitimately grows the same test file step 1 froze.
            target = attempt.worktree / "tests/greeting_test.py"
            target.write_text(target.read_text(encoding="utf-8") + "# second behavior\n", encoding="utf-8")
            oracle = red_oracle(
                [
                    "python3",
                    "-c",
                    (
                        "from pathlib import Path; import sys; "
                        "grown='farewell' in Path('src/greeting.py').read_text(); "
                        "print('green' if grown else 'greeting missing'); "
                        "sys.exit(0 if grown else 1)"
                    ),
                ]
            )
            oracle["step_id"] = "step-2"
            self.assertTrue(implement_runtime.accept_red(attempt, oracle).ok)
            production = attempt.worktree / "src/greeting.py"
            production.write_text(
                production.read_text(encoding="utf-8") + "def farewell():\n    return 'bye'\n",
                encoding="utf-8",
            )
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-2", "green").ok)
            self.assertTrue(implement_runtime.run_frozen_oracle(attempt, "step-2", "refactor").ok)
            self.assertTrue(
                implement_runtime.stage_paths(
                    attempt, ["src/greeting.py", "tests/greeting_test.py"], step_id="step-2"
                ).ok
            )
            previous_head = git(attempt.worktree, "rev-parse", "HEAD")
            git(attempt.worktree, "commit", "-m", "feat: add farewell")
            self.assertTrue(implement_runtime.record_commit(attempt, "step-2", previous_head).ok)

            terminal = implement_runtime.mark_implementation_green(attempt)
            self.assertTrue(terminal.ok, terminal.error)


class VendoredEntrySmokeTest(unittest.TestCase):
    """The vendored copy has its own import graph; byte-identity alone does not prove it loads."""

    def test_the_vendored_copy_resolves_its_modules_and_answers_help(self) -> None:
        entry = ROOT / "skills/ba0918-implement/scripts/implement_runtime.py"
        completed = subprocess.run(
            [sys.executable, str(entry), "--help"], capture_output=True, text=True
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class InstructionContractTest(unittest.TestCase):
    def test_instructions_describe_the_current_runtime_boundaries(self) -> None:
        skill_root = ROOT / "skills/ba0918-implement"
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
            exit_code = implement_runtime.main(arguments)
        return exit_code, json.loads(output.getvalue())

    def test_attempt_id_generation_is_path_safe_and_injectable(self) -> None:
        attempt_id = implement_runtime.generate_attempt_id(
            now=lambda: "20260822t160000",
            random_suffix=lambda: "a1b2c3d4",
        )

        self.assertEqual(attempt_id, "20260822t160000-a1b2c3d4")
        self.assertIsNotNone(implement_runtime.execution_model.ATTEMPT_ID.fullmatch(attempt_id))

    def test_help_lists_human_gate_commands_and_invalid_results_are_cli_errors(self) -> None:
        help_output = io.StringIO()
        with contextlib.redirect_stdout(help_output), self.assertRaises(SystemExit) as help_exit:
            implement_runtime.main(["--help"])

        error_output = io.StringIO()
        with contextlib.redirect_stderr(error_output), self.assertRaises(SystemExit) as error_exit:
            implement_runtime.main(
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
                exit_code = implement_runtime.main(["resolve", "--repo", str(root)])

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
                implement_runtime.record_human_gate(
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
                exit_code = implement_runtime.main(["resolve", "--repo", str(root)])

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

class RevisedPlanTest(unittest.TestCase):
    def test_a_revised_plan_still_lets_the_execution_be_loaded_and_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            revise_fixture_plan(root, attempt.plan_id)

            loaded = implement_runtime.load_current_attempt(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
            )
            self.assertIsNone(loaded.error)

            context = implement_runtime.validate_context(loaded.value, step_id="step-1")
            self.assertEqual(context.error.code, "plan_identity_drift")

            stopped = implement_runtime.append_event(
                loaded.value, "stopped", {"reason": "plan_revised", "step_id": "step-1"}
            )
            self.assertTrue(stopped.ok, stopped.error)
            self.assertEqual(stopped.value["event_type"], "stopped")

    def test_residual_reports_whether_a_drifted_execution_can_be_rebound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            revise_fixture_plan(root, attempt.plan_id)

            facts = implement_runtime.residual_executions(root, plan_id=attempt.plan_id).value[0]
            self.assertFalse(facts["resumable"]["ok"])
            self.assertTrue(facts["rebindable"]["ok"], facts["rebindable"])

            (root / f".agents/artifacts/plans/{attempt.plan_id}_fixture.md").unlink()
            facts = implement_runtime.residual_executions(root, plan_id=attempt.plan_id).value[0]
            self.assertFalse(facts["rebindable"]["ok"])
            self.assertIn("no longer readable", facts["rebindable"]["reason"])

    def test_context_after_a_rebound_checks_the_revised_plan_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            revised = revise_fixture_plan(root, attempt.plan_id)
            binding = json.loads(attempt.binding_path.read_text(encoding="utf-8"))
            rebound = implement_runtime.append_event(
                attempt,
                "rebound",
                {
                    "plan": {
                        "id": attempt.plan_id,
                        "path": revised.path,
                        "revision": 2,
                        "content_identity": revised.content_identity,
                    },
                    "specs": binding["specs"],
                    "write_scope": ["src"],
                    "human_gates": [],
                    "step_map": [
                        {"step_id": "step-1", "previous_step_id": "step-1", "disposition": "continue"},
                        {"step_id": "step-2", "previous_step_id": None, "disposition": "new"},
                    ],
                    "superseded_steps": [],
                    "head": git(attempt.worktree, "rev-parse", "HEAD"),
                    "extra_commits": [],
                    "uncommitted_changes": False,
                },
            )
            self.assertTrue(rebound.ok, rebound.error)

            context = implement_runtime.validate_context(attempt, step_id="step-2")
            self.assertTrue(context.ok, context.error)
            self.assertEqual(context.value["plan"]["revision"], 2)
            (attempt.worktree / "tests/greeting_test.py").write_text("# changed\n", encoding="utf-8")
            staged = implement_runtime.stage_paths(attempt, ["tests/greeting_test.py"], step_id="step-1")
            self.assertFalse(staged.ok)
            self.assertEqual(staged.error.code, "write_scope_violation")

    def test_a_rebound_uses_the_revised_human_gate_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), human_gate=True, human_gate_timing="before_edit")
            revised = revise_fixture_plan(root, attempt.plan_id)
            binding = json.loads(attempt.binding_path.read_text(encoding="utf-8"))
            rebound = implement_runtime.append_event(
                attempt,
                "rebound",
                {
                    "plan": {
                        "id": attempt.plan_id,
                        "path": revised.path,
                        "revision": 2,
                        "content_identity": revised.content_identity,
                    },
                    "specs": binding["specs"],
                    "write_scope": binding["write_scope"],
                    "human_gates": [],
                    "step_map": [
                        {"step_id": "step-1", "previous_step_id": "step-1", "disposition": "continue"},
                        {"step_id": "step-2", "previous_step_id": None, "disposition": "new"},
                    ],
                    "superseded_steps": [],
                    "head": git(attempt.worktree, "rev-parse", "HEAD"),
                    "extra_commits": [],
                    "uncommitted_changes": False,
                },
            )
            self.assertTrue(rebound.ok, rebound.error)

            result = implement_runtime.record_human_gate(
                attempt, step_id="step-1", gate_id="approve-greeting", result="approved"
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "human_gate_undeclared")
            self.assertTrue(implement_runtime.check_human_gates(attempt, step_id="step-1", timing="before_edit").ok)


class CheckStepTest(unittest.TestCase):
    @staticmethod
    def _change_a_file_in_scope(attempt) -> str:
        target = attempt.worktree / "docs/guide.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("配布の複製についての手引き\n", encoding="utf-8")
        return "docs/guide.md"

    def test_a_check_step_runs_the_commands_the_plan_declared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "check"))
            complete_step_one(attempt)
            changed = self._change_a_file_in_scope(attempt)

            result = implement_runtime.record_check(attempt, step_id="step-2")

            self.assertTrue(result.ok, result.error)
            self.assertEqual(
                [check["command"] for check in result.value["checks"]],
                [["python3", "-c", "pass"]],
            )
            self.assertEqual([entry["path"] for entry in result.value["files"]], [changed])

    def test_a_check_step_records_nothing_when_a_declared_command_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(
                Path(directory), step_kinds=("test", "check"), check_commands=(FAILING_CHECK,)
            )
            complete_step_one(attempt)
            before = sorted(path.name for path in attempt.evidence_path.glob("0*.json"))

            result = implement_runtime.record_check(attempt, step_id="step-2")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "check_failed")
            self.assertEqual(sorted(path.name for path in attempt.evidence_path.glob("0*.json")), before)

    def test_a_check_step_refuses_a_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "check"))
            complete_step_one(attempt)
            self._change_a_file_in_scope(attempt)
            self.assertTrue(implement_runtime.record_check(attempt, step_id="step-2").ok)

            result = implement_runtime.record_approval(attempt, step_id="step-2", result="approved")

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "completion_kind_mismatch")

    def test_a_step_only_the_revised_plan_has_can_record_its_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test",))
            complete_step_one(attempt)
            append_check_step(root, attempt.plan_id)
            self.assertTrue(
                implement_runtime.resume.rebind_execution(
                    root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id
                ).ok
            )
            self._change_a_file_in_scope(attempt)

            result = implement_runtime.record_check(attempt, step_id="step-2")

            self.assertTrue(result.ok, result.error)


def append_check_step(root: Path, plan_id: str):
    """Revision 2 of a one-step fixture: a check step the first revision does not have."""
    current = plan_artifact.read_registered_plan(root, None)
    revised = current.text.replace("**Plan revision:** `1`", "**Plan revision:** `2`")
    revised += "\n### 2. 複製を作り直す\n\n**Completion:** check\n" + declared_checks((PASSING_CHECK,))
    publish_text(
        root,
        plan_id=plan_id,
        revision=2,
        relative_path=f".agents/artifacts/plans/{plan_id}_fixture-r2.md",
        text=revised,
        approved_identity=plan_artifact.content_identity(revised),
        switch_confirmed=False,
    )
    return plan_artifact.read_registered_plan(root, None)


def revise_three_step_plan(root: Path, plan_id: str):
    """Revision 2 of a three-step fixture: step 2 reworded, a step inserted, old step 3 kept, one appended."""
    current = plan_artifact.read_registered_plan(root, None)
    revised = current.text.replace("**Plan revision:** `1`", "**Plan revision:** `2`")
    revised = revised.replace(
        "### 2. 手順 2\n\n**Completion:** test\n",
        "### 2. 手順 2（書き直した）\n\n**Completion:** test\n\n### 3. 挿入した手順\n\n**Completion:** test\n",
    )
    revised = revised.replace("### 3. 手順 3\n", "### 4. 手順 3\n")
    revised += "\n### 5. 新しい手順\n\n**Completion:** test\n"
    publish_text(
        root,
        plan_id=plan_id,
        revision=2,
        relative_path=f".agents/artifacts/plans/{plan_id}_fixture-r2.md",
        text=revised,
        approved_identity=plan_artifact.content_identity(revised),
        switch_confirmed=False,
    )
    return plan_artifact.read_registered_plan(root, None)


class RebindTest(unittest.TestCase):
    def test_rebind_preview_matches_steps_by_their_text_not_their_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "test", "test"))
            complete_step_one(attempt)
            revise_three_step_plan(root, attempt.plan_id)
            preview = getattr(implement_runtime.resume, "rebind_preview", None)
            self.assertIsNotNone(preview)

            result = preview(root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id)

            self.assertTrue(result.ok, result.error)
            table = result.value
            self.assertEqual(
                [(row["step_id"], row["disposition"], row["previous_step_id"]) for row in table["step_map"]],
                [
                    ("step-1", "carry", "step-1"),
                    ("step-2", "new", None),
                    ("step-3", "new", None),
                    ("step-4", "continue", "step-3"),
                    ("step-5", "new", None),
                ],
            )
            self.assertEqual(table["superseded_steps"], ["step-2"])
            self.assertEqual(table["next_step"], "step-2")
            self.assertEqual(table["plan"]["revision"], 2)

    def test_rebind_preview_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "test", "test"))
            revise_three_step_plan(root, attempt.plan_id)
            before = sorted(path.name for path in attempt.evidence_path.glob("0*.json"))

            self.assertTrue(implement_runtime.resume.rebind_preview(root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id).ok)

            self.assertEqual(sorted(path.name for path in attempt.evidence_path.glob("0*.json")), before)

    def test_rebind_records_the_rebound_event_and_continues_from_the_first_uncarried_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "test", "test"))
            complete_step_one(attempt)
            (attempt.worktree / "notes.md").write_text("outside the evidence\n", encoding="utf-8")
            git(attempt.worktree, "add", "notes.md")
            git(attempt.worktree, "commit", "-m", "chore: unrecorded note")
            unrecorded = git(attempt.worktree, "rev-parse", "HEAD")
            revised = revise_three_step_plan(root, attempt.plan_id)

            result = implement_runtime.resume.rebind_execution(root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id)

            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value["next_step"], "step-2")
            self.assertFalse(result.value["redo"])
            events = implement_runtime._load_events(attempt).value
            self.assertEqual(events[-1]["event_type"], "rebound")
            self.assertEqual(events[-1]["plan"]["content_identity"], revised.content_identity)
            self.assertEqual(events[-1]["extra_commits"], [unrecorded])
            effective = implement_runtime.execution_model.effective_events(events)
            self.assertTrue(implement_runtime.execution_model.validate_step_evidence(effective, "step-1", "test").ok)
            context = implement_runtime.validate_context(attempt, step_id="step-4")
            self.assertTrue(context.ok, context.error)
            self.assertEqual(context.value["plan"]["revision"], 2)
            facts = implement_runtime.residual_executions(root, plan_id=attempt.plan_id).value[0]
            self.assertTrue(facts["resumable"]["ok"], facts["resumable"])
            self.assertEqual([commit["sha"] for commit in facts["branch"]["extra_commits"]], [unrecorded])

    def test_rebind_refuses_another_plan_and_a_missing_previous_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "test", "test"))
            other_text = plan_artifact.read_registered_plan(root, None).text.replace("20260822150000", "20260822150001")
            publish_text(
                root,
                plan_id="20260822150001",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822150001_other.md",
                text=other_text,
                approved_identity=plan_artifact.content_identity(other_text),
                switch_confirmed=True,
            )
            before = sorted(path.name for path in attempt.evidence_path.glob("0*.json"))

            other = implement_runtime.resume.rebind_execution(root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id)
            self.assertFalse(other.ok)
            self.assertEqual(other.error.code, "rebind_target_invalid")

            unregistered = implement_runtime.resume.rebind_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id, plan_path=".agents/artifacts/plans/nowhere.md"
            )
            self.assertFalse(unregistered.ok)
            self.assertEqual(unregistered.error.code, "rebind_target_invalid")

            (root / f".agents/artifacts/plans/{attempt.plan_id}_fixture.md").unlink()
            missing = implement_runtime.resume.rebind_execution(
                root, plan_id=attempt.plan_id, attempt_id=attempt.attempt_id, plan_path=".agents/artifacts/plans/20260822150001_other.md"
            )
            self.assertFalse(missing.ok)
            self.assertEqual(sorted(path.name for path in attempt.evidence_path.glob("0*.json")), before)

    def test_rebind_command_prints_the_table_and_records_only_with_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory), step_kinds=("test", "test", "test"))
            revise_three_step_plan(root, attempt.plan_id)
            common = ["rebind", "--repo", str(root), "--plan-id", attempt.plan_id, "--execution-id", attempt.attempt_id]

            with contextlib.redirect_stdout(io.StringIO()) as preview:
                self.assertEqual(implement_runtime.main(common), 0)
            self.assertIn("step_map", json.loads(preview.getvalue()))
            self.assertEqual(len(list(attempt.evidence_path.glob("0*.json"))), 1)

            with contextlib.redirect_stdout(io.StringIO()) as recorded:
                self.assertEqual(implement_runtime.main(common + ["--confirm"]), 0)
            self.assertEqual(json.loads(recorded.getvalue())["next_step"], "step-1")
            self.assertEqual(len(list(attempt.evidence_path.glob("0*.json"))), 2)


def commit_outside_the_evidence(attempt, name: str = "notes.md") -> str:
    (attempt.worktree / name).write_text("outside the evidence\n", encoding="utf-8")
    git(attempt.worktree, "add", name)
    git(attempt.worktree, "commit", "-m", f"chore: unrecorded {name}")
    return git(attempt.worktree, "rev-parse", "HEAD")


class HistoryApprovalTest(unittest.TestCase):
    def test_terminal_lists_an_unexplained_commit_and_waits_for_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            complete_step_one(attempt)
            commit_outside_the_evidence(attempt)

            result = implement_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "history_approval_required")
            events = implement_runtime._load_events(attempt).value
            self.assertEqual(events[-1]["event_type"], "commit")

    def test_history_approval_lets_the_terminal_finish_with_every_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            recorded = complete_step_one(attempt)
            unrecorded = commit_outside_the_evidence(attempt)

            approved = implement_runtime.cli.approve_history(attempt, reason="前セッションのメモ")
            self.assertTrue(approved.ok, approved.error)
            self.assertEqual(approved.value["event_type"], "history_approved")
            self.assertEqual(approved.value["unexplained_commits"], [unrecorded])
            self.assertEqual(approved.value["out_of_scope_paths"], ["notes.md"])
            self.assertEqual(approved.value["reason"], "前セッションのメモ")

            terminal = implement_runtime.mark_implementation_green(attempt)
            self.assertTrue(terminal.ok, terminal.error)
            self.assertEqual(terminal.value["commits"], [recorded, unrecorded])

    def test_a_history_approval_is_not_reused_after_the_history_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            complete_step_one(attempt)
            commit_outside_the_evidence(attempt)
            self.assertTrue(implement_runtime.cli.approve_history(attempt).ok)
            commit_outside_the_evidence(attempt, "more.md")

            result = implement_runtime.mark_implementation_green(attempt)

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "history_approval_required")

    def test_out_of_scope_uncommitted_changes_are_listed_not_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            complete_step_one(attempt)
            (attempt.worktree / "outside.txt").write_text("outside\n", encoding="utf-8")

            result = implement_runtime.mark_implementation_green(attempt)
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "history_approval_required")

            approved = implement_runtime.cli.approve_history(attempt)
            self.assertTrue(approved.ok, approved.error)
            self.assertEqual(approved.value["uncommitted_out_of_scope"], ["outside.txt"])
            self.assertTrue(implement_runtime.mark_implementation_green(attempt).ok)

    def test_nothing_to_approve_is_refused_and_a_clean_history_needs_no_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, attempt = bootstrap_fixture(Path(directory))
            complete_step_one(attempt)

            refused = implement_runtime.cli.approve_history(attempt)
            self.assertFalse(refused.ok)
            self.assertEqual(refused.error.code, "history_approval_unnecessary")
            self.assertTrue(implement_runtime.mark_implementation_green(attempt).ok)

    def test_approve_history_command_records_the_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, attempt = bootstrap_fixture(Path(directory))
            complete_step_one(attempt)
            commit_outside_the_evidence(attempt)

            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = implement_runtime.main(
                    ["approve-history", "--repo", str(root), "--reason", "意図した直し"]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.getvalue())["event_type"], "history_approved")


if __name__ == "__main__":
    unittest.main()
