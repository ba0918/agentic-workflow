import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[3]
MODEL_MODULE = ROOT / "tools/workflow-runtime/review/review_model.py"


def load_model():
    assert MODEL_MODULE.exists(), "review_model.py does not exist yet"
    spec = importlib.util.spec_from_file_location("review_model", MODEL_MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SPEC_IDENTITY = "sha256:" + "a" * 64
IMPLEMENT_EVENT_IDENTITY = "sha256:" + "b" * 64
PLAN_IDENTITY = "sha256:" + "c" * 64


def oracle(command: str = "python3 -m unittest tests.review_model_test") -> dict:
    return {"kind": "command", "command": command, "cwd": "."}


def finding(**overrides) -> dict:
    value = {
        "severity": "warn",
        "action": "fix_and_verify",
        "spec_refs": [{"path": "docs/spec/review.md", "section": "指摘（finding）"}],
        "evidence": {
            "files": ["skills/ba0918-review/scripts/review_model.py"],
            "lines": [[10, 20]],
            "summary": "validation accepts an unknown severity",
        },
        "oracle": oracle(),
        "oracle_unavailable_reason": None,
        "root_cause_key": "severity-validation",
        "state": "open",
        "spec_identities": {"docs/spec/review.md": SPEC_IDENTITY},
        "profile": "default",
    }
    value.update(overrides)
    return value


def common_event(sequence: int = 1, previous_identity=None) -> dict:
    return {
        "version": 1,
        "sequence": sequence,
        "event_type": "review-bound",
        "review_id": "20260823t120000-deadbeef",
        "plan_identity": PLAN_IDENTITY,
        "spec_identities": {"docs/spec/review.md": SPEC_IDENTITY},
        "previous_identity": previous_identity,
    }


class FindingValidationTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()

    def test_a_complete_finding_is_accepted_with_an_id_derived_from_its_oracle(self):
        result = self.model.validate_finding(finding())
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["id"], self.model.finding_id(oracle()))

    def test_a_missing_field_is_rejected(self):
        value = finding()
        del value["root_cause_key"]
        result = self.model.validate_finding(value)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "finding_field_missing")

    def test_an_unknown_field_is_rejected(self):
        result = self.model.validate_finding(finding(line_number=12))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "finding_fields_invalid")

    def test_severity_action_and_state_must_be_known_words(self):
        for field, bad in (("severity", "blocker"), ("action", "ignore"), ("state", "done")):
            with self.subTest(field=field):
                result = self.model.validate_finding(finding(**{field: bad}))
                self.assertFalse(result.ok)
                self.assertEqual(result.error.field, field)

    def test_info_findings_can_only_be_recorded(self):
        result = self.model.validate_finding(finding(severity="info", action="auto_fix"))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "info_action_invalid")
        accepted = self.model.validate_finding(finding(severity="info", action="record_only"))
        self.assertTrue(accepted.ok, accepted.error)

    def test_a_human_judgment_finding_needs_the_reason_the_oracle_is_impossible(self):
        result = self.model.validate_finding(
            finding(action="human_judgment", oracle=None, oracle_unavailable_reason=None)
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "oracle_reason_missing")
        accepted = self.model.validate_finding(
            finding(
                action="human_judgment",
                oracle=None,
                oracle_unavailable_reason="naming quality cannot be checked by a command",
            )
        )
        self.assertTrue(accepted.ok, accepted.error)

    def test_every_other_finding_needs_an_oracle(self):
        result = self.model.validate_finding(finding(oracle=None))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "oracle_missing")

    def test_evidence_paths_must_stay_inside_the_repository(self):
        value = finding()
        value["evidence"]["files"] = ["/etc/passwd"]
        result = self.model.validate_finding(value)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "evidence_path_invalid")


class FindingIdentityTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()

    def test_the_same_oracle_gives_the_same_id_even_when_evidence_lines_move(self):
        first = self.model.validate_finding(finding()).value
        moved = finding()
        moved["evidence"]["lines"] = [[40, 55]]
        second = self.model.validate_finding(moved).value
        self.assertEqual(first["id"], second["id"])

    def test_a_different_oracle_gives_a_different_id(self):
        first = self.model.finding_id(oracle())
        second = self.model.finding_id(oracle("python3 -m unittest tests.other_test"))
        self.assertNotEqual(first, second)

    def test_a_human_judgment_finding_derives_its_id_from_the_reason_and_evidence(self):
        reason = "naming quality cannot be checked by a command"
        first = self.model.validate_finding(
            finding(action="human_judgment", oracle=None, oracle_unavailable_reason=reason)
        ).value
        second = self.model.validate_finding(
            finding(action="human_judgment", oracle=None, oracle_unavailable_reason=reason)
        ).value
        self.assertEqual(first["id"], second["id"])

    def test_a_fixed_set_identity_does_not_depend_on_ordering(self):
        one = self.model.validate_finding(finding()).value
        two = self.model.validate_finding(
            finding(oracle=oracle("python3 -m unittest tests.other_test"))
        ).value
        self.assertEqual(
            self.model.findings_identity([one, two]), self.model.findings_identity([two, one])
        )


class FindingTransitionTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()

    def test_an_open_finding_closes_when_its_oracle_passes(self):
        value = self.model.validate_finding(finding()).value
        result = self.model.transition(value, "closed", cause="oracle_passed")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["state"], "closed")
        self.assertEqual(value["state"], "open")

    def test_a_closed_finding_never_reopens(self):
        value = self.model.validate_finding(finding(state="closed")).value
        result = self.model.transition(value, "open", cause="oracle_failed")
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "transition_invalid")

    def test_a_human_judgment_finding_does_not_close_on_an_oracle_result(self):
        value = self.model.validate_finding(
            finding(
                action="human_judgment",
                oracle=None,
                oracle_unavailable_reason="cannot be checked by a command",
            )
        ).value
        by_oracle = self.model.transition(value, "closed", cause="oracle_passed")
        self.assertFalse(by_oracle.ok)
        self.assertEqual(by_oracle.error.code, "transition_invalid")
        by_human = self.model.transition(value, "closed", cause="human_decision")
        self.assertTrue(by_human.ok, by_human.error)

    def test_an_open_finding_can_become_stale_or_deferred(self):
        value = self.model.validate_finding(finding()).value
        self.assertTrue(self.model.transition(value, "stale", cause="spec_revised").ok)
        self.assertTrue(self.model.transition(value, "deferred", cause="deferred").ok)

    def test_a_machine_checked_finding_closes_on_a_human_rejection_and_never_reopens(self):
        value = self.model.validate_finding(finding()).value
        rejected = self.model.transition(value, "closed", cause="human_rejection")
        self.assertTrue(rejected.ok, rejected.error)
        self.assertEqual(rejected.value["state"], "closed")
        reopened = self.model.transition(rejected.value, "open", cause="oracle_failed")
        self.assertFalse(reopened.ok)
        self.assertEqual(reopened.error.code, "transition_invalid")

    def test_a_human_may_reject_but_not_accept_a_machine_checked_finding(self):
        value = self.model.validate_finding(finding()).value
        accepted = self.model.transition(value, "closed", cause="human_decision")
        self.assertFalse(accepted.ok)
        self.assertEqual(accepted.error.code, "transition_invalid")
        rejected = self.model.transition(value, "closed", cause="human_rejection")
        self.assertTrue(rejected.ok, rejected.error)

    def test_a_human_judgment_finding_still_closes_on_acceptance_or_rejection(self):
        value = self.model.validate_finding(
            finding(
                action="human_judgment",
                oracle=None,
                oracle_unavailable_reason="cannot be checked by a command",
            )
        ).value
        accepted = self.model.transition(value, "closed", cause="human_decision")
        self.assertTrue(accepted.ok, accepted.error)
        rejected = self.model.transition(value, "closed", cause="human_rejection")
        self.assertTrue(rejected.ok, rejected.error)


class RootCauseGroupingTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()

    def test_findings_with_the_same_root_cause_are_shown_as_one_fix_unit(self):
        one = self.model.validate_finding(finding()).value
        two = self.model.validate_finding(
            finding(oracle=oracle("python3 -m unittest tests.other_test"))
        ).value
        other = self.model.validate_finding(
            finding(
                oracle=oracle("python3 -m unittest tests.third_test"),
                root_cause_key="unrelated",
            )
        ).value
        groups = self.model.group_by_root_cause([one, two, other])
        self.assertEqual(groups["severity-validation"], sorted([one["id"], two["id"]]))
        self.assertEqual(groups["unrelated"], [other["id"]])


class ReviewEventTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()

    def test_the_first_event_binds_to_the_last_implement_event(self):
        candidate = common_event()
        candidate["implement_event_identity"] = IMPLEMENT_EVENT_IDENTITY
        result = self.model.seal_review_event(candidate, None)
        self.assertTrue(result.ok, result.error)
        self.assertIn("content_identity", result.value)

    def test_a_first_event_without_the_implement_identity_is_rejected(self):
        result = self.model.seal_review_event(common_event(), None)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "event_field_missing")

    def test_a_frozen_findings_event_records_model_level_and_profile(self):
        bound = common_event()
        bound["implement_event_identity"] = IMPLEMENT_EVENT_IDENTITY
        previous = self.model.seal_review_event(bound, None).value
        one = self.model.validate_finding(finding()).value
        candidate = common_event(2, previous["content_identity"])
        candidate["event_type"] = "findings-frozen"
        candidate.update(
            {
                "findings": [one],
                "findings_identity": self.model.findings_identity([one]),
                "model": "claude-fable-5",
                "model_source": "explicit",
                "level": "standard",
                "profile_identities": {"default": SPEC_IDENTITY},
                "reviewed_paths": ["skills/ba0918-review/scripts/review_model.py"],
            }
        )
        result = self.model.seal_review_event(candidate, previous)
        self.assertTrue(result.ok, result.error)
        del candidate["model_source"]
        missing = self.model.seal_review_event(candidate, previous)
        self.assertFalse(missing.ok)
        self.assertEqual(missing.error.code, "event_field_missing")

    def test_raw_logs_and_secret_values_are_never_durable(self):
        candidate = common_event()
        candidate["implement_event_identity"] = IMPLEMENT_EVENT_IDENTITY
        candidate["stdout"] = "whole output"
        result = self.model.seal_review_event(candidate, None)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "raw_log_forbidden")

    def test_a_second_opinion_event_records_reviewer_and_full_model_id(self):
        bound = common_event()
        bound["implement_event_identity"] = IMPLEMENT_EVENT_IDENTITY
        previous = self.model.seal_review_event(bound, None).value
        candidate = common_event(2, previous["content_identity"])
        candidate["event_type"] = "second-opinion"
        candidate["second_reviewer"] = "codex"
        candidate["second_model"] = "gpt-5.4"
        result = self.model.seal_review_event(candidate, previous)
        self.assertTrue(result.ok, result.error)
        alias = dict(candidate)
        alias["second_model"] = "gpt"
        refused = self.model.seal_review_event(alias, previous)
        self.assertFalse(refused.ok)
        self.assertEqual(refused.error.code, "model_id_invalid")

    def test_a_stopped_event_type_is_refused_as_unknown(self):
        candidate = common_event()
        candidate["event_type"] = "stopped"
        candidate["reason"] = "blocking condition"
        result = self.model.seal_review_event(candidate, None)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "event_type_invalid")

    def test_an_event_that_does_not_extend_the_chain_is_rejected(self):
        bound = common_event()
        bound["implement_event_identity"] = IMPLEMENT_EVENT_IDENTITY
        previous = self.model.seal_review_event(bound, None).value
        candidate = common_event(3, previous["content_identity"])
        candidate["event_type"] = "warning"
        candidate["reason"] = "second_reviewer_unavailable"
        result = self.model.seal_review_event(candidate, previous)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "stale_event_chain")


class DecisionEventTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()
        bound = common_event()
        bound["implement_event_identity"] = IMPLEMENT_EVENT_IDENTITY
        self.previous = self.model.seal_review_event(bound, None).value

    def decision(self, result: str, **extra) -> dict:
        candidate = common_event(2, self.previous["content_identity"])
        candidate["event_type"] = "decision"
        candidate["finding_id"] = "f-0123456789abcdef"
        candidate["result"] = result
        candidate.update(extra)
        return candidate

    def test_a_rejection_is_sealed_only_with_a_reason(self):
        without = self.model.seal_review_event(self.decision("rejected"), self.previous)
        self.assertFalse(without.ok)
        self.assertEqual(without.error.code, "decision_reason_missing")
        empty = self.model.seal_review_event(self.decision("rejected", reason=""), self.previous)
        self.assertFalse(empty.ok)
        with_reason = self.model.seal_review_event(
            self.decision("rejected", reason="the check is stricter than the specification asks"),
            self.previous,
        )
        self.assertTrue(with_reason.ok, with_reason.error)
        self.assertEqual(with_reason.value["reason"], "the check is stricter than the specification asks")

    def test_an_acceptance_recorded_without_a_reason_as_older_records_were_is_still_sealed(self):
        result = self.model.seal_review_event(self.decision("accepted"), self.previous)
        self.assertTrue(result.ok, result.error)
        self.assertNotIn("reason", result.value)


class DerivedFindingStatesTest(unittest.TestCase):
    def setUp(self):
        self.model = load_model()
        self.machine = self.model.validate_finding(finding()).value
        self.judged = self.model.validate_finding(
            finding(
                action="human_judgment",
                oracle=None,
                oracle_unavailable_reason="naming quality cannot be checked by a command",
            )
        ).value

    def test_states_are_derived_from_a_record_whose_decisions_carry_no_reason(self):
        # Records written before the reason field existed name the frozen set "findings-fixed"
        # and record decisions without a reason; deriving states from them must keep working.
        events = [
            {"event_type": "review-bound"},
            {"event_type": "findings-fixed", "findings": [self.machine, self.judged]},
            {
                "event_type": "reverify",
                "verdicts": [
                    {"finding_id": self.machine["id"], "state": "closed", "oracle_failures": 0},
                    {"finding_id": self.judged["id"], "state": "open", "oracle_failures": 0},
                ],
            },
            {"event_type": "decision", "finding_id": self.judged["id"], "result": "accepted"},
        ]
        states = {id_: f["state"] for id_, f in self.model.current_findings(events).items()}
        self.assertEqual(states, {self.machine["id"]: "closed", self.judged["id"]: "closed"})

    def test_a_rejection_with_a_reason_closes_a_machine_checked_finding_in_the_derived_states(self):
        events = [
            {"event_type": "findings-frozen", "findings": [self.machine]},
            {
                "event_type": "decision",
                "finding_id": self.machine["id"],
                "result": "rejected",
                "reason": "the check is stricter than the specification asks",
            },
        ]
        derived = self.model.current_findings(events)
        self.assertEqual(derived[self.machine["id"]]["state"], "closed")

    def test_a_stale_event_marks_its_findings_stale_in_the_derived_states(self):
        events = [
            {"event_type": "findings-frozen", "findings": [self.machine, self.judged]},
            {
                "event_type": "findings_stale",
                "observed_spec_identities": {},
                "verdicts": [{"finding_id": self.machine["id"], "state": "stale"}],
            },
        ]
        derived = self.model.current_findings(events)
        self.assertEqual(derived[self.machine["id"]]["state"], "stale")
        self.assertEqual(derived[self.judged["id"]]["state"], "open")

    def test_a_finding_added_again_after_a_decision_keeps_its_decided_state(self):
        resubmitted = dict(self.machine)
        resubmitted["oracle_failures"] = 3
        events = [
            {"event_type": "findings-frozen", "findings": [self.machine]},
            {"event_type": "decision", "finding_id": self.machine["id"], "result": "rejected", "reason": "stays"},
            {"event_type": "findings-added", "findings": [resubmitted], "commits": []},
        ]
        derived = self.model.current_findings(events)[self.machine["id"]]
        self.assertEqual(derived["state"], "closed")
        self.assertEqual(derived["oracle_failures"], 0)

    def test_deferred_findings_stay_outside_the_derived_set(self):
        aside = dict(self.machine)
        aside["state"] = "deferred"
        events = [
            {"event_type": "findings-frozen", "findings": [self.judged]},
            {"event_type": "deferred", "findings": [aside]},
        ]
        self.assertEqual(set(self.model.current_findings(events)), {self.judged["id"]})


if __name__ == "__main__":
    unittest.main()
