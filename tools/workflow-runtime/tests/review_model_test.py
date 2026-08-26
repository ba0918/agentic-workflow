import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "tools/workflow-runtime/review/review_model.py"
SPEC = importlib.util.spec_from_file_location("review_model", MODULE)
model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(model)

def finding(**changes) -> dict:
    value = {
        "severity": "critical",
        "action": "fix_and_verify",
        "specification": {"path": "docs/spec/review.md", "section": "指摘（finding）"},
        "evidence": {"path": "src/app.py", "observation": "wrong result"},
        "oracle": "python3 -m unittest tests.app_test",
        "root_cause": "validation",
        "state": "open",
        "spec_commit": "a" * 40,
        "profile": "default",
    }
    value.update(changes)
    value["id"] = model.finding_id(value)
    return value

class ReviewModelTest(unittest.TestCase):
    def test_finding_id_is_stable_across_line_movement(self) -> None:
        first = finding()
        second = finding(evidence={"path": "src/app.py", "line": 80, "observation": "wrong result"})
        self.assertEqual(first["id"], second["id"])

    def test_finding_state_is_only_open_or_closed(self) -> None:
        self.assertTrue(model.validate_finding(finding()).ok)
        for state in ("stale", "deferred"):
            result = model.validate_finding(finding(state=state))
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "finding_state_invalid")

    def test_findings_stale_is_a_resumable_pause(self) -> None:
        events = [{"event_type": "findings-recorded"}, {"event_type": "findings_stale"}]
        self.assertFalse(model.review_complete(events, []))
        self.assertTrue(model.can_append_after(events[-1]))

    def test_open_counts_progress_lexicographically(self) -> None:
        before = [finding(severity="security"), finding(severity="warn")]
        after = [finding(severity="critical"), finding(severity="warn"), finding(severity="warn", oracle="other")]
        self.assertEqual(model.open_counts(before), (1, 0, 1))
        self.assertEqual(model.open_counts(after), (0, 1, 2))
        self.assertTrue(model.made_progress(before, after))
        self.assertFalse(model.made_progress(after, after))

    def test_review_stage_is_initial_targeted_final_then_targeted_only(self) -> None:
        self.assertEqual(model.next_review_stage([], []), "initial-full")
        open_finding = finding()
        self.assertEqual(model.next_review_stage([{"event_type": "initial-full-review"}], [open_finding]), "targeted")
        closed = {**open_finding, "state": "closed"}
        self.assertEqual(model.next_review_stage([{"event_type": "initial-full-review"}], [closed]), "final-full")
        events = [{"event_type": "initial-full-review"}, {"event_type": "final-full-review"}]
        self.assertEqual(model.next_review_stage(events, [open_finding]), "targeted")
        self.assertEqual(model.next_review_stage(events, [closed]), "complete")

    def test_unrelated_minor_findings_are_observations_but_serious_regressions_join_review(self) -> None:
        warn = finding(severity="warn")
        critical = finding(severity="critical", oracle="critical oracle")
        admitted, observations = model.admit_new_findings([warn, critical], related_ids=set())
        self.assertEqual([item["severity"] for item in admitted], ["critical"])
        self.assertEqual([item["severity"] for item in observations], ["warn"])

if __name__ == "__main__":
    unittest.main()
