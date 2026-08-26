from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime import deps
from runtime import context, deliverables, gates, repository, storage, tdd
from runtime.types import ResolvedPlan

class ImplementDistributionTest(unittest.TestCase):
    def test_plan_reader_is_loaded_from_the_same_distribution(self) -> None:
        self.assertTrue(deps.PLAN_READER_PATH.is_file())
        self.assertEqual(deps.plan_artifact.PLAN_STORE.as_posix(), "docs/plans")

    def test_run_binds_to_approval_commit_under_agents_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ("src/app.py",))
            result = repository.bind_run(root, plan, run_id="run-1", delegated=True)
            self.assertTrue(result.ok, result.error)
            run = result.value
            self.assertEqual(run.evidence_path.relative_to(root).as_posix(), ".agents/evidence/plan-a/run-1")
            binding = storage.read_json(run.binding_path)
            self.assertEqual(binding.value["approval_commit"], "a" * 40)
            self.assertNotIn("identity", str(binding.value))

    def test_events_are_numbered_append_only_without_a_hash_chain(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).value
            first = context.append_event(run, "delegation-started", {"role": "implementer"})
            second = context.append_event(run, "delegation-finished", {"outcome": "completed"})
            self.assertTrue(first.ok and second.ok)
            names = [path.name for path in sorted(run.evidence_path.glob("*.json"))]
            self.assertEqual(names, ["000001-delegation-started.json", "000002-delegation-finished.json", "binding.json"])
            self.assertNotIn("identity", second.value)
            with self.assertRaises(FileExistsError):
                storage.write_once(first.value["path"], b"replacement")

    def test_direct_implementations_can_append_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=False).value
            result = context.append_event(run, "step-completed", {"step": "1"}, actor="implement")
            self.assertTrue(result.ok, result.error)

    def test_cycle_cannot_write_implementation_evidence_during_delegation(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).value
            self.assertTrue(context.append_event(run, "delegation-started", {"role": "implementer"}, actor="cycle").ok)
            blocked = context.append_event(run, "step-completed", {"step": "1"}, actor="cycle")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.error.code, "writer_not_allowed")
            self.assertTrue(context.append_event(run, "step-completed", {"step": "1"}, actor="implement").ok)
            self.assertTrue(context.append_event(run, "delegation-finished", {"outcome": "returned"}, actor="cycle").ok)

    def test_red_test_snapshot_freezes_files_and_command(self) -> None:
        snapshot = tdd.freeze_test(
            {"tests/example_test.py": b"test bytes"},
            command="python3 -m unittest tests.example_test",
        )
        self.assertRegex(snapshot["files"]["tests/example_test.py"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(snapshot["command"], r"^sha256:[0-9a-f]{64}$")
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
            self.assertEqual(result.error.code, "human_gate_not_allowed")

    def test_recovery_escalates_only_after_diagnosis_and_one_changed_method(self) -> None:
        self.assertEqual(gates.recovery_action(diagnosed=False, method_changed=False, still_stuck=True), "diagnose")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=False, still_stuck=True), "change_method")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=True, still_stuck=True), "human_judgment")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=True, still_stuck=False), "continue")

if __name__ == "__main__":
    unittest.main()
