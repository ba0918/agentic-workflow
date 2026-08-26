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
        "oracle_status": "failing",
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

    def test_fixable_finding_requires_a_preverified_failing_oracle(self) -> None:
        result = model.validate_finding(finding(oracle_status="passing"))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "finding_oracle_not_failing")

    def test_finding_requires_traceable_spec_evidence_root_cause_version_and_profile(self) -> None:
        for field in ("specification", "evidence", "root_cause", "spec_commit", "profile"):
            value = finding()
            value.pop(field)
            value["id"] = model.finding_id(value)
            result = model.validate_finding(value)
            self.assertFalse(result.ok, field)
            self.assertEqual(result.error.code, "finding_field_missing")

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
        initial = [
            {"event_type": "initial-full-review-started"},
            {"event_type": "initial-findings-recorded"},
        ]
        self.assertEqual(model.next_review_stage(initial, [open_finding]), "targeted")
        closed = {**open_finding, "state": "closed"}
        self.assertEqual(model.next_review_stage(initial, [closed]), "final-full")
        events = initial + [
            {"event_type": "final-full-review-started"},
            {"event_type": "final-findings-recorded"},
        ]
        self.assertEqual(model.next_review_stage(events, [open_finding]), "targeted")
        self.assertEqual(model.next_review_stage(events, [closed]), "ready-to-complete")

    def test_review_is_complete_only_after_distinct_completion_event(self) -> None:
        findings = [{**finding(), "state": "closed"}]
        final_results = [{"event_type": "final-full-review-started"}, {"event_type": "final-findings-recorded"}]
        self.assertFalse(model.review_complete(final_results, findings))
        self.assertTrue(model.review_complete(final_results + [{"event_type": "review-completed"}], findings))

    def test_unrelated_minor_findings_are_observations_but_serious_regressions_join_review(self) -> None:
        warn = finding(severity="warn")
        info = finding(severity="info", action="record_only", oracle="")
        critical = finding(severity="critical", oracle="critical oracle")
        related_warn = finding(severity="warn", oracle="related oracle")
        admitted, observations = model.admit_new_findings(
            [warn, info, critical, related_warn], related_ids={related_warn["id"]}
        )
        self.assertEqual([item["severity"] for item in admitted], ["critical", "warn"])
        self.assertEqual([item["severity"] for item in observations], ["warn", "info"])

if __name__ == "__main__":
    unittest.main()
