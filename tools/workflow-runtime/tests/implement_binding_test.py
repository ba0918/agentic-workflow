from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime.repository import bind_run
from runtime.types import JsonObject, ResolvedPlan


class ImplementBindingTest(unittest.TestCase):
    def test_binding_preserves_the_approved_step_contract(self) -> None:
        step: JsonObject = {"id": "1", "completion": "check", "checks": ["lint"]}
        plan = ResolvedPlan(
            "plan-a", "docs/plans/plan-a.md", "a" * 40, "plan", (), (), steps=(step,)
        )
        with tempfile.TemporaryDirectory() as directory:
            result = bind_run(
                Path(directory), plan, run_id="run-1", delegated=False
            )
        self.assertTrue(result.ok, result.error)


if __name__ == "__main__":
    unittest.main()
