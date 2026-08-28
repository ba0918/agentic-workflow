import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "tools/workflow-runtime/review/review_model.py"
SPEC = importlib.util.spec_from_file_location("review_model_for_test", MODULE)
assert SPEC is not None
model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(model)
JsonObject = dict[str, object]


def finding(**changes: object) -> JsonObject:
    value: JsonObject = {
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

    def test_review_completion_is_derived_from_final_results_and_closed_findings(self) -> None:
        safety = {"completed": True, "summary": "safe", "unresolved": []}
        complete = [
            {"version": 2, "sequence": 1, "event_type": "review-bound", "model": "m"},
            {"version": 2, "sequence": 2, "event_type": "initial-full-review-started", "reviewer_context": "initial"},
            {"version": 2, "sequence": 3, "event_type": "initial-findings-recorded", "findings": [], "safety": safety, "reviewer_context": "initial", "actual_model": "m"},
            {"version": 2, "sequence": 4, "event_type": "final-full-review-started", "reviewer_context": "final"},
            {"version": 2, "sequence": 5, "event_type": "final-findings-recorded", "findings": [], "safety": safety, "reviewer_context": "final", "actual_model": "m"},
        ]
        self.assertTrue(model.review_complete(complete, []))
        self.assertFalse(model.review_complete(complete[:-2], []))

    def test_human_decision_clears_targeted_pending_and_rebound_updates_active_specification(self) -> None:
        item = finding(action="human_judgment", oracle="", oracle_status="unavailable",
                       oracle_unavailable_reason="requires a product decision")
        safety = {"completed": True, "summary": "safe", "unresolved": []}
        events = [
            {"version": 2, "sequence": 1, "event_type": "review-bound", "model": "m"},
            {"version": 2, "sequence": 2, "event_type": "initial-full-review-started", "reviewer_context": "initial"},
            {"version": 2, "sequence": 3, "event_type": "initial-findings-recorded", "findings": [item],
             "safety": safety, "reviewer_context": "initial", "actual_model": "m"},
            {"version": 2, "sequence": 4, "event_type": "targeted-review-started", "finding_ids": [item["id"]],
             "reviewer_context": "targeted"},
            {"version": 2, "sequence": 5, "event_type": "human-finding-decided", "finding_id": item["id"],
             "decision": "do_not_fix", "reason": "accepted"},
            {"version": 2, "sequence": 6, "event_type": "progress-assessed", "progressed": True},
            {"version": 2, "sequence": 7, "event_type": "findings_stale", "reason": "spec changed"},
            {"version": 2, "sequence": 8, "event_type": "findings-rebound", "reason": "approved",
             "spec_commit": "b" * 40},
        ]

        reduced = model.reduce_review(events)

        self.assertTrue(reduced.ok, reduced.error)
        self.assertEqual(reduced.value["targeted_pending"], [])
        self.assertEqual(reduced.value["active_spec_commit"], "b" * 40)
        self.assertEqual(reduced.value["findings"][0]["spec_commit"], "b" * 40)

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
