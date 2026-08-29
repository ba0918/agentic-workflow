from pathlib import Path
import inspect
import json
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime import deps
from runtime import (
    context, deliverables, events, evidence as runtime_evidence, gates, repository,
    secret_detect, storage, tdd,
)
from runtime.types import JsonObject, ResolvedPlan, Run, object_value, object_values

def resolved_plan(
    approval: str, *, expected_paths: tuple[str, ...] = (),
    steps: tuple[JsonObject, ...] = ({"id": "1", "completion": "check"},),
) -> ResolvedPlan:
    normalized_steps = tuple({
        **step,
        "checks": step.get("checks", ("lint",)) if step.get("completion") == "check" else (),
    } for step in steps)
    return ResolvedPlan(
        "plan-a", "docs/plans/plan-a.md", approval, "text", (), expected_paths, steps=normalized_steps,
    )

def approved_plan_text(
    step_id: str = "1", completion: str = "check", scope: str | None = "app.txt",
) -> str:
    checks = "\n**Checks:**\n\n- `lint`\n" if completion == "check" else ""
    scope_block = f"## Scope\n\n```text\n{scope}\n```\n\n" if scope is not None else ""
    return (
        "# Plan\n\n**Verification coverage:**\n\n"
        f"- `docs/spec/a.md` / `Contract` -> `{step_id}:{completion}`\n\n"
        f"{scope_block}"
        f"## Step {step_id}: Implement\n{checks}"
    )


def rebound_fixture(root: Path) -> tuple[Run, str]:
    """A bound run whose plan is then revised; returns the run and the revision commit."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
    (root / "docs/spec").mkdir(parents=True)
    (root / "docs/plans").mkdir(parents=True)
    (root / "docs/spec/a.md").write_text("# Contract\n", encoding="utf-8")
    (root / "docs/plans/plan-a.md").write_text(approved_plan_text(), encoding="utf-8")
    (root / "app.txt").write_text("base\n", encoding="utf-8")
    (root / "lib.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", ".gitignore", "docs", "app.txt", "lib.txt"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "approval"], check=True)
    approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
    plan = resolved_plan(approval, expected_paths=("app.txt",), steps=({"id": "1", "completion": "check"},))
    run = repository.bind_run(
        root, plan, run_id="run-1", delegated=False, branch="main", worktree=str(root),
    ).required()
    return run, approval


def commit_plan_revision(root: Path, plan_text: str) -> str:
    (root / "docs/plans/plan-a.md").write_text(plan_text, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "docs/plans/plan-a.md"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "approved revision"], check=True)
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()

class ImplementDistributionTest(unittest.TestCase):
    def test_plan_reader_is_loaded_from_the_same_distribution(self) -> None:
        self.assertTrue(deps.PLAN_READER_PATH.is_file())
        self.assertEqual(deps.plan_artifact.PLAN_STORE.as_posix(), "docs/plans")

    def test_run_binds_to_approval_commit_under_agents_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan("a" * 40, expected_paths=("src/app.py",))
            result = repository.bind_run(root, plan, run_id="run-1", delegated=True)
            self.assertTrue(result.ok, result.error)
            run = result.required()
            self.assertEqual(run.evidence_path.relative_to(root).as_posix(), ".agents/evidence/plan-a/run-1")
            binding = storage.read_json(run.binding_path)
            self.assertEqual(binding.required()["approval_commit"], "a" * 40)
            steps = object_values(binding.required().get("steps"))
            if not steps:
                self.fail("binding steps are unavailable")
            self.assertEqual(steps[0].get("checks"), ["lint"])
            self.assertNotIn("identity", str(binding.required()))

    def test_bind_validates_every_contract_before_creation_and_cleans_failed_initial_event(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            branch = subprocess.run(
                ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True
            ).stdout.strip()
            approval = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
            ).stdout.strip()
            invalid_plan = resolved_plan(approval, steps=({"id": "1", "completion": "unknown"},))
            invalid = repository.bind_run(
                root, invalid_plan, run_id="run-1", delegated=False, branch=branch, worktree=str(root),
            )
            self.assertFalse(invalid.ok)
            self.assertFalse((root / ".agents/evidence/plan-a/run-1").exists())
            plan = resolved_plan(approval)
            with mock.patch("runtime.context.append_event", return_value=context.failure("write_failed", "failed")):
                failed = repository.bind_run(
                    root, plan, run_id="run-1", delegated=False,
                    branch=branch, worktree=str(root),
                )
            self.assertFalse(failed.ok)
            self.assertFalse((root / ".agents/evidence/plan-a/run-1").exists())
            retried = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                branch=branch, worktree=str(root),
            )
            self.assertTrue(retried.ok, retried.error)

    def test_events_are_numbered_append_only_without_a_hash_chain(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "docs/spec").mkdir(parents=True)
            (root / "docs/plans").mkdir(parents=True)
            (root / "docs/spec/a.md").write_text("# Contract\n", encoding="utf-8")
            (root / "docs/plans/plan-a.md").write_text(approved_plan_text(), encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "docs/spec/a.md", "docs/plans/plan-a.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "documents"], check=True)
            approval = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
            ).stdout.strip()
            plan = resolved_plan(approval)
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).required()
            first = context.append_event(run, "delegated", {"role": "implementer", "model": "claude-fable-5"})
            second = context.append_event(run, "returned", {"outcome": "completed"})
            self.assertTrue(first.ok and second.ok)
            names = [path.name for path in sorted(run.evidence_path.glob("*.json"))]
            self.assertEqual(names, ["000001-delegated.json", "000002-returned.json", "binding.json"])
            self.assertTrue((run.evidence_path / "current-status").is_file())
            self.assertNotIn("identity", second.required())
            with self.assertRaises(FileExistsError):
                event_path = first.required().get("path")
                if not isinstance(event_path, Path):
                    self.fail("event path is unavailable")
                storage.write_once(event_path, b"replacement")

    def test_direct_implementations_can_append_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan("a" * 40)
            run = repository.bind_run(root, plan, run_id="run-1", delegated=False).required()
            result = context.append_event(run, "human_gate", {"reason": "writer contract check"}, actor="implement")
            self.assertTrue(result.ok, result.error)
            blocked = context.append_event(run, "delegated", {"role": "implementer", "model": "claude-fable-5"}, actor="cycle")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.required_error().code, "writer_not_allowed")

    def test_cycle_cannot_write_implementation_evidence_during_delegation(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan("a" * 40)
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).required()
            self.assertTrue(context.append_event(run, "delegated", {"role": "implementer", "model": "claude-fable-5"}, actor="cycle").ok)
            blocked = context.append_event(run, "human_gate", {"reason": "not cycle evidence"}, actor="cycle")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.required_error().code, "writer_not_allowed")
            self.assertTrue(context.append_event(run, "human_gate", {"reason": "implement evidence"}, actor="implement").ok)
            wrong_boundary_writer = context.append_event(run, "returned", {}, actor="implement")
            self.assertFalse(wrong_boundary_writer.ok)
            self.assertEqual(wrong_boundary_writer.required_error().code, "writer_not_allowed")
            self.assertTrue(context.append_event(run, "returned", {"outcome": "returned"}, actor="cycle").ok)

    def test_delegated_implement_cannot_write_before_delegation_starts(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan("a" * 40)
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).required()
            blocked = context.append_event(run, "recovering", {"reason": "before delegation"}, actor="implement")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.required_error().code, "writer_not_allowed")

    def test_delegated_implement_cannot_write_after_delegation_finishes(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan("a" * 40)
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).required()
            self.assertTrue(context.append_event(run, "delegated", {"role": "implementer", "model": "claude-fable-5"}, actor="cycle").ok)
            self.assertTrue(context.append_event(run, "returned", {}, actor="cycle").ok)
            blocked = context.append_event(run, "recovering", {"reason": "after delegation"}, actor="implement")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.required_error().code, "writer_not_allowed")

    def test_implementation_green_cannot_be_appended_or_faked(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan("a" * 40, steps=({"id": "1", "completion": "test"},))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
            ).required()
            result = context.append_event(run, "implementation_green", {}, actor="implement")
            self.assertFalse(result.ok)
            self.assertEqual(result.required_error().code, "event_not_recordable")
            with self.assertRaises(TypeError):
                inspect.signature(context.append_event).bind(
                    run, "implementation_green", {}, actor="implement", _derived=True
                )

    def test_generic_append_cannot_record_commit_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan("a" * 40)
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
            ).required()
            result = context.append_event(run, "commit", {"step": "1", "commit": "b" * 40})
            self.assertFalse(result.ok)
            self.assertEqual(result.required_error().code, "event_not_recordable")

    def test_empty_run_and_invalid_test_transition_cannot_complete(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            empty = repository.bind_run(
                root, resolved_plan("a" * 40, steps=()), run_id="empty", delegated=False,
            )
            self.assertEqual(empty.required_error().code, "step_contract_invalid")
            (root / "tests").mkdir()
            (root / "tests/example_test.py").write_text("test bytes\n", encoding="utf-8")
            plan = resolved_plan("a" * 40, steps=({"id": "1", "completion": "test"},))
            run = repository.bind_run(
                root, plan, run_id="ordered", delegated=False,
            ).required()
            self.assertTrue(context.record_stage(
                run, "1", "red", context.StageObservation("test", 1, ["tests/example_test.py"]),
            ).ok)
            self.assertTrue(context.record_stage(
                run, "1", "green", context.StageObservation("test", 0),
            ).ok)
            self.assertTrue(context.record_stage(
                run, "1", "red", context.StageObservation("new test", 1, ["tests/example_test.py"]),
            ).ok)
            invalid = context.record_stage(
                run, "1", "refactor", context.StageObservation("new test", 0),
            )
            self.assertFalse(invalid.ok)
            self.assertEqual(invalid.required_error().code, "transition_invalid")

class ImplementLifecycleEvidenceTest(unittest.TestCase):
    def test_stopped_run_accepts_only_resume_or_rebound_and_status_tracks_rebound(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "docs/spec").mkdir(parents=True)
            (root / "docs/plans").mkdir(parents=True)
            (root / "docs/spec/a.md").write_text("# Contract\n", encoding="utf-8")
            (root / "docs/plans/plan-a.md").write_text(approved_plan_text(), encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "docs/spec/a.md", "docs/plans/plan-a.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "documents"], check=True)
            approval = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
            ).stdout.strip()
            plan = resolved_plan(approval)
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
            ).required()
            self.assertTrue(context.stop_run(run, "important decision").ok)
            blocked = context.append_event(
                run, "check", {"step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": []}
            )
            self.assertFalse(blocked.ok)
            rebound = context.rebound_run(
                run, approval, "approved revision", mappings=[{"old": "1", "new": "1"}],
            )
            self.assertTrue(rebound.ok, rebound.error)
            status = json.loads((run.evidence_path / "current-status").read_text(encoding="utf-8"))
            self.assertEqual(status["plan"]["approval_commit"], approval)

    def test_completion_is_derived_from_step_commit_safety_and_clean_worktree(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "README.md").write_text("fixture\n", encoding="utf-8")
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            (root / "tests").mkdir()
            test_path = root / "tests/example_test.py"
            test_path.write_text("test bytes\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md", ".gitignore", "tests/example_test.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            branch = subprocess.run(
                ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True
            ).stdout.strip()
            commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
            ).stdout.strip()
            plan = resolved_plan(
                commit, expected_paths=("README.md", ".gitignore", "tests/example_test.py"),
                steps=({"id": "1", "completion": "test"},),
            )
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=True, branch=branch, worktree=str(root),
            ).required()
            self.assertTrue(context.append_event(run, "delegated", {"role": "implementer", "model": "claude-fable-5"}, actor="cycle").ok)
            self.assertTrue(context.record_stage(
                run, "1", "red", context.StageObservation(
                    "test cmd", 1, ["tests/example_test.py"]
                ),
            ).ok)
            command_drift = context.record_stage(
                run, "1", "green", context.StageObservation("other cmd", 0),
            )
            self.assertEqual(command_drift.required_error().code, "frozen_red_mismatch")
            test_path.write_text("changed fixture\n", encoding="utf-8")
            fixture_drift = context.record_stage(
                run, "1", "green", context.StageObservation("test cmd", 0),
            )
            self.assertEqual(fixture_drift.required_error().code, "frozen_red_mismatch")
            test_path.write_text("test bytes\n", encoding="utf-8")
            self.assertTrue(context.record_stage(
                run, "1", "green", context.StageObservation("test cmd", 0),
            ).ok)
            self.assertTrue(context.record_stage(
                run, "1", "refactor", context.StageObservation("test cmd", 0),
            ).ok)
            (root / "README.md").write_text("implemented\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "implement"], check=True)
            implementation_commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
            ).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", implementation_commit).ok)
            completed = context.complete_run(run)
            self.assertTrue(completed.ok, completed.error)
            self.assertEqual(completed.required()["event_type"], "implementation_green")
            returned = context.append_event(run, "returned", {"outcome": "completed"}, actor="cycle")
            self.assertTrue(returned.ok, returned.error)
            status = json.loads((run.evidence_path / "current-status").read_text(encoding="utf-8"))
            self.assertEqual(status["completed_steps"], ["1"])
            self.assertEqual(status["last_event"]["event_type"], "returned")

    def test_human_gate_after_rebound_is_validated_against_the_original_history(self) -> None:
        import tempfile
        gate: JsonObject = {
            "gate_id": "approve-step",
            "sections": ["Contract"],
            "criterion": "Approved?",
            "target": {"kind": "files", "paths": ["app.txt"]},
            "timing": "before_implementation_green",
            "allowed_results": ["approved", "rejected"],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = resolved_plan(
                "a" * 40,
                steps=({
                    "id": "old", "completion": "check", "human_gates": (gate,),
                },),
            )
            run = repository.bind_run(root, plan, run_id="run-1", delegated=False).required()
            self.assertTrue(context.append_event(run, "check", {
                "step": "old", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            self.assertTrue(context.append_event(run, "rebound", {
                "approval_commit": "b" * 40,
                "steps": [{
                    "id": "new", "completion": "check", "checks": ["lint"],
                    "human_gates": [gate],
                }],
                "mappings": [{"old": "old", "new": "new"}],
                "reason": "approved revision",
            }).ok)
            self.assertTrue(context.append_event(run, "check", {
                "step": "new", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)

            result = runtime_evidence.record_human_gate(
                run, "new", "approve-step", "approved",
            )

            self.assertTrue(result.ok, result.error)

    def test_final_check_must_verify_the_current_branch_head(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
            plan = resolved_plan(commit, expected_paths=("app.txt",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False, branch=branch, worktree=str(root),
            ).required()
            checked = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            })
            self.assertTrue(checked.ok, checked.error)
            self.assertEqual(checked.required()["changed_paths"], [])
            self.assertNotIn("verified_commit", checked.required())

            (root / "app.txt").write_text("implemented\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "implement"], check=True)
            implementation = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", implementation).ok)

            stale = context.complete_run(run)
            self.assertFalse(stale.ok)
            self.assertEqual(stale.required_error().code, "final_verification_stale")

            rechecked = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            })
            self.assertTrue(rechecked.ok, rechecked.error)
            self.assertTrue(context.complete_run(run).ok)

    def test_final_check_must_follow_a_commit_with_the_same_changed_paths(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "-C", str(root), "branch", "--show-current"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            plan = resolved_plan(approval, expected_paths=("app.txt",))
            run = repository.bind_run(
                root,
                plan,
                run_id="run-1",
                delegated=False,
                branch=branch,
                worktree=str(root),
            ).required()
            (root / "app.txt").write_text("checked bytes\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            checked = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            })
            self.assertTrue(checked.ok, checked.error)
            self.assertNotIn("verified_commit", checked.required())
            (root / "app.txt").write_text("committed bytes\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "implement"], check=True)
            implementation = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", implementation).ok)

            stale = context.complete_run(run)
            self.assertFalse(stale.ok)
            self.assertEqual(stale.required_error().code, "final_verification_stale")
            rechecked = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            })
            self.assertTrue(rechecked.ok, rechecked.error)
            self.assertTrue(context.complete_run(run).ok)

    def test_check_requires_every_plan_command_in_declared_order(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "-C", str(root), "branch", "--show-current"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            plan = resolved_plan(approval, steps=({
                "id": "1", "completion": "check", "checks": ("first-check", "second-check"),
            },))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                branch=branch, worktree=str(root),
            ).required()

            partial = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "first-check", "exit_code": 0}], "paths": [],
            })
            reordered = context.append_event(run, "check", {
                "step": "1", "checks": [
                    {"command": "second-check", "exit_code": 0},
                    {"command": "first-check", "exit_code": 0},
                ], "paths": [],
            })
            complete = context.append_event(run, "check", {
                "step": "1", "checks": [
                    {"command": "first-check", "exit_code": 0},
                    {"command": "second-check", "exit_code": 0},
                ], "paths": [],
            })

            self.assertFalse(partial.ok)
            self.assertFalse(reordered.ok)
            self.assertTrue(complete.ok, complete.error)
            self.assertTrue(context.complete_run(run).ok)

    def test_existing_v2_check_contract_without_declared_commands_keeps_its_meaning(self) -> None:
        binding = {"version": 2, "delegated": False, "steps": [{"id": "1", "completion": "check"}]}

        result = events.validate_event(binding, [], events.EventCandidate("check", {
            "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            "changed_paths": [],
        }, "implement"))

        self.assertTrue(result.ok, result.error)

    def test_rebound_completion_matches_commits_with_their_revision_segments(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            (root / "docs/spec").mkdir(parents=True)
            (root / "docs/plans").mkdir(parents=True)
            (root / "docs/spec/a.md").write_text("# Contract\n", encoding="utf-8")
            (root / "docs/plans/plan-a.md").write_text(approved_plan_text(), encoding="utf-8")
            (root / "app.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore", "docs", "app.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "approval"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            plan = resolved_plan(
                approval, expected_paths=("app.txt",), steps=({"id": "1", "completion": "check"},),
            )
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False, branch="main", worktree=str(root),
            ).required()
            wording_run = repository.bind_run(
                root, plan, run_id="wording", delegated=False, branch="main", worktree=str(root),
            ).required()
            (root / "app.txt").write_text("done\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}],
            }).ok)
            self.assertTrue(context.append_event(wording_run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}],
            }).ok)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "implementation"], check=True)
            implementation = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", implementation).ok)
            self.assertTrue(context.record_commit(wording_run, "1", implementation).ok)
            (root / "docs/spec/a.md").write_text("# Contract\n\nClarified.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "docs/spec/a.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "approved revision"], check=True)
            revised = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            self.assertTrue(context.follow_documents(
                run, revised, ["docs/spec/a.md"], "wording-only revision",
            ).ok)
            self.assertTrue(context.follow_documents(
                wording_run, revised, ["docs/spec/a.md"], "wording-only revision",
            ).ok)
            status = json.loads((run.evidence_path / "current-status").read_text(encoding="utf-8"))
            self.assertEqual(status["plan"]["approval_commit"], revised)
            self.assertTrue(context.append_event(wording_run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            self.assertTrue(context.complete_run(wording_run).ok)
            self.assertTrue(context.rebound_run(
                run, revised, "approved revision", mappings=[{"old": "1", "new": "1"}],
            ).ok)
            last_event = context.load_events(run).required()[-1]
            steps = object_values(last_event.get("steps"))
            if not steps:
                self.fail("rebound steps are unavailable")
            self.assertEqual(steps[0].get("checks"), ["lint"])
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            completed = context.complete_run(run)
            self.assertTrue(completed.ok, completed.error)

    def test_rebound_records_the_revised_scope_and_safety_judges_against_it(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, _ = rebound_fixture(root)
            revised = commit_plan_revision(root, approved_plan_text(scope="lib.txt"))

            rebound = context.rebound_run(
                run, revised, "scope moved to lib", mappings=[{"old": "1", "new": "1"}],
            )
            self.assertTrue(rebound.ok, rebound.error)
            self.assertEqual(context.load_events(run).required()[-1].get("expected_paths"), ["lib.txt"])

            (root / "app.txt").write_text("changed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            old_scope_only = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}],
            })
            self.assertEqual(
                old_scope_only.error.code if old_scope_only.error is not None else None,
                "unplanned_reason_missing",
            )

            subprocess.run(["git", "-C", str(root), "restore", "--staged", "--worktree", "app.txt"], check=True)
            (root / "lib.txt").write_text("changed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "lib.txt"], check=True)
            new_scope = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}],
            })
            self.assertTrue(new_scope.ok, new_scope.error)

    def test_completion_treats_paths_outside_the_rebound_scope_as_outside_scope(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, _ = rebound_fixture(root)
            revised = commit_plan_revision(root, approved_plan_text(scope="lib.txt"))
            self.assertTrue(context.rebound_run(
                run, revised, "scope moved to lib", mappings=[{"old": "1", "new": "1"}],
            ).ok)
            (root / "lib.txt").write_text("changed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "lib.txt"], check=True)
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}],
            }).ok)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "implementation"], check=True)
            implementation = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", implementation).ok)
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            (root / "app.txt").write_text("left over\n", encoding="utf-8")

            completed = context.complete_run(run)

            self.assertTrue(completed.ok, completed.error)
            self.assertEqual(completed.required().get("uncommitted_outside_scope"), ["app.txt"])

    def test_document_follow_rejects_a_commit_whose_plan_scope_differs_from_the_approval(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, _ = rebound_fixture(root)
            revised = commit_plan_revision(root, approved_plan_text(scope="lib.txt"))

            result = context.follow_documents(
                run, revised, ["docs/plans/plan-a.md"], "wording-only revision",
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.required_error().code, "rebound_or_new_run_required")
            self.assertEqual(len(context.load_events(run).required()), 1)

    def test_document_follow_accepts_a_plan_wording_change_that_keeps_the_scope(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, _ = rebound_fixture(root)
            reworded = approved_plan_text().replace("# Plan\n\n", "# Plan\n\nClarified wording.\n\n")
            revised = commit_plan_revision(root, reworded)

            result = context.follow_documents(
                run, revised, ["docs/plans/plan-a.md"], "wording-only revision",
            )

            self.assertTrue(result.ok, result.error)
            self.assertEqual(
                context.load_events(run).required()[-1].get("event_type"), "recovering",
            )

    def test_rebound_rejects_a_plan_whose_scope_cannot_be_read(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, _ = rebound_fixture(root)
            revised = commit_plan_revision(root, approved_plan_text(scope=None))

            rebound = context.rebound_run(
                run, revised, "scope missing", mappings=[{"old": "1", "new": "1"}],
            )

            self.assertEqual(
                rebound.error.code if rebound.error is not None else None, "document_commit_invalid",
            )

class ImplementSafetyEvidenceTest(unittest.TestCase):
    def test_document_follow_rejects_a_duplicate_specification_heading(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            (root / "docs/spec").mkdir(parents=True)
            (root / "docs/plans").mkdir(parents=True)
            (root / "docs/spec/a.md").write_text("# Contract\n", encoding="utf-8")
            (root / "docs/plans/plan-a.md").write_text(approved_plan_text(), encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore", "docs"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "approval"], check=True)
            approval = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            run = repository.bind_run(
                root, resolved_plan(approval), run_id="run-1", delegated=False,
                branch="main", worktree=str(root),
            ).required()
            (root / "docs/spec/a.md").write_text(
                "# Contract\n\n## Contract\n", encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(root), "add", "docs/spec/a.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "duplicate heading"], check=True)
            revised = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()

            result = context.follow_documents(
                run, revised, ["docs/spec/a.md"], "wording-only revision",
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.required_error().code, "document_commit_invalid")

    def test_dangerous_commit_path_cannot_be_recorded_or_completed(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
            plan = resolved_plan(approval, expected_paths=(".env.production",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False, branch=branch, worktree=str(root),
            ).required()
            (root / ".env.production").write_text("SECRET=value\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "-f", ".env.production"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "dangerous"], check=True)
            dangerous = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [".env.production"],
            })
            recorded = context.record_commit(run, "1", dangerous)
            self.assertFalse(recorded.ok)
            self.assertEqual(recorded.required_error().code, "dangerous_path")
            self.assertFalse(context.complete_run(run).ok)

    def test_secret_shaped_content_is_rejected_without_exposing_its_value(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
            plan = resolved_plan(approval, expected_paths=("config.py",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False, branch=branch, worktree=str(root),
            ).required()
            for name in ("api_token", "TOKEN", "Secret", "CREDENTIAL"):
                with self.subTest(name=name):
                    fake_value = f"fake_{name.lower()}_value_123456789"
                    (root / "config.py").write_text(f"{name}={fake_value}\n", encoding="utf-8")
                    subprocess.run(["git", "-C", str(root), "add", "config.py"], check=True)
                    rejected = context.append_event(run, "check", {
                        "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": ["config.py"],
                    })
                    self.assertFalse(rejected.ok)
                    self.assertEqual(rejected.required_error().code, "secret_content")
                    self.assertNotIn(fake_value, str(rejected.error))

    def test_secret_detector_covers_credentials_and_private_key_headers(self) -> None:
        for assignment in (
            b"Api-Token=fake_api_token_value",
            b"TOKEN: fake_standalone_token",
            b"secret = fake_secret_value",
            b"CREDENTIAL=fake_credential_value",
            b"password=fake_password_value",
        ):
            with self.subTest(assignment=assignment.split(b"=", 1)[0]):
                self.assertTrue(secret_detect.contains_secret(assignment))
        self.assertTrue(secret_detect.contains_secret(b"-----BEGIN FAKE PRIVATE KEY-----\nnot-a-key"))
        self.assertFalse(secret_detect.contains_secret(b"password = os.environ['PASSWORD']"))

    def test_secret_content_in_commit_object_is_rejected_without_value_exposure(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            plan = resolved_plan(approval, expected_paths=("config.py",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False, branch="main", worktree=str(root),
            ).required()
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            fake_value = "fake_commit_token_123456789"
            (root / "config.py").write_text(f"TOKEN={fake_value}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "config.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "candidate"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            rejected = context.record_commit(run, "1", commit)
            self.assertFalse(rejected.ok)
            self.assertEqual(rejected.required_error().code, "secret_content")
            self.assertNotIn(fake_value, str(rejected.error))
            evidence = "".join(path.read_text(encoding="utf-8") for path in run.evidence_path.glob("*.json"))
            self.assertNotIn(fake_value, evidence)

    def test_record_commit_rejects_side_branch_and_duplicate_step_assignment(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            plan = resolved_plan(
                approval, expected_paths=("app.txt",), steps=(
                    {"id": "1", "completion": "check"}, {"id": "2", "completion": "check"},
                ),
            )
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                branch="main", worktree=str(root),
            ).required()
            subprocess.run(["git", "-C", str(root), "switch", "-qc", "side"], check=True)
            (root / "app.txt").write_text("side\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "side"], check=True)
            side = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            subprocess.run(["git", "-C", str(root), "switch", "-q", "main"], check=True)
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            rejected = context.record_commit(run, "1", side)
            self.assertEqual(rejected.required_error().code, "commit_not_on_branch")
            (root / "app.txt").write_text("main\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "main change"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", commit).ok)
            self.assertTrue(context.append_event(run, "check", {
                "step": "2", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            duplicate = context.record_commit(run, "2", commit)
            self.assertEqual(duplicate.required_error().code, "commit_already_recorded")

    def test_red_test_snapshot_freezes_files_and_command(self) -> None:
        snapshot = tdd.freeze_test(
            {"tests/example_test.py": b"test bytes"},
            command="python3 -m unittest tests.example_test",
        )
        files = object_value(snapshot.get("files"))
        command = snapshot.get("command")
        digest = files.get("tests/example_test.py") if files is not None else None
        if not isinstance(digest, str) or not isinstance(command, str):
            self.fail("test snapshot is invalid")
        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(command, r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(tdd.frozen_test_matches(
            snapshot,
            {"tests/example_test.py": b"test bytes"},
            command="python3 -m unittest discover",
        ))

    def test_artifact_and_external_results_are_evidence_not_human_approvals(self) -> None:
        artifact = deliverables.artifact_event("2", ["docs/guide.md"], [{"command": "lint", "exit_code": 0}])
        external = deliverables.external_event("3", "device smoke test", "passed")
        self.assertEqual(artifact["event_type"], "artifact")
        self.assertEqual(external["event_type"], "external")
        self.assertNotIn("approval", artifact)
        self.assertNotIn("approval", external)

    def test_human_gates_accept_only_exception_boundaries(self) -> None:
        for kind in ("irreversible", "human_permission", "dangerous_target"):
            self.assertTrue(gates.validate_gate({"kind": kind, "reason": "needed"}).ok)
        for kind in ("artifact", "external", "step_commit", "history"):
            result = gates.validate_gate({"kind": kind, "reason": "ritual"})
            self.assertFalse(result.ok)
            self.assertEqual(result.required_error().code, "human_gate_not_allowed")

    def test_recovery_escalates_only_after_diagnosis_and_one_changed_method(self) -> None:
        self.assertEqual(gates.recovery_action(diagnosed=False, method_changed=False, still_stuck=True), "diagnose")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=False, still_stuck=True), "change_method")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=True, still_stuck=True), "human_judgment")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=True, still_stuck=False), "continue")

if __name__ == "__main__":
    unittest.main()
