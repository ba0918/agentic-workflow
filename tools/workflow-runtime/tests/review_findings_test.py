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

    def test_targeted_review_execution_records_any_executed_operation_verbatim(self) -> None:
        operations = (
            "python3 tools/quality/quality_gate.py",
            "make test && rg foo",
            "python3 /abs/test.py",
            "python3 ../tools/check.py",
            "rg -n 'unclosed app.txt",
            "git reset --hard",
        )

        for operation in operations:
            with self.subTest(operation=operation):
                recorded = review_execution(operation, 1, "operation was executed")
                self.assertTrue(recorded.ok, recorded.error)
                self.assertEqual(recorded.required()["operation"], operation)

    def test_targeted_review_execution_rejects_empty_null_and_overlong_operations(self) -> None:
        malformed = ("", "   ", "pytest\x00", "p" * 2001)

        for operation in malformed:
            with self.subTest(operation=operation):
                rejected = review_execution(operation, 0, "operation was executed")
                self.assertEqual(rejected.required_error().code, "bounded_text_invalid")


if __name__ == "__main__":
    unittest.main()
