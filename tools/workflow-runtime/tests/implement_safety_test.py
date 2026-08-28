from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime.safety import assess_safety
from runtime.types import JsonObject


class ImplementSafetyTest(unittest.TestCase):
    def test_safe_helper_needs_an_explicit_unplanned_reason(self) -> None:
        binding: JsonObject = {"expected_paths": ["src/app.py"]}

        missing = assess_safety(binding, ["tests/app_test.py"])
        explained = assess_safety(
            binding,
            ["tests/app_test.py"],
            {"tests/app_test.py": "behavior coverage"},
        )

        self.assertEqual(missing.error.code if missing.error is not None else None, "unplanned_reason_missing")
        self.assertTrue(explained.ok, explained.error)


if __name__ == "__main__":
    unittest.main()
