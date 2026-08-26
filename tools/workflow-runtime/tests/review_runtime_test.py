import importlib.util
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
import json

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

    def test_comparison_base_uses_explicit_then_pull_request_then_default(self) -> None:
        self.assertEqual(runtime.choose_comparison_base(explicit="release", pull_request_target="main", default_branch="trunk").value, "release")
        self.assertEqual(runtime.choose_comparison_base(explicit=None, pull_request_target="main", default_branch="trunk").value, "main")
        self.assertEqual(runtime.choose_comparison_base(explicit=None, pull_request_target=None, default_branch="trunk").value, "trunk")
        self.assertEqual(runtime.choose_comparison_base(explicit=None, pull_request_target=None, default_branch=None).error.code, "comparison_base_required")

    def test_all_three_input_forms_enter_the_same_binding_contract(self) -> None:
        execution = runtime.execution_binding("plan-a", "run-1", "a" * 40, implement_sequence=7)
        branch = runtime.standalone_binding("review-1", branch="feature", base="a" * 40, head="b" * 40, spec_paths=["docs/spec/"])
        commits = runtime.standalone_binding("review-2", base="a" * 40, head="b" * 40, spec_paths=["docs/spec/review.md"])
        self.assertEqual({runtime.input_kind(value) for value in (execution, branch, commits)}, {"execution", "branch", "commits"})

    def test_full_review_is_repeated_only_when_review_topology_changes(self) -> None:
        self.assertFalse(runtime.requires_full_review({"paths"}))
        self.assertTrue(runtime.requires_full_review({"structure"}))
        self.assertTrue(runtime.requires_full_review({"specification"}))
        self.assertTrue(runtime.requires_full_review({"scope_topology"}))

    def test_resolves_all_inputs_and_starts_the_same_review_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            execution_store = root / ".agents/evidence/plan-a/run-1"
            execution_store.mkdir(parents=True)
            (execution_store / "binding.json").write_text(json.dumps({
                "plan_key": "plan-a", "run_id": "run-1", "approval_commit": "a" * 40
            }), encoding="utf-8")
            (execution_store / "000001-all-steps-complete.json").write_text("{}", encoding="utf-8")
            bindings = [
                runtime.resolve_input(root, review_id="exec-review", plan_key="plan-a", run_id="run-1"),
                runtime.resolve_input(root, review_id="branch-review", branch="feature", base="a" * 40, head="b" * 40, spec_paths=["docs/spec/"]),
                runtime.resolve_input(root, review_id="commit-review", base="a" * 40, head="b" * 40, spec_paths=["docs/spec/review.md"]),
            ]
            self.assertTrue(all(result.ok for result in bindings))
            self.assertEqual({runtime.input_kind(result.value) for result in bindings}, {"execution", "branch", "commits"})
            binding = bindings[1].value
            initial = runtime.begin_stage(root, binding, [])
            self.assertEqual(initial.value["event_type"], "initial-full-review")
            open_item = {"state": "open"}
            targeted = runtime.begin_stage(root, binding, [open_item])
            self.assertEqual(targeted.value["event_type"], "targeted-review")
            final = runtime.begin_stage(root, binding, [{"state": "closed"}])
            self.assertEqual(final.value["event_type"], "final-full-review")

    def test_cli_binds_branch_input_and_starts_initial_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = runtime.main([
                    "bind", "--repo", directory, "--review-id", "review-1", "--branch", "feature",
                    "--base", "a" * 40, "--head", "b" * 40, "--spec-path", "docs/spec/",
                ])
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["input"]["input"]["kind"], "branch")
            self.assertEqual(payload["stage"]["event_type"], "initial-full-review")

if __name__ == "__main__":
    unittest.main()
