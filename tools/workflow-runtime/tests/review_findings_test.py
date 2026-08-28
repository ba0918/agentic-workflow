from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/review"))
from review_support.validation import review_execution


class ReviewFindingsTest(unittest.TestCase):
    def test_targeted_review_execution_records_a_local_test(self) -> None:
        result = review_execution("python3 -m unittest tests.review_test", 1, "still failing")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.required()["working_directory"], ".")

    def test_targeted_review_execution_rejects_a_destructive_command(self) -> None:
        result = review_execution("git reset --hard", 1, "not executed")
        self.assertEqual(result.required_error().code, "review_operation_unsafe")


if __name__ == "__main__":
    unittest.main()
