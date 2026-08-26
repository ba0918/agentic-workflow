import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "tools/workflow-runtime/review/review_model.py"
MODEL_SPEC = importlib.util.spec_from_file_location("review_model", MODEL_PATH)
review_model = importlib.util.module_from_spec(MODEL_SPEC)
assert MODEL_SPEC.loader is not None
MODEL_SPEC.loader.exec_module(review_model)
import sys
sys.modules["review_model"] = review_model
RUNTIME_PATH = ROOT / "tools/workflow-runtime/review/review_runtime.py"
RUNTIME_SPEC = importlib.util.spec_from_file_location("review_runtime", RUNTIME_PATH)
runtime = importlib.util.module_from_spec(RUNTIME_SPEC)
assert RUNTIME_SPEC.loader is not None
RUNTIME_SPEC.loader.exec_module(runtime)

class ReviewRuntimeTest(unittest.TestCase):
    def test_execution_review_uses_the_implementation_evidence_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = runtime.execution_binding("plan-a", "run-1", "a" * 40, implement_sequence=7)
            path = runtime.review_directory(root, binding)
            self.assertEqual(path.relative_to(root).as_posix(), ".agents/evidence/plan-a/run-1/review")

    def test_standalone_branch_and_commit_range_bindings_have_their_own_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for binding in (
                runtime.standalone_binding("review-1", branch="feature", base="a" * 40, head="b" * 40, spec_paths=["docs/spec/"]),
                runtime.standalone_binding("review-2", base="a" * 40, head="b" * 40, spec_paths=["docs/spec/review.md"]),
            ):
                path = runtime.review_directory(root, binding)
                self.assertEqual(path.parent.relative_to(root).as_posix(), ".agents/evidence/reviews")

    def test_events_are_append_only_numbered_json_without_identity_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = runtime.standalone_binding("review-1", base="a" * 40, head="b" * 40, spec_paths=["docs/spec/"])
            runtime.append_event(root, binding, "review-bound", {"model": "model-x"})
            event = runtime.append_event(root, binding, "findings_stale", {"reason": "important spec change"})
            self.assertEqual(event.value["sequence"], 2)
            self.assertNotIn("identity", str(event.value))
            self.assertEqual([p.name for p in sorted(runtime.review_directory(root, binding).glob("*.json"))], [
                "000001-review-bound.json", "000002-findings_stale.json"
            ])

if __name__ == "__main__":
    unittest.main()
