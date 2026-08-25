import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[3]
MODEL_MODULE = ROOT / "tools/workflow-runtime/implement/execution_model.py"
SPEC = importlib.util.spec_from_file_location("cycle_execution_model", MODEL_MODULE)
implement_model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(implement_model)


PLAN_IDENTITY = "sha256:" + "1" * 64
SPEC_IDENTITY = "sha256:" + "2" * 64
BASE_HEAD = "3" * 40


def binding() -> dict:
    return {
        "version": 1,
        "attempt_id": "20260822t152244-a1b2c3d4",
        "plan": {
            "id": "20260822143915",
            "path": ".agents/artifacts/plans/20260822143915_cycle.md",
            "revision": 1,
            "content_identity": PLAN_IDENTITY,
        },
        "specs": [
            {
                "path": "docs/spec/cycle.md",
                "content_identity": SPEC_IDENTITY,
            }
        ],
        "repository_identity": "sha256:" + "4" * 64,
        "base_head": BASE_HEAD,
        "branch": "implement/20260822t152244-a1b2c3d4",
        "worktree": "/tmp/fixture/linked-worktree",
        "write_scope": ["skills/ba0918-cycle", "tests/cycle_runtime_test.py"],
        "human_gates": [],
        "executor": {
            "executor": "codex",
            "backend": "unavailable",
            "session_id": "unavailable",
            "reason": "not exposed safely",
        },
    }


def human_gate() -> dict:
    return {
        "gate_id": "approve-cycle-files",
        "step_id": "step-1",
        "sections": ["作業場所"],
        "criterion": "対象fileが承認済みの内容である",
        "target": {"kind": "files", "paths": ["skills/ba0918-cycle/SKILL.md"]},
        "timing": "before_implementation_green",
        "allowed_results": ["approved", "rejected"],
    }


def human_gate_event(result: str = "approved", target_identity: str | None = None) -> dict:
    return {
        "version": 1,
        "sequence": 1,
        "event_type": "human_gate",
        "attempt_id": binding()["attempt_id"],
        "plan_identity": PLAN_IDENTITY,
        "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
        "previous_identity": None,
        "gate_id": "approve-cycle-files",
        "step_id": "step-1",
        "target_identity": target_identity or "sha256:" + "8" * 64,
        "result": result,
    }


def oracle() -> dict:
    return {
        "version": 1,
        "step_id": "step-1",
        "sections": ["作業場所"],
        "test_targets": [
            {
                "path": "tests/cycle_runtime_test.py",
                "content_identity": "sha256:" + "5" * 64,
            }
        ],
        "command": ["python3", "-m", "unittest", "tests/cycle_runtime_test.py"],
        "cwd": ".",
        "environment_names": [],
        "timeout_seconds": 30,
        "expected_failure_kind": "behavior_failure",
        "observed_failure_kind": "behavior_failure",
        "failure_signature": "AttributeError: resolve_plan",
    }


def command_event(event_type: str, test_summary: dict) -> dict:
    return {
        "version": 1,
        "sequence": 1,
        "event_type": event_type,
        "attempt_id": binding()["attempt_id"],
        "plan_identity": PLAN_IDENTITY,
        "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
        "previous_identity": None,
        "step_id": "step-1",
        "oracle_identity": implement_model.content_identity(oracle()),
        "outcome": "passed",
        "exit_code": 0,
        "observation": "test command completed",
        "test_summary": test_summary,
    }


class CanonicalIdentityTest(unittest.TestCase):
    def test_mapping_order_does_not_change_content_identity(self) -> None:
        first = {"b": 2, "a": {"d": 4, "c": 3}}
        second = {"a": {"c": 3, "d": 4}, "b": 2}

        self.assertEqual(implement_model.content_identity(first), implement_model.content_identity(second))
        self.assertEqual(
            implement_model.canonical_json(first),
            b'{"a":{"c":3,"d":4},"b":2}\n',
        )


class BindingValidationTest(unittest.TestCase):
    def test_complete_binding_is_accepted(self) -> None:
        result = implement_model.validate_binding(binding())

        self.assertTrue(result.ok)
        self.assertIsNone(result.error)

    def test_identity_drift_names_the_changed_field(self) -> None:
        observed = binding()
        observed["base_head"] = "6" * 40

        result = implement_model.validate_snapshot(binding(), observed)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "identity_drift")
        self.assertEqual(result.error.field, "base_head")

    def test_missing_step_or_oracle_is_rejected(self) -> None:
        missing_step = oracle()
        del missing_step["step_id"]
        missing_identity = oracle()
        del missing_identity["test_targets"]

        self.assertEqual(
            implement_model.validate_oracle(missing_step).error.code,
            "oracle_field_missing",
        )
        self.assertEqual(
            implement_model.validate_oracle(missing_identity).error.code,
            "oracle_field_missing",
        )

    def test_environment_values_and_raw_logs_are_rejected(self) -> None:
        unsafe_oracle = oracle()
        unsafe_oracle["environment"] = {"API_TOKEN": "not-a-real-token"}
        unsafe_event = {
            "version": 1,
            "sequence": 1,
            "event_type": "stopped",
            "attempt_id": binding()["attempt_id"],
            "plan_identity": PLAN_IDENTITY,
            "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
            "previous_identity": None,
            "reason": "failure",
            "stdout": "full process output",
        }

        self.assertEqual(
            implement_model.validate_oracle(unsafe_oracle).error.code,
            "secret_value_forbidden",
        )
        self.assertEqual(
            implement_model.seal_event(unsafe_event).error.code,
            "raw_log_forbidden",
        )

    def test_untrusted_scalar_types_return_failures_instead_of_raising(self) -> None:
        invalid_binding = binding()
        invalid_binding["plan"]["id"] = 20260822143915
        invalid_oracle = oracle()
        invalid_oracle["test_targets"] = None

        binding_result = implement_model.validate_binding(invalid_binding)
        oracle_result = implement_model.validate_oracle(invalid_oracle)

        self.assertFalse(binding_result.ok)
        self.assertEqual(binding_result.error.code, "plan_binding_invalid")
        self.assertFalse(oracle_result.ok)
        self.assertEqual(oracle_result.error.code, "oracle_field_invalid")

    def test_generic_runner_summary_is_not_a_behavior_signature(self) -> None:
        invalid_oracle = oracle()
        invalid_oracle["failure_signature"] = "FAILED (errors=1)"

        result = implement_model.validate_oracle(invalid_oracle)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "oracle_failure_signature_invalid")

    def test_oracle_candidate_does_not_claim_an_observation_before_execution(self) -> None:
        candidate = oracle()
        del candidate["observed_failure_kind"]
        candidate["test_targets"] = ["tests/cycle_runtime_test.py"]

        candidate_result = implement_model.validate_oracle_candidate(candidate)
        durable_result = implement_model.validate_oracle(candidate)

        self.assertTrue(candidate_result.ok, candidate_result.error)
        self.assertFalse(durable_result.ok)
        self.assertEqual(durable_result.error.code, "oracle_field_missing")

    def test_oracle_candidate_only_expects_a_behavior_failure(self) -> None:
        candidate = oracle()
        del candidate["observed_failure_kind"]
        candidate["test_targets"] = ["tests/cycle_runtime_test.py"]
        candidate["expected_failure_kind"] = "import_failure"

        result = implement_model.validate_oracle_candidate(candidate)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "oracle_field_invalid")
        self.assertEqual(result.error.field, "expected_failure_kind")
        self.assertIn("behavior_failure", result.error.message)

    def test_oracle_candidate_names_why_its_test_targets_are_invalid(self) -> None:
        cases = {
            "test targets must be path strings": [{"path": "tests/a_test.py"}],
            "test targets must be unique": ["tests/a_test.py", "tests/a_test.py"],
            "test targets must be safe relative paths": ["../tests/a_test.py"],
        }
        for expected_message, targets in cases.items():
            with self.subTest(expected_message):
                candidate = oracle()
                del candidate["observed_failure_kind"]
                candidate["test_targets"] = targets

                result = implement_model.validate_oracle_candidate(candidate)

                self.assertFalse(result.ok)
                self.assertEqual(result.error.code, "oracle_field_invalid")
                self.assertEqual(result.error.message, expected_message)

    def test_oracle_rejects_unknown_fields_and_secret_shaped_command_arguments(self) -> None:
        unknown = oracle()
        unknown["stdout_copy"] = "bounded-looking output"
        secret_argument = oracle()
        secret_argument["command"].append("--api-token=<credential>")

        unknown_result = implement_model.validate_oracle(unknown)
        secret_result = implement_model.validate_oracle(secret_argument)

        self.assertFalse(unknown_result.ok)
        self.assertEqual(unknown_result.error.code, "oracle_fields_invalid")
        self.assertFalse(secret_result.ok)
        self.assertEqual(secret_result.error.code, "secret_value_forbidden")

    def test_event_rejects_unknown_fields_recursively(self) -> None:
        candidate = {
            "version": 1,
            "sequence": 1,
            "event_type": "stopped",
            "attempt_id": binding()["attempt_id"],
            "plan_identity": PLAN_IDENTITY,
            "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
            "previous_identity": None,
            "reason": "failure",
            "details": {"api_key": "<credential>"},
        }

        result = implement_model.seal_event(candidate)

        self.assertFalse(result.ok)
        self.assertIn(result.error.code, {"event_fields_invalid", "secret_value_forbidden"})

    def test_executor_provenance_and_environment_names_are_exact(self) -> None:
        unsafe_binding = binding()
        unsafe_binding["executor"]["api_key"] = "<credential>"
        duplicate_environment = oracle()
        duplicate_environment["environment_names"] = ["PYTHONPATH", "PYTHONPATH"]
        invalid_environment = oracle()
        invalid_environment["environment_names"] = ["lower-case-name"]

        binding_result = implement_model.validate_binding(unsafe_binding)

        self.assertFalse(binding_result.ok)
        self.assertIn(binding_result.error.code, {"executor_invalid", "secret_value_forbidden"})
        self.assertEqual(
            implement_model.validate_oracle(duplicate_environment).error.code,
            "oracle_field_invalid",
        )
        self.assertEqual(
            implement_model.validate_oracle(invalid_environment).error.code,
            "oracle_field_invalid",
        )


class WriteScopeTest(unittest.TestCase):
    def test_descendant_and_exact_file_are_inside_scope(self) -> None:
        scopes = ["skills/ba0918-cycle", "tests/cycle_runtime_test.py"]

        self.assertTrue(implement_model.validate_write_path("skills/ba0918-cycle/SKILL.md", scopes).ok)
        self.assertTrue(implement_model.validate_write_path("tests/cycle_runtime_test.py", scopes).ok)

    def test_absolute_traversal_and_sibling_paths_are_rejected(self) -> None:
        scopes = ["skills/ba0918-cycle"]

        for candidate in (
            "/tmp/outside",
            "skills/ba0918-cycle/../../../outside",
            "skills/ba0918-cycle-old/file.py",
        ):
            with self.subTest(candidate=candidate):
                result = implement_model.validate_write_path(candidate, scopes)
                self.assertFalse(result.ok)
                self.assertEqual(result.error.code, "write_scope_violation")


class TestSummaryValidationTest(unittest.TestCase):
    def test_command_events_accept_complete_or_unavailable_test_summary(self) -> None:
        complete = implement_model.seal_event(
            command_event(
                "green",
                {"status": "complete", "passed": 7, "failed": 0, "skipped": 2},
            )
        )
        unavailable = implement_model.seal_event(
            command_event(
                "green",
                {
                    "status": "unavailable",
                    "reason": "runner did not expose structured counts",
                },
            )
        )

        self.assertTrue(complete.ok, complete.error)
        self.assertTrue(unavailable.ok, unavailable.error)

    def test_test_summary_rejects_unknown_mixed_or_invented_counts(self) -> None:
        invalid_summaries = {
            "unknown status": {"status": "partial", "passed": 1, "failed": 0, "skipped": 0},
            "missing skipped": {"status": "complete", "passed": 1, "failed": 0},
            "negative count": {"status": "complete", "passed": 1, "failed": -1, "skipped": 0},
            "boolean count": {"status": "complete", "passed": True, "failed": 0, "skipped": 0},
            "invented unavailable counts": {
                "status": "unavailable",
                "reason": "runner did not expose structured counts",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
            "empty reason": {"status": "unavailable", "reason": ""},
            "unbounded reason": {"status": "unavailable", "reason": "x" * 501},
        }

        for case, summary in invalid_summaries.items():
            with self.subTest(case=case):
                result = implement_model.seal_event(command_event("green", summary))
                self.assertFalse(result.ok)
                self.assertEqual(result.error.code, "test_summary_invalid")

    def test_refactor_event_keeps_the_command_exit_code(self) -> None:
        event = command_event(
            "refactor",
            {"status": "complete", "passed": 1, "failed": 0, "skipped": 0},
        )
        del event["exit_code"]

        result = implement_model.seal_event(event)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "event_field_missing")
        self.assertEqual(result.error.field, "exit_code")


class EventChainTest(unittest.TestCase):
    def test_events_form_an_immutable_hash_chain(self) -> None:
        first = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 1,
                "event_type": "worktree-bound",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": None,
                "outcome": "bound",
            }
        )
        self.assertTrue(first.ok)
        second = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 2,
                "event_type": "red",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": first.value["content_identity"],
                "step_id": "step-1",
                "oracle_identity": implement_model.content_identity(oracle()),
                "outcome": "expected_failure",
                "exit_code": 1,
                "observation": "1 failed",
                "test_summary": {
                    "status": "unavailable",
                    "reason": "fixture has no structured runner output",
                },
            },
            previous_event=first.value,
        )

        self.assertTrue(second.ok)
        self.assertEqual(second.value["sequence"], 2)
        self.assertEqual(
            second.value["previous_identity"],
            first.value["content_identity"],
        )
        self.assertEqual(
            implement_model.event_identity(second.value),
            second.value["content_identity"],
        )

    def test_stale_sequence_and_previous_identity_are_rejected(self) -> None:
        previous = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 1,
                "event_type": "worktree-bound",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": None,
                "outcome": "bound",
            }
        ).value
        stale = {
            "version": 1,
            "sequence": 3,
            "event_type": "stopped",
            "attempt_id": binding()["attempt_id"],
            "plan_identity": PLAN_IDENTITY,
            "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
            "previous_identity": "sha256:" + "9" * 64,
            "reason": "drift",
        }

        result = implement_model.seal_event(stale, previous_event=previous)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "stale_event_chain")

    def test_stopped_event_is_terminal_for_the_attempt(self) -> None:
        first = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 1,
                "event_type": "worktree-bound",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": None,
                "outcome": "bound",
            }
        ).value
        stopped = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 2,
                "event_type": "stopped",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": first["content_identity"],
                "reason": "oracle_field_invalid",
            },
            previous_event=first,
        ).value

        result = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 3,
                "event_type": "red",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": stopped["content_identity"],
                "step_id": "step-1",
                "oracle_identity": implement_model.content_identity(oracle()),
                "outcome": "expected_failure",
                "exit_code": 1,
                "observation": "missing behavior",
                "test_summary": {
                    "status": "unavailable",
                    "reason": "fixture has no structured runner output",
                },
            },
            previous_event=stopped,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "terminal_event_chain")

    def test_only_a_resumed_event_may_follow_a_stop(self) -> None:
        first = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 1,
                "event_type": "worktree-bound",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": None,
                "outcome": "bound",
            }
        ).value
        stopped = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 2,
                "event_type": "stopped",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": first["content_identity"],
                "reason": "unintended_red",
            },
            previous_event=first,
        ).value

        resumed = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 3,
                "event_type": "resumed",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": stopped["content_identity"],
                "head": BASE_HEAD,
                "extra_commits": [],
                "uncommitted_changes": False,
                "next_step": "step-1",
                "redo": True,
            },
            previous_event=stopped,
        )

        self.assertTrue(resumed.ok, resumed.error)

    def _common(self, event_type: str, **fields) -> dict:
        return {
            "version": 1,
            "sequence": 1,
            "event_type": event_type,
            "attempt_id": binding()["attempt_id"],
            "plan_identity": PLAN_IDENTITY,
            "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
            "previous_identity": None,
            **fields,
        }

    def test_artifact_event_records_files_with_identities_and_format_checks(self) -> None:
        event = self._common(
            "artifact",
            step_id="step-2",
            files=[{"path": "skills/ba0918-cycle/SKILL.md", "content_identity": "sha256:" + "6" * 64}],
            checks=[{"command": ["bunx", "skills-ref", "validate", "skills/ba0918-cycle"], "exit_code": 0}],
        )

        sealed = implement_model.seal_event(event)

        self.assertTrue(sealed.ok, sealed.error)
        self.assertTrue(implement_model.seal_event({**event, "checks": []}).ok)

    def test_artifact_event_rejects_empty_or_unsafe_files(self) -> None:
        base = self._common(
            "artifact",
            step_id="step-2",
            files=[{"path": "skills/ba0918-cycle/SKILL.md", "content_identity": "sha256:" + "6" * 64}],
            checks=[],
        )
        invalid = {
            "no files": {**base, "files": []},
            "absolute path": {**base, "files": [{"path": "/etc/passwd", "content_identity": "sha256:" + "6" * 64}]},
            "bad identity": {**base, "files": [{"path": "a.md", "content_identity": "sha256:zz"}]},
            "unknown field": {**base, "stdout": "..."},
            "check without exit code": {**base, "checks": [{"command": ["true"]}]},
        }
        for case, event in invalid.items():
            with self.subTest(case=case):
                self.assertFalse(implement_model.seal_event(event).ok)

    def test_external_event_records_what_was_checked_and_a_bounded_summary(self) -> None:
        event = self._common("external", step_id="step-3", checked="手順 3 の実機確認", summary="起動して応答した")

        self.assertTrue(implement_model.seal_event(event).ok)
        self.assertFalse(implement_model.seal_event({**event, "summary": "x" * 501}).ok)
        self.assertFalse(implement_model.seal_event({**event, "checked": ""}).ok)

    def test_approval_event_records_the_human_verdict_on_a_target_identity(self) -> None:
        event = self._common("approval", step_id="step-2", target_identity="sha256:" + "7" * 64, result="approved")

        self.assertTrue(implement_model.seal_event(event).ok)
        self.assertTrue(implement_model.seal_event({**event, "result": "rejected"}).ok)
        self.assertFalse(implement_model.seal_event({**event, "result": "maybe"}).ok)
        self.assertFalse(implement_model.seal_event({**event, "target_identity": "nope"}).ok)

    def test_commit_event_may_say_it_was_recorded_late(self) -> None:
        event = self._common("commit", step_id="step-1", commit_sha="7" * 40, outcome="committed")

        self.assertTrue(implement_model.seal_event(event).ok)
        self.assertTrue(implement_model.seal_event({**event, "recorded_late": True}).ok)
        self.assertFalse(implement_model.seal_event({**event, "recorded_late": "yes"}).ok)

    def test_event_type_requires_its_own_fields(self) -> None:
        incomplete = {
            "version": 1,
            "sequence": 1,
            "event_type": "commit",
            "attempt_id": binding()["attempt_id"],
            "plan_identity": PLAN_IDENTITY,
            "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
            "previous_identity": None,
            "step_id": "step-1",
        }

        result = implement_model.seal_event(incomplete)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "event_field_missing")

    def test_existing_event_only_accepts_the_same_identity(self) -> None:
        candidate = {
            "version": 1,
            "sequence": 1,
            "event_type": "stopped",
            "attempt_id": binding()["attempt_id"],
            "plan_identity": PLAN_IDENTITY,
            "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
            "previous_identity": None,
            "reason": "permission_required",
        }
        sealed = implement_model.seal_event(candidate).value

        self.assertTrue(implement_model.compare_event_retry(sealed, sealed).ok)
        changed = dict(sealed)
        changed["reason"] = "persistence_unavailable"
        self.assertEqual(
            implement_model.compare_event_retry(sealed, changed).error.code,
            "event_identity_collision",
        )


class CheckEventTest(unittest.TestCase):
    @staticmethod
    def _event(**fields) -> dict:
        return {
            "version": 1,
            "sequence": 1,
            "event_type": "check",
            "attempt_id": binding()["attempt_id"],
            "plan_identity": PLAN_IDENTITY,
            "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
            "previous_identity": None,
            "step_id": "step-2",
            "checks": [{"command": ["bunx", "agentic-skill-vendor", "verify"], "exit_code": 0}],
            "files": [{"path": "skills/ba0918-cycle/scripts/run.py", "content_identity": "sha256:" + "6" * 64}],
            **fields,
        }

    def test_a_check_records_the_commands_that_ran_and_the_files_they_covered(self) -> None:
        sealed = implement_model.seal_event(self._event())

        self.assertTrue(sealed.ok, sealed.error)

    def test_a_check_that_changed_no_file_is_still_evidence(self) -> None:
        sealed = implement_model.seal_event(self._event(files=[]))

        self.assertTrue(sealed.ok, sealed.error)

    def test_a_check_carrying_a_command_that_did_not_succeed_is_rejected(self) -> None:
        sealed = implement_model.seal_event(
            self._event(checks=[{"command": ["bunx", "agentic-skill-vendor", "verify"], "exit_code": 1}])
        )

        self.assertFalse(sealed.ok)

    def test_a_check_without_a_command_is_rejected(self) -> None:
        sealed = implement_model.seal_event(self._event(checks=[]))

        self.assertFalse(sealed.ok)


class CheckStepEvidenceTest(unittest.TestCase):
    @staticmethod
    def _events(*event_types: str) -> list[dict]:
        return [{"event_type": kind, "step_id": "step-1"} for kind in event_types]

    @staticmethod
    def _check(*paths: str) -> dict:
        return {
            "event_type": "check",
            "step_id": "step-1",
            "files": [{"path": path, "content_identity": "sha256:" + "7" * 64} for path in paths],
        }

    def test_a_check_step_is_complete_once_its_check_is_committed(self) -> None:
        events = [self._check("vendor-lock.json"), {"event_type": "commit", "step_id": "step-1"}]

        result = implement_model.validate_step_evidence(events, "step-1", "check")

        self.assertTrue(result.ok, result.error)

    def test_a_check_step_needs_no_human_approval(self) -> None:
        events = self._events("check", "commit")

        self.assertNotIn("approval", [event["event_type"] for event in events])
        result = implement_model.validate_step_evidence(events, "step-1", "check")

        self.assertTrue(result.ok, result.error)

    def test_a_check_that_changed_files_is_incomplete_until_they_are_committed(self) -> None:
        result = implement_model.validate_step_evidence([self._check("vendor-lock.json")], "step-1", "check")

        self.assertFalse(result.ok)

    def test_a_check_that_changed_nothing_completes_without_a_commit(self) -> None:
        result = implement_model.validate_step_evidence([self._check()], "step-1", "check")

        self.assertTrue(result.ok, result.error)

    def test_test_evidence_on_a_check_step_is_rejected(self) -> None:
        result = implement_model.validate_step_evidence(
            self._events("red", "green", "refactor", "check", "commit"), "step-1", "check"
        )

        self.assertFalse(result.ok)

    def test_a_check_inside_a_test_step_breaks_its_evidence(self) -> None:
        result = implement_model.validate_step_evidence(
            self._events("red", "green", "refactor", "check", "commit"), "step-1", "test"
        )

        self.assertFalse(result.ok)


class HumanGateStateTest(unittest.TestCase):
    def test_declared_human_gate_is_part_of_the_exact_binding(self) -> None:
        value = binding()
        value["human_gates"] = [human_gate()]

        result = implement_model.validate_binding(value)

        self.assertTrue(result.ok, result.error)

    def test_human_gate_event_must_match_a_declared_gate(self) -> None:
        value = binding()
        value["human_gates"] = [human_gate()]
        event = implement_model.seal_event(human_gate_event()).value

        declared = implement_model.validate_human_gate_event(value, event)
        ad_hoc = dict(event)
        ad_hoc["gate_id"] = "undeclared-gate"

        self.assertTrue(declared.ok, declared.error)
        self.assertEqual(
            implement_model.validate_human_gate_event(value, ad_hoc).error.code,
            "human_gate_undeclared",
        )

    def test_plan_without_human_gates_crosses_the_boundary(self) -> None:
        result = implement_model.validate_human_gate_boundary(
            binding(),
            [],
            step_id="step-1",
            timing="before_implementation_green",
            target_identities={},
        )

        self.assertTrue(result.ok, result.error)

    def test_missing_or_rejected_human_gate_blocks_the_boundary(self) -> None:
        value = binding()
        value["human_gates"] = [human_gate()]
        targets = {"approve-cycle-files": "sha256:" + "8" * 64}

        missing = implement_model.validate_human_gate_boundary(
            value,
            [],
            step_id="step-1",
            timing="before_implementation_green",
            target_identities=targets,
        )
        rejected = implement_model.validate_human_gate_boundary(
            value,
            [implement_model.seal_event(human_gate_event("rejected")).value],
            step_id="step-1",
            timing="before_implementation_green",
            target_identities=targets,
        )

        self.assertEqual(missing.error.code, "human_gate_missing")
        self.assertEqual(rejected.error.code, "human_gate_rejected")

    def test_changed_target_stales_a_previous_approval(self) -> None:
        value = binding()
        value["human_gates"] = [human_gate()]
        approved = implement_model.seal_event(human_gate_event()).value

        result = implement_model.validate_human_gate_boundary(
            value,
            [approved],
            step_id="step-1",
            timing="before_implementation_green",
            target_identities={"approve-cycle-files": "sha256:" + "9" * 64},
        )

        self.assertEqual(result.error.code, "human_gate_target_changed")

    def test_current_approval_crosses_the_declared_boundary(self) -> None:
        value = binding()
        value["human_gates"] = [human_gate()]
        approved = implement_model.seal_event(human_gate_event()).value

        result = implement_model.validate_human_gate_boundary(
            value,
            [approved],
            step_id="step-1",
            timing="before_implementation_green",
            target_identities={"approve-cycle-files": "sha256:" + "8" * 64},
        )

        self.assertTrue(result.ok, result.error)


class ResultDerivationTest(unittest.TestCase):
    def test_no_events_is_not_started(self) -> None:
        result = implement_model.derive_result([])

        self.assertEqual(result["state"], "not_started")
        self.assertNotIn("attempt_id", result)

    def test_stopped_result_comes_from_the_last_durable_event(self) -> None:
        stopped = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 1,
                "event_type": "stopped",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": None,
                "reason": "identity_drift",
                "step_id": "step-1",
            }
        ).value

        result = implement_model.derive_result([stopped])

        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["reason"], "identity_drift")
        self.assertEqual(result["last_sequence"], 1)

    def test_implementation_green_requires_the_terminal_event(self) -> None:
        terminal = implement_model.seal_event(
            {
                "version": 1,
                "sequence": 1,
                "event_type": "implementation_green",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": None,
                "commits": ["7" * 40],
            }
        ).value

        result = implement_model.derive_result([terminal])

        self.assertEqual(result["state"], "implementation_green")
        self.assertEqual(result["commits"], ["7" * 40])

    def test_event_count_never_changes_a_nonterminal_result_to_failure(self) -> None:
        events = []
        previous = None
        for sequence in range(1, 101):
            candidate = {
                "version": 1,
                "sequence": sequence,
                "event_type": "refactor",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": previous["content_identity"] if previous else None,
                "step_id": "step-1",
                "oracle_identity": implement_model.content_identity(oracle()),
                "outcome": "no_change",
                "exit_code": 0,
                "observation": "no structural change needed",
                "test_summary": {
                    "status": "unavailable",
                    "reason": "fixture has no structured runner output",
                },
            }
            previous = implement_model.seal_event(candidate, previous_event=previous).value
            events.append(previous)

        result = implement_model.derive_result(events)

        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["reason"], "terminal_event_missing")
        self.assertEqual(result["event_count"], 100)


class StepEvidenceRedoTest(unittest.TestCase):
    @staticmethod
    def _events(*event_types: str) -> list[dict]:
        return [{"event_type": kind, "step_id": "step-1"} for kind in event_types]

    def test_a_step_redone_from_red_counts_as_complete(self) -> None:
        events = self._events("red", "stopped", "red", "green", "refactor", "commit")
        self.assertTrue(implement_model.validate_step_evidence(events, "step-1", "test").ok)

    def test_a_redo_may_interrupt_any_unfinished_phase(self) -> None:
        for shape in (
            ("red", "green", "red", "green", "refactor", "commit"),
            ("red", "green", "refactor", "red", "green", "refactor", "commit"),
        ):
            result = implement_model.validate_step_evidence(self._events(*shape), "step-1", "test")
            self.assertTrue(result.ok, shape)

    def test_repeated_refactor_passes_still_complete_the_step(self) -> None:
        for shape in (
            ("red", "green", "refactor", "refactor", "commit"),
            ("red", "green", "refactor", "refactor", "refactor", "commit"),
        ):
            result = implement_model.validate_step_evidence(self._events(*shape), "step-1", "test")
            self.assertTrue(result.ok, shape)

    def test_a_rerun_green_before_refactor_still_completes_the_step(self) -> None:
        events = self._events("red", "green", "green", "refactor", "commit")
        self.assertTrue(implement_model.validate_step_evidence(events, "step-1", "test").ok)

    def test_a_commit_without_a_green_after_the_last_red_is_incomplete(self) -> None:
        events = self._events("red", "green", "red", "commit")
        self.assertFalse(implement_model.validate_step_evidence(events, "step-1", "test").ok)


NEW_PLAN_IDENTITY = "sha256:" + "5" * 64
NEW_SPEC_IDENTITY = "sha256:" + "6" * 64


def chain_event(sequence: int, event_type: str, previous: dict | None, **fields: object) -> dict:
    return {
        "version": 1,
        "sequence": sequence,
        "event_type": event_type,
        "attempt_id": binding()["attempt_id"],
        "plan_identity": PLAN_IDENTITY,
        "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
        "previous_identity": None if previous is None else previous["content_identity"],
        **fields,
    }


def rebound_event(sequence: int, previous: dict, **overrides: object) -> dict:
    event = chain_event(
        sequence,
        "rebound",
        previous,
        plan={
            "id": "20260822143915",
            "path": ".agents/artifacts/plans/20260822143915_cycle-r2.md",
            "revision": 2,
            "content_identity": NEW_PLAN_IDENTITY,
        },
        specs=[{"path": "docs/spec/cycle.md", "content_identity": NEW_SPEC_IDENTITY}],
        write_scope=["skills/ba0918-cycle", "tests/cycle_runtime_test.py", "docs/extra.md"],
        human_gates=[],
        step_map=[
            {"step_id": "step-1", "previous_step_id": "step-1", "disposition": "carry"},
            {"step_id": "step-2", "previous_step_id": None, "disposition": "new"},
            {"step_id": "step-3", "previous_step_id": "step-2", "disposition": "carry"},
        ],
        superseded_steps=["step-3"],
        head=BASE_HEAD,
        extra_commits=[],
        uncommitted_changes=False,
    )
    event["plan_identity"] = NEW_PLAN_IDENTITY
    event["spec_identities"] = {"docs/spec/cycle.md": NEW_SPEC_IDENTITY}
    event.update(overrides)
    return event


class ReboundChainTest(unittest.TestCase):
    def _bound(self) -> dict:
        return implement_model.seal_event(chain_event(1, "worktree-bound", None, outcome="bound")).value

    def test_a_rebound_changes_the_identities_and_later_events_must_follow_it(self) -> None:
        bound = self._bound()
        rebound = implement_model.seal_event(rebound_event(2, bound), previous_event=bound)
        self.assertIsNone(rebound.error)

        follower = chain_event(3, "stopped", rebound.value, reason="drift")
        follower["plan_identity"] = NEW_PLAN_IDENTITY
        follower["spec_identities"] = {"docs/spec/cycle.md": NEW_SPEC_IDENTITY}
        self.assertTrue(implement_model.seal_event(follower, previous_event=rebound.value).ok)

        stale = chain_event(3, "stopped", rebound.value, reason="drift")
        result = implement_model.seal_event(stale, previous_event=rebound.value)
        self.assertEqual(result.error.code, "stale_event_chain")

    def test_only_a_rebound_may_change_the_identities(self) -> None:
        bound = self._bound()
        drifted = chain_event(2, "stopped", bound, reason="drift")
        drifted["plan_identity"] = NEW_PLAN_IDENTITY
        result = implement_model.seal_event(drifted, previous_event=bound)
        self.assertEqual(result.error.code, "stale_event_chain")

    def test_rebound_identities_must_match_the_plan_and_specs_it_carries(self) -> None:
        bound = self._bound()
        wrong_plan = rebound_event(2, bound, plan_identity=PLAN_IDENTITY)
        self.assertFalse(implement_model.seal_event(wrong_plan, previous_event=bound).ok)
        wrong_spec = rebound_event(2, bound, spec_identities={"docs/spec/cycle.md": SPEC_IDENTITY})
        self.assertFalse(implement_model.seal_event(wrong_spec, previous_event=bound).ok)

    def test_a_rebound_may_follow_a_stop_but_not_implementation_green(self) -> None:
        bound = self._bound()
        stopped = implement_model.seal_event(chain_event(2, "stopped", bound, reason="drift"), previous_event=bound).value
        self.assertTrue(implement_model.seal_event(rebound_event(3, stopped), previous_event=stopped).ok)
        green = implement_model.seal_event(
            chain_event(2, "implementation_green", bound, commits=[BASE_HEAD]), previous_event=bound
        ).value
        result = implement_model.seal_event(rebound_event(3, green), previous_event=green)
        self.assertEqual(result.error.code, "terminal_event_chain")

    def test_a_history_approval_records_the_approved_lists(self) -> None:
        bound = self._bound()
        approval = chain_event(
            2,
            "history_approved",
            bound,
            unexplained_commits=[BASE_HEAD],
            out_of_scope_paths=["docs/notes.md"],
            uncommitted_out_of_scope=["scratch.txt"],
            reason="前セッションのバグ修正",
        )
        self.assertIsNone(implement_model.seal_event(approval, previous_event=bound).error)
        unsafe = dict(approval, out_of_scope_paths=["../outside.md"])
        self.assertFalse(implement_model.seal_event(unsafe, previous_event=bound).ok)


class EffectiveBindingTest(unittest.TestCase):
    def test_without_a_rebound_the_effective_binding_is_the_binding(self) -> None:
        events = [{"event_type": "worktree-bound"}, {"event_type": "stopped"}]
        self.assertEqual(implement_model.effective_binding(binding(), events), binding())

    def test_the_last_rebound_overlays_plan_specs_scope_and_gates(self) -> None:
        bound = implement_model.seal_event(chain_event(1, "worktree-bound", None, outcome="bound")).value
        rebound = implement_model.seal_event(rebound_event(2, bound), previous_event=bound).value
        effective = implement_model.effective_binding(binding(), [bound, rebound])
        self.assertEqual(effective["plan"], rebound["plan"])
        self.assertEqual(effective["specs"], rebound["specs"])
        self.assertEqual(effective["write_scope"], rebound["write_scope"])
        self.assertEqual(effective["human_gates"], rebound["human_gates"])
        self.assertEqual(effective["base_head"], binding()["base_head"])


class EffectiveEventsTest(unittest.TestCase):
    @staticmethod
    def _tdd(step_id: str, *event_types: str) -> list[dict]:
        return [{"event_type": kind, "step_id": step_id} for kind in event_types]

    def _rebound(self) -> dict:
        return {
            "event_type": "rebound",
            "step_map": [
                {"step_id": "step-1", "previous_step_id": "step-1", "disposition": "carry"},
                {"step_id": "step-2", "previous_step_id": None, "disposition": "new"},
                {"step_id": "step-3", "previous_step_id": "step-2", "disposition": "carry"},
            ],
            "superseded_steps": ["step-3"],
        }

    def test_without_a_rebound_the_events_are_unchanged(self) -> None:
        events = self._tdd("step-1", "red", "green", "refactor", "commit")
        self.assertEqual(implement_model.effective_events(events), events)

    def test_carried_steps_are_renumbered_and_superseded_evidence_is_dropped(self) -> None:
        before = (
            self._tdd("step-1", "red", "green", "refactor", "commit")
            + self._tdd("step-2", "red", "green", "refactor", "commit")
            + self._tdd("step-3", "red", "green", "refactor", "commit")
        )
        events = before + [self._rebound()] + self._tdd("step-2", "red")
        effective = implement_model.effective_events(events)

        self.assertTrue(implement_model.validate_step_evidence(effective, "step-1", "test").ok)
        self.assertTrue(implement_model.validate_step_evidence(effective, "step-3", "test").ok)
        self.assertFalse(implement_model.validate_step_evidence(effective, "step-2", "test").ok)
        self.assertEqual([event["step_id"] for event in effective if event.get("step_id") == "step-3"], ["step-3"] * 4)
        self.assertEqual(sum(1 for event in effective if event["event_type"] == "commit"), 2)
        self.assertEqual(effective[-1], {"event_type": "red", "step_id": "step-2"})
        self.assertEqual(len(before), 12)


if __name__ == "__main__":
    unittest.main()
