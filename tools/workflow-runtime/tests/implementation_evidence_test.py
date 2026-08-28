from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/shared"))
import implementation_evidence
from implementation_evidence import JsonObject

class _EvidenceTestCase(unittest.TestCase):
    def binding(self, steps: list[JsonObject]) -> JsonObject:
        return {"version": 2, "approval_commit": "a" * 40, "steps": steps}

    def event(self, sequence: int, event_type: str, **fields: object) -> JsonObject:
        return {"version": 2, "sequence": sequence, "event_type": event_type, **fields}

    def snapshot(self) -> JsonObject:
        return {"files": {"tests/a.py": "sha256:" + "0" * 64}, "command": "sha256:" + "1" * 64}

    def gate(
        self, timing: str, *, target: JsonObject | None = None, criterion: str = "Approved?",
    ) -> JsonObject:
        return {
            "gate_id": "approve-step",
            "sections": ["Contract"],
            "criterion": criterion,
            "target": target or {"kind": "files", "paths": ["app.txt"]},
            "timing": timing,
            "allowed_results": ["approved", "rejected"],
        }

    def approval(self, sequence: int, *, result: str = "approved") -> JsonObject:
        return self.event(
            sequence, "human_gate", step="1", gate_id="approve-step", result=result,
            reason="human answered the declared gate",
        )


class HumanGateEvidenceTest(_EvidenceTestCase):
    def test_before_edit_gate_must_be_approved_before_step_work(self) -> None:
        binding = self.binding([{
            "id": "1", "completion": "check", "human_gates": [self.gate("before_edit")],
        }])
        check = self.event(
            1, "check", step="1", checks=[{"exit_code": 0}], changed_paths=[],
        )
        missing = implementation_evidence.derive_implementation(binding, [check])
        rejected = implementation_evidence.derive_implementation(
            binding, [self.approval(1, result="rejected"), {**check, "sequence": 2}],
        )
        approved = implementation_evidence.derive_implementation(
            binding, [self.approval(1), {**check, "sequence": 2}],
        )

        self.assertEqual(missing.required_error().code, "human_gate_required")
        self.assertEqual(rejected.required_error().code, "human_gate_required")
        self.assertTrue(approved.ok, approved.error)
        self.assertEqual(approved.required()["completed_steps"], ["1"])

    def test_before_commit_gate_must_follow_evidence_and_immediately_guard_target_changes(self) -> None:
        binding = self.binding([{
            "id": "1", "completion": "artifact", "human_gates": [self.gate("before_commit")],
        }])
        artifact = self.event(
            1, "artifact", step="1", checks=[], changed_paths=["app.txt"],
        )
        gate = self.approval(2)
        commit = self.event(
            3, "commit", step="1", commit="b" * 40,
            safety={"paths": ["app.txt"], "unplanned": []},
        )
        too_early = implementation_evidence.derive_implementation(
            binding, [self.approval(1), {**artifact, "sequence": 2}, commit],
        )
        missing = implementation_evidence.derive_implementation(binding, [artifact, {**commit, "sequence": 2}])
        approved = implementation_evidence.derive_implementation(binding, [artifact, gate, commit])
        changed_after_approval = implementation_evidence.derive_implementation(binding, [
            artifact,
            gate,
            self.event(3, "artifact", step="1", checks=[], changed_paths=["app.txt"]),
            {**commit, "sequence": 4},
        ])

        self.assertEqual(too_early.required_error().code, "human_gate_timing_invalid")
        self.assertEqual(missing.required_error().code, "human_gate_required")
        self.assertTrue(approved.ok, approved.error)
        self.assertEqual(changed_after_approval.required_error().code, "human_gate_required")

    def test_before_implementation_green_gate_must_follow_step_completion_and_stay_current(self) -> None:
        binding = self.binding([{
            "id": "1", "completion": "check",
            "human_gates": [self.gate("before_implementation_green")],
        }])
        check = self.event(
            1, "check", step="1", checks=[{"exit_code": 0}], changed_paths=[],
        )
        green = self.event(3, "implementation_green", completed_steps=["1"])
        missing = implementation_evidence.derive_implementation(
            binding, [check, {**green, "sequence": 2}],
        )
        too_early = implementation_evidence.derive_implementation(
            binding, [self.approval(1), {**check, "sequence": 2}, green],
        )
        approved = implementation_evidence.derive_implementation(binding, [check, self.approval(2), green])

        self.assertEqual(missing.required_error().code, "human_gate_required")
        self.assertEqual(too_early.required_error().code, "human_gate_timing_invalid")
        self.assertTrue(approved.ok, approved.error)

    def test_implementation_green_lists_the_steps_completed_under_human_gates(self) -> None:
        binding = self.binding([{
            "id": "1", "completion": "check",
            "human_gates": [self.gate("before_implementation_green")],
        }])
        events = [
            self.event(1, "check", step="1", checks=[{"exit_code": 0}], changed_paths=[]),
            self.approval(2),
            self.event(3, "implementation_green", completed_steps=[]),
        ]

        result = implementation_evidence.derive_implementation(binding, events)

        self.assertEqual(result.required_error().code, "transition_invalid")

    def test_event_gate_requires_the_declared_existing_sequence(self) -> None:
        target = {"kind": "event", "sequence": 1}
        binding = self.binding([{
            "id": "1", "completion": "check",
            "human_gates": [self.gate("before_implementation_green", target=target)],
        }])
        check = self.event(1, "check", step="1", checks=[{"exit_code": 0}], changed_paths=[])
        approved = implementation_evidence.derive_implementation(binding, [check, self.approval(2)])
        missing_target_binding = self.binding([{
            "id": "1", "completion": "check",
            "human_gates": [self.gate(
                "before_implementation_green", target={"kind": "event", "sequence": 9},
            )],
        }])
        missing_target = implementation_evidence.derive_implementation(
            missing_target_binding, [check, self.approval(2)],
        )

        self.assertTrue(approved.ok, approved.error)
        self.assertEqual(missing_target.required_error().code, "human_gate_target_invalid")

    def test_rebound_carries_completion_only_for_identical_human_gates(self) -> None:
        gate = self.gate("before_edit")
        binding = self.binding([{
            "id": "old", "completion": "check", "human_gates": [gate],
        }])
        completed = [
            self.event(
                1, "human_gate", step="old", gate_id="approve-step", result="approved",
                reason="approved",
            ),
            self.event(2, "check", step="old", checks=[{"exit_code": 0}], changed_paths=[]),
        ]
        same = self.event(
            3, "rebound", approval_commit="b" * 40,
            steps=[{"id": "same", "completion": "check", "human_gates": [gate]}],
            mappings=[{"old": "old", "new": "same"}], reason="approved",
        )
        changed_gate = {**gate, "criterion": "A changed question?"}
        changed = self.event(
            3, "rebound", approval_commit="b" * 40,
            steps=[{"id": "changed", "completion": "check", "human_gates": [changed_gate]}],
            mappings=[{"old": "old", "new": "changed"}], reason="approved",
        )
        same_result = implementation_evidence.derive_implementation(binding, [*completed, same])
        changed_result = implementation_evidence.derive_implementation(binding, [*completed, changed])

        self.assertEqual(same_result.required()["completed_steps"], ["same"])
        self.assertEqual(changed_result.required()["completed_steps"], [])
        self.assertEqual(changed_result.required()["resume_step"], "changed")

    def test_later_target_changes_allow_work_but_require_a_fresh_final_gate(self) -> None:
        binding = self.binding([
            {
                "id": "1", "completion": "check",
                "human_gates": [self.gate("before_implementation_green")],
            },
            {"id": "2", "completion": "check"},
        ])
        work = [
            self.event(1, "check", step="1", checks=[{"exit_code": 0}], changed_paths=[]),
            self.approval(2),
            self.event(
                3, "check", step="2", checks=[{"exit_code": 0}], changed_paths=["app.txt"],
            ),
            self.event(
                4, "commit", step="2", commit="b" * 40,
                safety={"paths": ["app.txt"], "unplanned": []},
            ),
        ]
        stale = implementation_evidence.derive_implementation(
            binding, [*work, self.event(5, "implementation_green", completed_steps=["1", "2"])],
        )
        refreshed = implementation_evidence.derive_implementation(binding, [
            *work,
            self.approval(5),
            self.event(6, "implementation_green", completed_steps=["1", "2"]),
        ])

        self.assertTrue(implementation_evidence.derive_implementation(binding, work).ok)
        self.assertEqual(stale.required_error().code, "human_gate_required")
        self.assertTrue(refreshed.ok, refreshed.error)


class CompletionFreshnessEvidenceTest(_EvidenceTestCase):
    def test_only_the_latest_red_green_refactor_commit_chain_completes_a_test_step(self) -> None:
        binding = self.binding([{"id": "1", "completion": "test"}])
        first_chain = [
            self.event(1, "red", step="1", command="tests", exit_code=1, snapshot=self.snapshot()),
            self.event(2, "green", step="1", command="tests", exit_code=0, snapshot=self.snapshot()),
            self.event(3, "refactor", step="1", command="tests", exit_code=0, snapshot=self.snapshot()),
            self.event(
                4, "commit", step="1", commit="b" * 40,
                safety={"paths": ["app.txt"], "unplanned": []},
            ),
        ]
        restarted = implementation_evidence.derive_implementation(binding, [
            *first_chain,
            self.event(5, "red", step="1", command="tests", exit_code=1, snapshot=self.snapshot()),
        ])
        refreshed = implementation_evidence.derive_implementation(binding, [
            *first_chain,
            self.event(5, "red", step="1", command="tests", exit_code=1, snapshot=self.snapshot()),
            self.event(6, "green", step="1", command="tests", exit_code=0, snapshot=self.snapshot()),
            self.event(7, "refactor", step="1", command="tests", exit_code=0, snapshot=self.snapshot()),
            self.event(
                8, "commit", step="1", commit="c" * 40,
                safety={"paths": ["app.txt"], "unplanned": []},
            ),
        ])

        self.assertTrue(restarted.ok, restarted.error)
        self.assertEqual(restarted.required()["completed_steps"], [])
        self.assertEqual(restarted.required()["resume_step"], "1")
        self.assertTrue(refreshed.ok, refreshed.error)
        self.assertEqual(refreshed.required()["completed_steps"], ["1"])

    def test_artifact_requires_a_nonempty_target_and_a_covering_commit(self) -> None:
        binding = self.binding([{"id": "1", "completion": "artifact"}])
        empty = implementation_evidence.derive_implementation(binding, [
            self.event(
                1, "artifact", step="1", checks=[], paths=[], changed_paths=["report.md"],
            ),
        ])
        artifact = self.event(
            1, "artifact", step="1", checks=[], paths=["report.md"],
            changed_paths=["report.md"],
        )
        unrelated = implementation_evidence.derive_implementation(binding, [
            artifact,
            self.event(
                2, "commit", step="1", commit="b" * 40,
                safety={"paths": ["other.txt"], "unplanned": []},
            ),
        ])
        covering = implementation_evidence.derive_implementation(binding, [
            artifact,
            self.event(
                2, "commit", step="1", commit="b" * 40,
                safety={"paths": ["other.txt", "report.md"], "unplanned": []},
            ),
        ])

        self.assertEqual(empty.required_error().code, "transition_invalid")
        self.assertTrue(unrelated.ok, unrelated.error)
        self.assertEqual(unrelated.required()["completed_steps"], [])
        self.assertEqual(unrelated.required()["resume_step"], "1")
        self.assertTrue(covering.ok, covering.error)
        self.assertEqual(covering.required()["completed_steps"], ["1"])

    def test_existing_version_two_artifact_without_paths_uses_its_changed_paths(self) -> None:
        binding = self.binding([{"id": "1", "completion": "artifact"}])
        events = [
            self.event(
                1, "artifact", step="1", checks=[], changed_paths=["legacy-report.md"],
            ),
            self.event(
                2, "commit", step="1", commit="b" * 40,
                safety={"paths": ["legacy-report.md"], "unplanned": []},
            ),
        ]

        result = implementation_evidence.derive_implementation(binding, events)

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.required()["completed_steps"], ["1"])


class ImplementationEvidenceTest(_EvidenceTestCase):

    def test_completion_and_resume_follow_each_completion_kind(self) -> None:
        steps: list[JsonObject] = [
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
        result = implementation_evidence.derive_implementation(self.binding(steps), events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.required()["completed_steps"], ["test", "check", "artifact", "external"])
        self.assertIsNone(result.required()["resume_step"])

    def test_later_evidence_is_rejected_until_a_changed_prior_step_is_committed(self) -> None:
        steps: list[JsonObject] = [
            {"id": "check", "completion": "check"},
            {"id": "external", "completion": "external"},
        ]
        events = [
            self.event(1, "check", step="check", checks=[{"exit_code": 0}], changed_paths=["x"]),
            self.event(2, "external", step="external", checked="deployment", summary="not ready", condition_met=False, changed_paths=[]),
        ]
        result = implementation_evidence.derive_implementation(self.binding(steps), events)
        self.assertFalse(result.ok)
        self.assertEqual(result.required_error().code, "step_order_invalid")

    def test_legacy_binding_and_event_are_explicitly_rejected(self) -> None:
        binding = self.binding([{"id": "1", "completion": "check"}])
        self.assertEqual(implementation_evidence.derive_implementation({**binding, "version": 1}, []).required_error().code, "legacy_evidence_unsupported")
        event = {"version": 1, "sequence": 1, "event_type": "check", "step": "1", "checks": [{"exit_code": 0}], "changed_paths": []}
        self.assertEqual(implementation_evidence.derive_implementation(binding, [event]).required_error().code, "legacy_evidence_unsupported")

    def test_rebound_carries_only_one_to_one_equivalent_completed_steps(self) -> None:
        binding = self.binding([{"id": "old", "completion": "check"}, {"id": "changed", "completion": "check"}])
        events = [
            self.event(1, "check", step="old", checks=[{"exit_code": 0}], changed_paths=[]),
            self.event(2, "check", step="changed", checks=[{"exit_code": 0}], changed_paths=[]),
            self.event(3, "rebound", approval_commit="b" * 40,
                       steps=[{"id": "same", "completion": "check"}, {"id": "new", "completion": "external"}],
                       mappings=[{"old": "old", "new": "same"}], reason="approved"),
        ]
        result = implementation_evidence.derive_implementation(binding, events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.required()["approval_commit"], "b" * 40)
        self.assertEqual(result.required()["completed_steps"], ["same"])
        self.assertEqual(result.required()["resume_step"], "new")

    def test_rebound_rejects_ambiguous_or_completion_changing_mapping(self) -> None:
        binding = self.binding([{"id": "old", "completion": "check"}])
        for mappings, steps in (
            ([{"old": "old", "new": "one"}, {"old": "old", "new": "two"}],
             [{"id": "one", "completion": "check"}, {"id": "two", "completion": "check"}]),
            ([{"old": "old", "new": "one"}], [{"id": "one", "completion": "external"}]),
        ):
            event = self.event(1, "rebound", approval_commit="b" * 40, steps=steps, mappings=mappings, reason="approved")
            self.assertEqual(implementation_evidence.derive_implementation(binding, [event]).required_error().code, "rebound_mapping_invalid")

    def test_malformed_version_two_events_are_rejected_without_crashing(self) -> None:
        binding = self.binding([{"id": "1", "completion": "check"}])
        malformed = self.event(1, "check", step="1", checks=[1], changed_paths=[])
        result = implementation_evidence.derive_implementation(binding, [malformed])
        self.assertFalse(result.ok)
        self.assertEqual(result.required_error().code, "evidence_invalid")
        malformed_boundary = self.event(1, "worktree-bound", branch=1, worktree="/tmp/work")
        self.assertEqual(
            implementation_evidence.derive_implementation(binding, [malformed_boundary]).required_error().code,
            "evidence_invalid",
        )
        green_without_red = self.event(
            1, "green", step="1", command="tests", exit_code=0,
            snapshot=self.snapshot(),
        )
        test_binding = self.binding([{"id": "1", "completion": "test"}])
        self.assertEqual(
            implementation_evidence.derive_implementation(test_binding, [green_without_red]).required_error().code,
            "transition_invalid",
        )

    def test_recovering_changes_the_effective_revision_boundary(self) -> None:
        binding = self.binding([{"id": "1", "completion": "check"}])
        events = [
            self.event(1, "recovering", current_commit="b" * 40,
                       changed_documents=["docs/spec/a.md"], reason="wording only"),
            self.event(2, "check", step="1", checks=[{"exit_code": 0}], changed_paths=[]),
        ]
        result = implementation_evidence.derive_implementation(binding, events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.required()["approval_commit"], "b" * 40)
        self.assertEqual(result.required()["segments"], [
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
        result = implementation_evidence.derive_implementation(binding, events)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.required()["segments"], [
            {"approval_commit": "a" * 40, "commits": ["c" * 40]},
            {"approval_commit": "d" * 40, "commits": []},
        ])
        self.assertEqual(result.required()["commits"], ["c" * 40])

    def test_frozen_red_snapshot_must_match_green_and_refactor(self) -> None:
        binding = self.binding([{"id": "1", "completion": "test"}])
        other = {"files": {"tests/b.py": "sha256:" + "2" * 64}, "command": "sha256:" + "3" * 64}
        events = [
            self.event(1, "red", step="1", command="tests", exit_code=1, snapshot=self.snapshot()),
            self.event(2, "green", step="1", command="tests", exit_code=0, snapshot=other),
            self.event(3, "refactor", step="1", command="tests", exit_code=0, snapshot=other),
            self.event(4, "commit", step="1", commit="b" * 40, safety={"paths": [], "unplanned": []}),
        ]
        result = implementation_evidence.derive_implementation(binding, events)
        self.assertFalse(result.ok)
        self.assertEqual(result.required_error().code, "frozen_red_mismatch")

    def test_external_requires_checked_summary_and_artifact_checks_are_optional(self) -> None:
        external = self.binding([{"id": "1", "completion": "external"}])
        missing = self.event(1, "external", step="1", condition_met=True, changed_paths=[])
        self.assertEqual(implementation_evidence.derive_implementation(external, [missing]).required_error().code, "evidence_invalid")
        artifact = self.binding([{"id": "1", "completion": "artifact"}])
        events = [
            self.event(1, "artifact", step="1", checks=[], changed_paths=["report.md"]),
            self.event(2, "commit", step="1", commit="b" * 40,
                       safety={"paths": ["report.md"], "unplanned": []}),
        ]
        result = implementation_evidence.derive_implementation(artifact, events)
        self.assertTrue(result.ok, result.error)
        self.assertIsNone(result.required()["resume_step"])

    def test_retirement_excludes_default_resume_without_erasing_run_state(self) -> None:
        binding = self.binding([{"id": "1", "completion": "check"}])
        events = [self.event(1, "resume-candidate-retired", reason="replacement requested")]

        result = implementation_evidence.derive_implementation(binding, events)

        self.assertTrue(result.ok, result.error)
        self.assertTrue(result.required()["resume_candidate_retired"])
        self.assertEqual(result.required()["resume_step"], "1")

    def test_rebound_does_not_reuse_an_unfinished_red_snapshot(self) -> None:
        binding = self.binding([{"id": "old", "completion": "test"}])
        events = [
            self.event(1, "red", step="old", command="tests", exit_code=1, snapshot=self.snapshot()),
            self.event(2, "rebound", approval_commit="b" * 40,
                       steps=[{"id": "new", "completion": "test"}],
                       mappings=[{"old": "old", "new": "new"}], reason="approved"),
            self.event(3, "green", step="new", command="tests", exit_code=0, snapshot=self.snapshot()),
        ]

        result = implementation_evidence.derive_implementation(binding, events)

        self.assertFalse(result.ok)
        self.assertEqual(result.required_error().code, "transition_invalid")

    def test_step_evidence_cannot_complete_out_of_plan_order(self) -> None:
        binding = self.binding([
            {"id": "first", "completion": "check"}, {"id": "second", "completion": "check"},
        ])
        event = self.event(1, "check", step="second", checks=[{"exit_code": 0}], changed_paths=[])

        result = implementation_evidence.derive_implementation(binding, [event])

        self.assertFalse(result.ok)
        self.assertEqual(result.required_error().code, "step_order_invalid")

    def test_later_step_cannot_complete_while_prior_changed_artifact_awaits_commit(self) -> None:
        binding = self.binding([
            {"id": "artifact", "completion": "artifact"},
            {"id": "verify", "completion": "check"},
        ])
        events = [
            self.event(
                1, "artifact", step="artifact", checks=[{"exit_code": 0}],
                changed_paths=["artifact.txt"],
            ),
            self.event(2, "check", step="verify", checks=[{"exit_code": 0}], changed_paths=[]),
        ]

        result = implementation_evidence.derive_implementation(binding, events)

        self.assertFalse(result.ok)
        self.assertEqual(result.required_error().code, "step_order_invalid")

if __name__ == "__main__":
    unittest.main()
