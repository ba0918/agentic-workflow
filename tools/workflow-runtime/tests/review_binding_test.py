from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/review"))
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/shared"))
from review_support.binding import execution_binding, standalone_binding


class ReviewBindingTest(unittest.TestCase):
    def test_execution_binding_keeps_the_version_two_shape(self) -> None:
        commit = "a" * 40
        self.assertEqual(
            execution_binding("plan", "run", commit, implement_sequence=7),
            {
                "version": 2,
                "kind": "execution",
                "plan_key": "plan",
                "run_id": "run",
                "approval_commit": commit,
                "implement_sequence": 7,
                "branch": None,
                "head": None,
                "worktree": None,
            },
        )

    def test_standalone_binding_rejects_paths_outside_the_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe specification path"):
            standalone_binding(
                "review",
                base="a" * 40,
                head="b" * 40,
                spec_paths=["../spec.md"],
            )


if __name__ == "__main__":
    unittest.main()
