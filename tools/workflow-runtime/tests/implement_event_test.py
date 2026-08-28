from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime.events import EventCandidate, validate_event
from runtime.types import JsonObject


class ImplementEventTest(unittest.TestCase):
    def test_check_event_accepts_only_the_declared_commands(self) -> None:
        binding: JsonObject = {
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
        }
        result = validate_event(
            binding, [], EventCandidate("check", fields, "implement")
        )
        self.assertTrue(result.ok, result.error)

    def test_stopped_delegation_can_return_before_cycle_resumes_it(self) -> None:
        binding: JsonObject = {"delegated": True, "steps": []}
        events: list[JsonObject] = [{"event_type": "delegated"}]

        stopped = EventCandidate("stopped", {"reason": "human decision"}, "implement")
        self.assertTrue(validate_event(binding, events, stopped).ok)
        events.append({"event_type": "stopped", "reason": "human decision"})

        returned = EventCandidate("returned", {"outcome": "stopped"}, "cycle")
        self.assertTrue(validate_event(binding, events, returned).ok)
        events.append({"event_type": "returned", "outcome": "stopped"})

        resumed = EventCandidate("resumed", {}, "cycle")
        self.assertTrue(validate_event(binding, events, resumed).ok)
        events.append({"event_type": "resumed"})

        delegated = EventCandidate("delegated", {}, "cycle")
        self.assertTrue(validate_event(binding, events, delegated).ok)
        events.append({"event_type": "delegated"})

        continued = EventCandidate("recovering", {"reason": "continue"}, "implement")
        self.assertTrue(validate_event(binding, events, continued).ok)


if __name__ == "__main__":
    unittest.main()
