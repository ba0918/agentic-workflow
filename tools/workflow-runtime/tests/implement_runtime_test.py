import importlib
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_HOME = ROOT / "tools/workflow-runtime/implement"
sys.path.insert(0, str(RUNTIME_HOME))
planning = importlib.import_module("runtime.planning")
staging = importlib.import_module("runtime.staging")
context = importlib.import_module("runtime.context")
resume = importlib.import_module("runtime.resume")
cli = importlib.import_module("runtime.cli")
repository = importlib.import_module("runtime.repository")

PLAN = """# Plan

**Target specifications:**

- `docs/spec/example.md`
  - sections: `Contract`

## Scope

```text
src/
  app.py
```
"""

class ImplementPlanBindingTest(unittest.TestCase):
    def fixture(self) -> Path:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "docs/spec").mkdir(parents=True)
        (root / "docs/plans").mkdir(parents=True)
        (root / "docs/spec/example.md").write_text("# Contract\n", encoding="utf-8")
        (root / "docs/plans/example.md").write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md", "docs/plans/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "approved"], check=True)
        return root

    def test_resolves_a_committed_plan_without_manual_identity_fields(self) -> None:
        root = self.fixture()
        result = planning.resolve_plan(root, plan_path="docs/plans/example.md")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value.plan_key, "example")
        self.assertEqual(result.value.specifications[0].sections, ("Contract",))
        self.assertEqual(result.value.expected_paths, ("src/app.py",))

    def test_unique_plan_is_selected_automatically(self) -> None:
        root = self.fixture()
        result = planning.resolve_plan(root)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value.path, "docs/plans/example.md")

    def test_multiple_plans_require_an_explicit_path(self) -> None:
        root = self.fixture()
        (root / "docs/plans/other.md").write_text(PLAN, encoding="utf-8")
        result = planning.resolve_plan(root)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "plan_candidate_ambiguous")

    def test_resolve_returns_spec_versions_for_ai_meaning_decision(self) -> None:
        root = self.fixture()
        (root / "docs/spec/example.md").write_text("# Contract\n\nWording clarified\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "clarify wording"], check=True)
        result = planning.resolve_plan(root)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value.specification_changes[0].path, "docs/spec/example.md")
        self.assertIn("+Wording clarified", result.value.specification_changes[0].diff)

    def test_public_runtime_imports_without_legacy_plan_fields(self) -> None:
        module = importlib.import_module("implement_runtime")
        self.assertTrue(callable(module.resolve_plan))
        for path in (
            RUNTIME_HOME / "runtime/types.py",
            RUNTIME_HOME / "runtime/planning.py",
            RUNTIME_HOME / "runtime/repository.py",
            RUNTIME_HOME / "runtime/context.py",
            RUNTIME_HOME / "runtime/resume.py",
            RUNTIME_HOME / "runtime/cli.py",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("plan_identity", source)
            self.assertNotIn("plan_revision", source)
            self.assertNotIn("content_identity", source)

    def test_safe_unplanned_paths_are_reported_instead_of_rejected(self) -> None:
        result = staging.assess_paths(
            ["src/app.py", "tests/app_test.py"],
            expected_paths=["src/app.py"],
            reasons={"tests/app_test.py": "behavior needs coverage"},
        )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["unplanned"], [{"path": "tests/app_test.py", "reason": "behavior needs coverage"}])

    def test_unplanned_path_requires_a_reason(self) -> None:
        result = staging.assess_paths(["tests/app_test.py"], expected_paths=[])
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "unplanned_reason_missing")

    def test_safety_checks_apply_inside_and_outside_expected_paths(self) -> None:
        for expected in ([".env.production"], []):
            result = staging.assess_paths([".env.production"], expected_paths=expected, reasons={".env.production": "needed"})
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "dangerous_path")
        for path in ("run.log", "scratch.tmp", "node_modules/pkg/index.js", ".agents/evidence/x.json"):
            result = staging.assess_paths([path], expected_paths=[path])
            self.assertFalse(result.ok)

    def test_semantically_dangerous_paths_are_returned_for_human_judgment(self) -> None:
        result = staging.assess_paths(
            ["config/release.toml"],
            expected_paths=["config/release.toml"],
            dangerous_paths={"config/release.toml": "production deployment target"},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "human_judgment_required")

    def test_document_context_reports_git_facts_without_classifying_importance(self) -> None:
        result = context.document_context(
            {"approval_commit": "a" * 40}, "b" * 40, ["docs/spec/a.md", "docs/plans/p.md"]
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.value["approval_commit"], "a" * 40)
        self.assertNotIn("important", result.value)
        self.assertNotIn("verdict", result.value)

    def test_ai_can_follow_a_nonimportant_document_change(self) -> None:
        result = context.document_decision(
            current_commit="b" * 40,
            changed_documents=["docs/spec/a.md"],
            important=False,
            reason="wording only",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.value["event_type"], "documents-followed")
        self.assertEqual(result.value["current_commit"], "b" * 40)

    def test_important_document_change_returns_to_the_human(self) -> None:
        result = context.document_decision(
            current_commit="b" * 40,
            changed_documents=["docs/spec/a.md"],
            important=True,
            reason="persistence choice changed",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "rebound_or_new_run_required")

    def test_unique_unfinished_run_resumes_automatically(self) -> None:
        self.assertEqual(resume.select_unfinished([{"run_id": "one", "state": "active"}]).value["run_id"], "one")
        multiple = resume.select_unfinished([{"run_id": "one", "state": "active"}, {"run_id": "two", "state": "stopped"}])
        self.assertFalse(multiple.ok)
        self.assertEqual(multiple.error.code, "run_candidate_ambiguous")

    def test_discovers_and_resumes_the_unique_run_from_evidence(self) -> None:
        from runtime import repository
        from runtime.types import ResolvedPlan
        root = Path(tempfile.mkdtemp())
        plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
        run = repository.bind_run(
            root, plan, run_id="run-1", delegated=False,
            steps=[{"id": "1", "completion": "check"}, {"id": "2", "completion": "check"}],
        ).value
        context.append_event(run, "check", {"step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": []})
        context.record_commit(run, "1", "b" * 40)
        resumed = resume.resume_unique(
            root,
            plan_key="plan-a",
            branch_head="b" * 40,
            unexplained_commits=[],
            uncommitted_paths=[],
            consequential_change=False,
        )
        self.assertTrue(resumed.ok, resumed.error)
        self.assertEqual(resumed.value["run"].run_id, "run-1")
        self.assertEqual(resumed.value["resume_step"], "2")
        self.assertEqual(context.load_events(resumed.value["run"]).value[-1]["event_type"], "resumed")

    def test_completed_run_is_not_discovered_as_unfinished(self) -> None:
        from runtime import repository
        from runtime.types import ResolvedPlan
        root = Path(tempfile.mkdtemp())
        plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
        run = repository.bind_run(root, plan, run_id="run-1", delegated=False).value
        context.append_event(run, "implementation_green", {"completed_steps": []}, actor="implement", _derived=True)
        self.assertEqual(resume.discover_unfinished(root, "plan-a").value, [])

    def test_resume_cli_discovers_records_and_reports_the_resume_point(self) -> None:
        from runtime import repository
        from runtime.types import ResolvedPlan
        root = Path(tempfile.mkdtemp())
        plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
        repository.bind_run(root, plan, run_id="run-1", delegated=False, steps=["1"]).value
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main(["resume", "--repo", str(root), "--plan-key", "plan-a", "--branch-head", "b" * 40])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["resume_step"], "1")

    def test_cli_connects_binding_stage_commit_stop_and_rebound(self) -> None:
        root = self.fixture()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
        ).stdout.strip()
        commands = [
            ["bind", "--repo", str(root), "--plan-path", "docs/plans/example.md", "--run-id", "run-1",
             "--branch", branch, "--worktree", str(root), "--step", "1:check"],
            ["stage", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
             "--step", "1", "--phase", "check", "--command", "lint", "--exit-code", "0"],
            ["record-commit", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
             "--step", "1", "--commit", commit],
            ["stop", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1", "--reason", "permission"],
            ["rebound", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
             "--approval-commit", commit, "--reason", "approved wording update"],
        ]
        for command in commands:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(command), 0)
        run = repository.load_run(root, "example", "run-1").value
        self.assertEqual(
            [event["event_type"] for event in context.load_events(run).value],
            ["worktree-bound", "check", "commit", "stopped", "rebound"],
        )

if __name__ == "__main__":
    unittest.main()
