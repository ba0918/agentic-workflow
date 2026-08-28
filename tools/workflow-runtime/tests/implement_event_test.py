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


if __name__ == "__main__":
    unittest.main()
