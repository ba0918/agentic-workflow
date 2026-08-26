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

    def snapshot(self) -> dict:
        return {"files": {"tests/a.py": "sha256:" + "0" * 64}, "command": "sha256:" + "1" * 64}

    def test_completion_and_resume_follow_each_completion_kind(self) -> None:
        steps = [
            {"id": "test", "completion": "test"}, {"id": "check", "completion": "check"},
            {"id": "artifact", "completion": "artifact"}, {"id": "external", "completion": "external"},
        ]
        events = [
            self.event(1, "red", step="test", command="tests", exit_code=1, snapshot=self.snapshot()),
            self.event(2, "green", step="test", command="tests", exit_code=0, snapshot=self.snapshot()),
            self.event(3, "refactor", step="test", command="tests", exit_code=0, snapshot=self.snapshot()),
            self.event(4, "commit", step="test", commit="b" * 40, safety={"paths": [], "unplanned": []}),
            self.event(5, "check", step="check", checks=[{"exit_code": 0}], changed_paths=[]),
            self.event(6, "artifact", step="artifact", checks=[{"exit_code": 0}], changed_paths=["a"]),
            self.event(7, "commit", step="artifact", commit="c" * 40, safety={"paths": ["a"], "unplanned": []}),
            self.event(8, "external", step="external", checked="deployment", summary="available", condition_met=True, changed_paths=[]),
        ]
        result = self.model.derive_implementation(self.binding(steps), events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["completed_steps"], ["test", "check", "artifact", "external"])
        self.assertIsNone(result.value["resume_step"])

    def test_external_false_and_changed_check_without_commit_remain_incomplete(self) -> None:
        steps = [{"id": "check", "completion": "check"}, {"id": "external", "completion": "external"}]
        events = [
            self.event(1, "check", step="check", checks=[{"exit_code": 0}], changed_paths=["x"]),
            self.event(2, "external", step="external", checked="deployment", summary="not ready", condition_met=False, changed_paths=[]),
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

    def test_rebound_carries_only_one_to_one_equivalent_completed_steps(self) -> None:
        binding = self.binding([{"id": "old", "completion": "check"}, {"id": "changed", "completion": "check"}])
        events = [
            self.event(1, "check", step="old", checks=[{"exit_code": 0}], changed_paths=[]),
            self.event(2, "check", step="changed", checks=[{"exit_code": 0}], changed_paths=[]),
            self.event(3, "rebound", approval_commit="b" * 40,
                       steps=[{"id": "same", "completion": "check"}, {"id": "new", "completion": "external"}],
                       mappings=[{"old": "old", "new": "same"}], reason="approved"),
        ]
        result = self.model.derive_implementation(binding, events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["approval_commit"], "b" * 40)
        self.assertEqual(result.value["completed_steps"], ["same"])
        self.assertEqual(result.value["resume_step"], "new")

    def test_rebound_rejects_ambiguous_or_completion_changing_mapping(self) -> None:
        binding = self.binding([{"id": "old", "completion": "check"}])
        for mappings, steps in (
            ([{"old": "old", "new": "one"}, {"old": "old", "new": "two"}],
             [{"id": "one", "completion": "check"}, {"id": "two", "completion": "check"}]),
            ([{"old": "old", "new": "one"}], [{"id": "one", "completion": "external"}]),
        ):
            event = self.event(1, "rebound", approval_commit="b" * 40, steps=steps, mappings=mappings, reason="approved")
            self.assertEqual(self.model.derive_implementation(binding, [event]).error.code, "rebound_mapping_invalid")

    def test_malformed_version_two_events_are_rejected_without_crashing(self) -> None:
        binding = self.binding([{"id": "1", "completion": "check"}])
        malformed = self.event(1, "check", step="1", checks=[1], changed_paths=[])
        result = self.model.derive_implementation(binding, [malformed])
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "evidence_invalid")
        malformed_boundary = self.event(1, "worktree-bound", branch=1, worktree="/tmp/work")
        self.assertEqual(
            self.model.derive_implementation(binding, [malformed_boundary]).error.code,
            "evidence_invalid",
        )
        green_without_red = self.event(
            1, "green", step="1", command="tests", exit_code=0,
            snapshot=self.snapshot(),
        )
        test_binding = self.binding([{"id": "1", "completion": "test"}])
        self.assertEqual(
            self.model.derive_implementation(test_binding, [green_without_red]).error.code,
            "transition_invalid",
        )

    def test_recovering_changes_the_effective_revision_boundary(self) -> None:
        binding = self.binding([{"id": "1", "completion": "check"}])
        events = [
            self.event(1, "recovering", current_commit="b" * 40,
                       changed_documents=["docs/spec/a.md"], reason="wording only"),
            self.event(2, "check", step="1", checks=[{"exit_code": 0}], changed_paths=[]),
        ]
        result = self.model.derive_implementation(binding, events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["approval_commit"], "b" * 40)
        self.assertEqual(result.value["segments"], [
            {"approval_commit": "a" * 40, "commits": []},
            {"approval_commit": "b" * 40, "commits": []},
        ])

    def test_rebound_keeps_commit_evidence_in_its_revision_segment(self) -> None:
        binding = self.binding([{"id": "old", "completion": "artifact"}])
        events = [
            self.event(1, "artifact", step="old", checks=[{"exit_code": 0}], changed_paths=["old"]),
            self.event(2, "commit", step="old", commit="c" * 40,
                       safety={"paths": ["old"], "unplanned": []}),
            self.event(3, "rebound", approval_commit="d" * 40,
                       steps=[{"id": "same", "completion": "artifact"}],
                       mappings=[{"old": "old", "new": "same"}], reason="approved"),
        ]
        result = self.model.derive_implementation(binding, events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["segments"], [
            {"approval_commit": "a" * 40, "commits": ["c" * 40]},
            {"approval_commit": "d" * 40, "commits": []},
        ])

    def test_frozen_red_snapshot_must_match_green_and_refactor(self) -> None:
        binding = self.binding([{"id": "1", "completion": "test"}])
        other = {"files": {"tests/b.py": "sha256:" + "2" * 64}, "command": "sha256:" + "3" * 64}
        events = [
            self.event(1, "red", step="1", command="tests", exit_code=1, snapshot=self.snapshot()),
            self.event(2, "green", step="1", command="tests", exit_code=0, snapshot=other),
            self.event(3, "refactor", step="1", command="tests", exit_code=0, snapshot=other),
            self.event(4, "commit", step="1", commit="b" * 40, safety={"paths": [], "unplanned": []}),
        ]
        result = self.model.derive_implementation(binding, events)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "frozen_red_mismatch")

    def test_external_requires_checked_summary_and_artifact_checks_are_optional(self) -> None:
        external = self.binding([{"id": "1", "completion": "external"}])
        missing = self.event(1, "external", step="1", condition_met=True, changed_paths=[])
        self.assertEqual(self.model.derive_implementation(external, [missing]).error.code, "evidence_invalid")
        artifact = self.binding([{"id": "1", "completion": "artifact"}])
        events = [
            self.event(1, "artifact", step="1", checks=[], changed_paths=["report.md"]),
            self.event(2, "commit", step="1", commit="b" * 40,
                       safety={"paths": ["report.md"], "unplanned": []}),
        ]
        result = self.model.derive_implementation(artifact, events)
        self.assertTrue(result.ok, result.error)
        self.assertIsNone(result.value["resume_step"])

if __name__ == "__main__":
    unittest.main()
