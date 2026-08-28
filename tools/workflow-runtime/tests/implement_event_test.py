from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime.events import EventCandidate, derive_implementation, validate_event
from runtime.types import JsonObject


class ImplementEventTest(unittest.TestCase):
    def test_stage_kind_mismatch_keeps_the_public_error_code(self) -> None:
        binding: JsonObject = {
            "version": 2,
            "delegated": False,
            "steps": [{"id": "1", "completion": "artifact"}],
        }
        candidate = EventCandidate("check", {
            "step": "1",
            "checks": [{"command": "lint", "exit_code": 0}],
            "changed_paths": [],
        }, "implement")

        result = validate_event(binding, [], candidate)

        self.assertEqual(result.required_error().code, "stage_invalid")

    def test_candidate_and_reloaded_history_use_the_same_transition_verdict(self) -> None:
        binding: JsonObject = {
            "version": 2,
            "approval_commit": "a" * 40,
            "delegated": False,
            "steps": [{"id": "1", "completion": "artifact"}],
        }
        fields: JsonObject = {
            "step": "1", "checks": [], "paths": [], "changed_paths": [],
            "safety": {"paths": [], "unplanned": []},
        }
        candidate = EventCandidate("artifact", fields, "implement")
        event: JsonObject = {
            "version": 2, "sequence": 1, "event_type": "artifact",
            "run_id": "run-1", "writer": "implement", **fields,
        }

        writer_result = validate_event(binding, [], candidate)
        reloaded_result = derive_implementation(binding, [event])

        self.assertEqual(writer_result.ok, reloaded_result.ok)

    def test_check_event_accepts_only_the_declared_commands(self) -> None:
        binding: JsonObject = {
            "version": 2,
            "delegated": False,
            "steps": [
                {"id": "1", "completion": "check", "checks": ["first", "second"]}
            ],
        }
        fields: JsonObject = {
            "step": "1",
            "checks": [
                {"command": "first", "exit_code": 0},
                {"command": "second", "exit_code": 0},
            ],
            "changed_paths": [],
        }
        result = validate_event(
            binding, [], EventCandidate("check", fields, "implement")
        )
        self.assertTrue(result.ok, result.error)

    def test_stopped_delegation_can_return_before_cycle_resumes_it(self) -> None:
        binding: JsonObject = {"version": 2, "delegated": True, "steps": []}
        events: list[JsonObject] = [
            {"version": 2, "sequence": 1, "event_type": "delegated"},
        ]

        stopped = EventCandidate("stopped", {"reason": "human decision"}, "implement")
        self.assertTrue(validate_event(binding, events, stopped).ok)
        events.append({
            "version": 2, "sequence": 2, "event_type": "stopped",
            "reason": "human decision",
        })

        returned = EventCandidate("returned", {"outcome": "stopped"}, "cycle")
        self.assertTrue(validate_event(binding, events, returned).ok)
        events.append({
            "version": 2, "sequence": 3, "event_type": "returned", "outcome": "stopped",
        })

        delegated_while_stopped = validate_event(
            binding, events, EventCandidate("delegated", {}, "cycle")
        )
        self.assertFalse(delegated_while_stopped.ok)
        self.assertEqual(
            delegated_while_stopped.required_error().code, "run_stopped"
        )

        resumed = EventCandidate("resumed", {
            "branch_head": "a" * 40, "unexplained_commits": [], "uncommitted_paths": [],
        }, "cycle")
        self.assertTrue(validate_event(binding, events, resumed).ok)
        events.append({
            "version": 2, "sequence": 4, "event_type": "resumed",
            "branch_head": "a" * 40, "unexplained_commits": [], "uncommitted_paths": [],
        })

        delegated = EventCandidate("delegated", {}, "cycle")
        self.assertTrue(validate_event(binding, events, delegated).ok)
        events.append({"version": 2, "sequence": 5, "event_type": "delegated"})

        continued = EventCandidate("recovering", {
            "current_commit": "a" * 40,
            "changed_documents": ["docs/spec/a.md"],
            "reason": "continue",
        }, "implement")
        self.assertTrue(validate_event(binding, events, continued).ok)


if __name__ == "__main__":
    unittest.main()
