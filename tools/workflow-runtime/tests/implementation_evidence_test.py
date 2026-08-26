import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "tools/workflow-runtime/shared/implementation_evidence.py"

class ImplementationEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("implementation_evidence", MODULE)
        cls.model = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.model)

    def binding(self, steps: list[dict]) -> dict:
        return {"version": 2, "approval_commit": "a" * 40, "steps": steps}

    def event(self, sequence: int, event_type: str, **fields) -> dict:
        return {"version": 2, "sequence": sequence, "event_type": event_type, **fields}

    def test_completion_and_resume_follow_each_completion_kind(self) -> None:
        steps = [
            {"id": "test", "completion": "test"}, {"id": "check", "completion": "check"},
            {"id": "artifact", "completion": "artifact"}, {"id": "external", "completion": "external"},
        ]
        events = [
            self.event(1, "refactor", step="test", exit_code=0),
            self.event(2, "commit", step="test", commit="b" * 40),
            self.event(3, "check", step="check", checks=[{"exit_code": 0}], changed_paths=[]),
            self.event(4, "artifact", step="artifact", checks=[{"exit_code": 0}], changed_paths=["a"]),
            self.event(5, "commit", step="artifact", commit="c" * 40),
            self.event(6, "external", step="external", condition_met=True, changed_paths=[]),
        ]
        result = self.model.derive_implementation(self.binding(steps), events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["completed_steps"], ["test", "check", "artifact", "external"])
        self.assertIsNone(result.value["resume_step"])

    def test_external_false_and_changed_check_without_commit_remain_incomplete(self) -> None:
        steps = [{"id": "check", "completion": "check"}, {"id": "external", "completion": "external"}]
        events = [
            self.event(1, "check", step="check", checks=[{"exit_code": 0}], changed_paths=["x"]),
            self.event(2, "external", step="external", condition_met=False, changed_paths=[]),
        ]
        result = self.model.derive_implementation(self.binding(steps), events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["completed_steps"], [])
        self.assertEqual(result.value["resume_step"], "check")

    def test_legacy_binding_and_event_are_explicitly_rejected(self) -> None:
        binding = self.binding([{"id": "1", "completion": "check"}])
        self.assertEqual(self.model.derive_implementation({**binding, "version": 1}, []).error.code, "legacy_evidence_unsupported")
        event = {"version": 1, "sequence": 1, "event_type": "check", "step": "1", "checks": [{"exit_code": 0}], "changed_paths": []}
        self.assertEqual(self.model.derive_implementation(binding, [event]).error.code, "legacy_evidence_unsupported")

if __name__ == "__main__":
    unittest.main()
