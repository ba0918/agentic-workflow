import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "tools/workflow-runtime/review/review_model.py"
MODEL_SPEC = importlib.util.spec_from_file_location("review_model", MODEL_PATH)
review_model = importlib.util.module_from_spec(MODEL_SPEC)
assert MODEL_SPEC.loader is not None
MODEL_SPEC.loader.exec_module(review_model)
sys.modules["review_model"] = review_model
RUNTIME_PATH = ROOT / "tools/workflow-runtime/review/review_runtime.py"
RUNTIME_SPEC = importlib.util.spec_from_file_location("review_runtime", RUNTIME_PATH)
runtime = importlib.util.module_from_spec(RUNTIME_SPEC)
assert RUNTIME_SPEC.loader is not None
RUNTIME_SPEC.loader.exec_module(runtime)

def finding(**changes) -> dict:
    value = {
        "severity": "critical", "action": "fix_and_verify",
        "specification": {"path": "docs/spec/review.md", "section": "finding"},
        "evidence": {"path": "app.txt", "observation": "wrong"},
        "oracle": "test -f fixed", "oracle_status": "failing", "root_cause": "logic",
        "state": "open", "spec_commit": "a" * 40, "profile": "default",
    }
    value.update(changes)
    value["id"] = review_model.finding_id(value)
    return value

class ReviewRuntimeTest(unittest.TestCase):
    def repository(self) -> tuple[Path, str, str]:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
        (root / "docs/spec").mkdir(parents=True)
        (root / "docs/spec/review.md").write_text("# Review\n", encoding="utf-8")
        (root / "app.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", ".gitignore", "docs/spec/review.md", "app.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
        base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", str(root), "switch", "-qc", "feature"], check=True)
        (root / "app.txt").write_text("feature\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "feature"], check=True)
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        return root, base, head

    def execution_fixture(self) -> tuple[Path, str, str]:
        root, base, head = self.repository()
        store = root / ".agents/evidence/plan-a/run-1"
        store.mkdir(parents=True)
        binding = {
            "version": 1, "plan_key": "plan-a", "run_id": "run-1", "approval_commit": base,
            "branch": "feature", "worktree": str(root),
            "steps": [{"id": "1", "completion": "check"}],
        }
        (store / "binding.json").write_text(json.dumps(binding), encoding="utf-8")
        events = [
            {"sequence": 1, "event_type": "worktree-bound", "branch": "feature", "worktree": str(root)},
            {"sequence": 2, "event_type": "check", "step": "1", "checks": [{"command": "lint", "exit_code": 0}]},
            {"sequence": 3, "event_type": "commit", "step": "1", "commit": head},
            {"sequence": 4, "event_type": "safety-check", "passed": True, "summary": "safe"},
            {"sequence": 5, "event_type": "implementation_green", "completed_steps": ["1"]},
        ]
        for event in events:
            (store / f"{event['sequence']:06d}-{event['event_type']}.json").write_text(json.dumps(event), encoding="utf-8")
        return root, base, head

    def test_resolves_real_branch_commits_and_implementation_run(self) -> None:
        root, base, head = self.execution_fixture()
        execution = runtime.resolve_input(root, review_id="exec", plan_key="plan-a", run_id="run-1")
        branch = runtime.resolve_input(root, review_id="branch", branch="feature", base="main")
        commits = runtime.resolve_input(root, review_id="commits", base=base, head=head)
        self.assertTrue(all(result.ok for result in (execution, branch, commits)))
        self.assertEqual({runtime.input_kind(result.value) for result in (execution, branch, commits)}, {"execution", "branch", "commits"})
        self.assertEqual(branch.value["input"]["base"], base)
        self.assertEqual(branch.value["input"]["head"], head)

    def test_rejects_imaginary_branch_sha_and_incomplete_implementation_evidence(self) -> None:
        root, base, head = self.execution_fixture()
        self.assertEqual(runtime.resolve_input(root, review_id="bad", branch="missing", base="main").error.code, "branch_not_found")
        self.assertEqual(runtime.resolve_input(root, review_id="bad", base="f" * 40, head=head).error.code, "commit_not_found")
        green = root / ".agents/evidence/plan-a/run-1/000005-implementation_green.json"
        green.unlink()
        self.assertEqual(
            runtime.resolve_input(root, review_id="bad", plan_key="plan-a", run_id="run-1").error.code,
            "implementation_incomplete",
        )

    def test_branch_base_uses_explicit_then_pr_then_unique_default(self) -> None:
        root, base, _ = self.repository()
        explicit = runtime.resolve_input(root, review_id="one", branch="feature", base="main")
        pull_request = runtime.resolve_input(root, review_id="two", branch="feature", pull_request_target="main")
        default = runtime.resolve_input(root, review_id="three", branch="feature")
        self.assertEqual([item.value["input"]["base"] for item in (explicit, pull_request, default)], [base, base, base])

    def test_empty_findings_cannot_fake_initial_final_and_completion(self) -> None:
        root, _, _ = self.repository()
        binding = runtime.resolve_input(root, review_id="review-1", branch="feature", base="main").value
        self.assertTrue(runtime.bind_review(root, binding, model="model-x").ok)
        initial = runtime.begin_stage(root, binding, reviewer_context="reviewer-initial")
        self.assertEqual(initial.value["event_type"], "initial-full-review-started")
        self.assertEqual(runtime.begin_stage(root, binding, reviewer_context="same").error.code, "stage_results_required")
        self.assertTrue(runtime.record_findings(
            root, binding, stage="initial", findings=[], safety_check=True, reviewer_context="reviewer-initial",
        ).ok)
        final = runtime.begin_stage(root, binding, reviewer_context="reviewer-final")
        self.assertEqual(final.value["event_type"], "final-full-review-started")
        self.assertEqual(runtime.complete_review(root, binding).error.code, "final_results_required")
        self.assertTrue(runtime.record_findings(
            root, binding, stage="final", findings=[], safety_check=True, reviewer_context="reviewer-final",
        ).ok)
        completed = runtime.complete_review(root, binding)
        self.assertTrue(completed.ok, completed.error)
        self.assertEqual(completed.value["event_type"], "review-completed")

    def test_targeted_close_requires_trailer_and_progress_then_stale_can_rebound(self) -> None:
        root, _, _ = self.repository()
        binding = runtime.resolve_input(root, review_id="review-1", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="reviewer-initial")
        item = finding(spec_commit=binding["spec_commit"])
        self.assertTrue(runtime.record_findings(
            root, binding, stage="initial", findings=[item], safety_check=True, reviewer_context="reviewer-initial",
        ).ok)
        self.assertEqual(runtime.begin_stage(root, binding, reviewer_context="reviewer-targeted").value["event_type"], "targeted-review-started")
        (root / "fixed").write_text("fixed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "fixed"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", f"fix finding\n\nFinding: {item['id']}"], check=True)
        fix_commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        closed = runtime.close_finding(root, binding, item["id"], oracle_exit_code=0, fix_commits=[fix_commit])
        self.assertTrue(closed.ok, closed.error)
        self.assertTrue(runtime.record_progress(root, binding, before=[item], after=[{**item, "state": "closed"}]).ok)
        self.assertTrue(runtime.mark_stale(root, binding, reason="important spec change").ok)
        self.assertEqual(runtime.begin_stage(root, binding, reviewer_context="blocked").error.code, "findings_stale")
        self.assertTrue(runtime.rebound_findings(root, binding, spec_commit=fix_commit, reason="human approved revision").ok)

    def test_dynamic_findings_and_stalled_progress_are_runtime_events(self) -> None:
        root, _, _ = self.repository()
        binding = runtime.resolve_input(root, review_id="review-1", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="reviewer-initial")
        original = finding(spec_commit=binding["spec_commit"])
        runtime.record_findings(
            root, binding, stage="initial", findings=[original], safety_check=True,
            reviewer_context="reviewer-initial",
        )
        related = finding(severity="warn", oracle="related", spec_commit=binding["spec_commit"])
        unrelated = finding(severity="warn", oracle="unrelated", spec_commit=binding["spec_commit"])
        added = runtime.add_findings(root, binding, candidates=[related, unrelated], related_ids={related["id"]})
        self.assertEqual([item["id"] for item in added.value["findings"]], [related["id"]])
        self.assertEqual([item["id"] for item in added.value["terminal_observations"]], [unrelated["id"]])
        actions = [
            runtime.record_progress(root, binding, before=[original], after=[original]).value["next_action"]
            for _ in range(3)
        ]
        self.assertEqual(actions, ["diagnose", "change_method", "human_judgment"])

    def test_cli_binds_real_branch_and_starts_initial_review(self) -> None:
        root, _, _ = self.repository()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = runtime.main([
                "bind", "--repo", str(root), "--review-id", "review-1", "--branch", "feature",
                "--base", "main", "--spec-path", "docs/spec/", "--model", "model-x",
                "--reviewer-context", "reviewer-initial",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["input"]["input"]["kind"], "branch")
        self.assertEqual(payload["stage"]["event_type"], "initial-full-review-started")

    def test_full_review_is_repeated_for_scope_topology(self) -> None:
        self.assertFalse(runtime.requires_full_review({"paths"}))
        self.assertTrue(runtime.requires_full_review({"scope_topology"}))

if __name__ == "__main__":
    unittest.main()
