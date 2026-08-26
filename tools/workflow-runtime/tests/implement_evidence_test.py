from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime import deps
from runtime import context, repository, storage, tdd
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

    def test_only_delegated_implementations_can_append_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=False).value
            result = context.append_event(run, "step-completed", {"step": "1"})
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "delegation_required")

    def test_red_test_snapshot_keeps_its_own_hash(self) -> None:
        snapshot = tdd.freeze_test({"tests/example_test.py": b"test bytes"})
        self.assertRegex(snapshot["tests/example_test.py"], r"^sha256:[0-9a-f]{64}$")

if __name__ == "__main__":
    unittest.main()
