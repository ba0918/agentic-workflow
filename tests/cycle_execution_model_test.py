import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
MODEL_MODULE = ROOT / "skills/ba0918-cycle/scripts/execution_model.py"
SPEC = importlib.util.spec_from_file_location("cycle_execution_model", MODEL_MODULE)
cycle_model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(cycle_model)


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
        "branch": "cycle/20260822t152244-a1b2c3d4",
        "write_scope": ["skills/ba0918-cycle", "tests/cycle_runtime_test.py"],
        "executor": {
            "executor": "codex",
            "backend": "unavailable",
            "session_id": "unavailable",
            "reason": "not exposed safely",
        },
    }


def oracle() -> dict:
    return {
        "version": 1,
        "step_id": "step-1",
        "clauses": ["CY-010"],
        "test_identity": "sha256:" + "5" * 64,
        "command": ["python3", "-m", "unittest", "tests/cycle_runtime_test.py"],
        "cwd": ".",
        "environment_names": [],
        "timeout_seconds": 30,
        "expected_failure_kind": "missing_behavior",
        "observed_failure_kind": "missing_behavior",
        "failure_signature": "AttributeError: resolve_plan",
    }


class CanonicalIdentityTest(unittest.TestCase):
    def test_mapping_order_does_not_change_content_identity(self) -> None:
        first = {"b": 2, "a": {"d": 4, "c": 3}}
        second = {"a": {"c": 3, "d": 4}, "b": 2}

        self.assertEqual(cycle_model.content_identity(first), cycle_model.content_identity(second))
        self.assertEqual(
            cycle_model.canonical_json(first),
            b'{"a":{"c":3,"d":4},"b":2}\n',
        )


class BindingValidationTest(unittest.TestCase):
    def test_complete_binding_is_accepted(self) -> None:
        result = cycle_model.validate_binding(binding())

        self.assertTrue(result.ok)
        self.assertIsNone(result.error)

    def test_identity_drift_names_the_changed_field(self) -> None:
        observed = binding()
        observed["base_head"] = "6" * 40

        result = cycle_model.validate_snapshot(binding(), observed)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "identity_drift")
        self.assertEqual(result.error.field, "base_head")

    def test_missing_step_or_oracle_is_rejected(self) -> None:
        missing_step = oracle()
        del missing_step["step_id"]
        missing_identity = oracle()
        del missing_identity["test_identity"]

        self.assertEqual(
            cycle_model.validate_oracle(missing_step).error.code,
            "oracle_field_missing",
        )
        self.assertEqual(
            cycle_model.validate_oracle(missing_identity).error.code,
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
            cycle_model.validate_oracle(unsafe_oracle).error.code,
            "secret_value_forbidden",
        )
        self.assertEqual(
            cycle_model.seal_event(unsafe_event).error.code,
            "raw_log_forbidden",
        )

    def test_untrusted_scalar_types_return_failures_instead_of_raising(self) -> None:
        invalid_binding = binding()
        invalid_binding["plan"]["id"] = 20260822143915
        invalid_oracle = oracle()
        invalid_oracle["test_identity"] = None

        binding_result = cycle_model.validate_binding(invalid_binding)
        oracle_result = cycle_model.validate_oracle(invalid_oracle)

        self.assertFalse(binding_result.ok)
        self.assertEqual(binding_result.error.code, "plan_binding_invalid")
        self.assertFalse(oracle_result.ok)
        self.assertEqual(oracle_result.error.code, "oracle_field_invalid")

    def test_generic_runner_summary_is_not_a_behavior_signature(self) -> None:
        invalid_oracle = oracle()
        invalid_oracle["failure_signature"] = "FAILED (errors=1)"

        result = cycle_model.validate_oracle(invalid_oracle)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "oracle_failure_signature_invalid")


class WriteScopeTest(unittest.TestCase):
    def test_descendant_and_exact_file_are_inside_scope(self) -> None:
        scopes = ["skills/ba0918-cycle", "tests/cycle_runtime_test.py"]

        self.assertTrue(cycle_model.validate_write_path("skills/ba0918-cycle/SKILL.md", scopes).ok)
        self.assertTrue(cycle_model.validate_write_path("tests/cycle_runtime_test.py", scopes).ok)

    def test_absolute_traversal_and_sibling_paths_are_rejected(self) -> None:
        scopes = ["skills/ba0918-cycle"]

        for candidate in (
            "/tmp/outside",
            "skills/ba0918-cycle/../../../outside",
            "skills/ba0918-cycle-old/file.py",
        ):
            with self.subTest(candidate=candidate):
                result = cycle_model.validate_write_path(candidate, scopes)
                self.assertFalse(result.ok)
                self.assertEqual(result.error.code, "write_scope_violation")


class EventChainTest(unittest.TestCase):
    def test_events_form_an_immutable_hash_chain(self) -> None:
        first = cycle_model.seal_event(
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
        second = cycle_model.seal_event(
            {
                "version": 1,
                "sequence": 2,
                "event_type": "red",
                "attempt_id": binding()["attempt_id"],
                "plan_identity": PLAN_IDENTITY,
                "spec_identities": {"docs/spec/cycle.md": SPEC_IDENTITY},
                "previous_identity": first.value["content_identity"],
                "step_id": "step-1",
                "oracle_identity": cycle_model.content_identity(oracle()),
                "outcome": "expected_failure",
                "exit_code": 1,
                "observation": "1 failed",
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
            cycle_model.event_identity(second.value),
            second.value["content_identity"],
        )

    def test_stale_sequence_and_previous_identity_are_rejected(self) -> None:
        previous = cycle_model.seal_event(
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

        result = cycle_model.seal_event(stale, previous_event=previous)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "stale_event_chain")

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

        result = cycle_model.seal_event(incomplete)

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
        sealed = cycle_model.seal_event(candidate).value

        self.assertTrue(cycle_model.compare_event_retry(sealed, sealed).ok)
        changed = dict(sealed)
        changed["reason"] = "persistence_unavailable"
        self.assertEqual(
            cycle_model.compare_event_retry(sealed, changed).error.code,
            "event_identity_collision",
        )


class ResultDerivationTest(unittest.TestCase):
    def test_no_events_is_not_started(self) -> None:
        result = cycle_model.derive_result([])

        self.assertEqual(result["state"], "not_started")
        self.assertNotIn("attempt_id", result)

    def test_stopped_result_comes_from_the_last_durable_event(self) -> None:
        stopped = cycle_model.seal_event(
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

        result = cycle_model.derive_result([stopped])

        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["reason"], "identity_drift")
        self.assertEqual(result["last_sequence"], 1)

    def test_implementation_green_requires_the_terminal_event(self) -> None:
        terminal = cycle_model.seal_event(
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

        result = cycle_model.derive_result([terminal])

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
                "oracle_identity": cycle_model.content_identity(oracle()),
                "outcome": "no_change",
                "observation": "no structural change needed",
            }
            previous = cycle_model.seal_event(candidate, previous_event=previous).value
            events.append(previous)

        result = cycle_model.derive_result(events)

        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["reason"], "terminal_event_missing")
        self.assertEqual(result["event_count"], 100)


if __name__ == "__main__":
    unittest.main()
