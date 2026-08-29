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
storage = importlib.import_module("runtime.storage")
from runtime.types import JsonObject, ResolvedPlan

PLAN = """# Plan

**Verification coverage:**

- `docs/spec/example.md` / `Contract` -> `1:check`

## Scope

```text
src/
  app.py
```

## Step 1: Validate the implementation

**Checks:**

- `lint`
"""

def plan_with_before_edit_gate() -> str:
    gate = {
        "version": 1,
        "gates": [{
            "gate_id": "approve-app",
            "sections": ["Contract"],
            "criterion": "May the implementation edit this file?",
            "target": {"kind": "files", "paths": ["src/app.py"]},
            "timing": "before_edit",
            "allowed_results": ["approved", "rejected"],
        }],
    }
    block = "\n\n**Human gates:**\n\n```json\n" + json.dumps(gate, indent=2) + "\n```"
    return PLAN + block

def resolved_plan(
    approval: str, *, expected_paths: tuple[str, ...] = (),
    steps: tuple[JsonObject, ...] = ({"id": "1", "completion": "check"},),
) -> ResolvedPlan:
    normalized_steps = tuple({
        **step,
        "checks": step.get("checks", ("check",)) if step.get("completion") == "check" else (),
    } for step in steps)
    return ResolvedPlan(
        "plan-a", "docs/plans/plan-a.md", approval, "text", (), expected_paths, steps=normalized_steps,
    )

class RepositoryFixture:
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


class ImplementPlanBindingTest(RepositoryFixture, unittest.TestCase):

    def test_resolves_a_committed_plan_without_manual_identity_fields(self) -> None:
        root = self.fixture()
        result = planning.resolve_plan(root, plan_path="docs/plans/example.md")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value.plan_key, "example")
        self.assertEqual(result.value.specifications[0].sections, ("Contract",))
        self.assertEqual(
            [(step.id, step.completion) for step in result.value.steps], [("1", "check")],
        )
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

    def test_unplanned_reasons_reject_surplus_entries(self) -> None:
        result = staging.assess_paths(
            ["src/app.py"], expected_paths=["src/app.py"], reasons={"src/app.py": "not unplanned"},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "unplanned_reason_extra")

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
        self.assertEqual(result.value["event_type"], "recovering")
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

class ImplementResumeTest(RepositoryFixture, unittest.TestCase):
    def test_discovery_summarizes_a_unique_run_without_resuming_it(self) -> None:
        root = self.fixture()
        approval = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        plan = resolved_plan(approval, steps=(
            {"id": "1", "completion": "check"}, {"id": "2", "completion": "check"},
        ))
        run = repository.bind_run(
            root, plan, run_id="run-1", delegated=False,
            branch=branch, worktree=str(root),
        ).value
        context.append_event(run, "check", {"step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": []})
        before = len(context.load_events(run).value)

        discovered = resume.discover_unfinished(root, "plan-a")

        self.assertTrue(discovered.ok, discovered.error)
        self.assertEqual(len(discovered.value), 1)
        summary = discovered.value[0]
        self.assertEqual(summary["run_id"], "run-1")
        self.assertEqual(summary["completed_steps"], ["1"])
        self.assertEqual(summary["remaining_steps"], ["2"])
        self.assertEqual(summary["branch"]["name"], branch)
        self.assertTrue(summary["worktree"]["registered"])
        self.assertIsNotNone(summary["started_at"])
        self.assertEqual(len(context.load_events(run).value), before)

        resumed = resume.resume_run(root, plan_key="plan-a", run_id="run-1")
        self.assertTrue(resumed.ok, resumed.error)
        self.assertEqual(resumed.value["run"].run_id, "run-1")
        self.assertEqual(resumed.value["resume_step"], "2")
        self.assertEqual(context.load_events(resumed.value["run"]).value[-1]["event_type"], "resumed")

    def test_discovery_shows_an_unexplained_commit_subject_exactly_as_written(self) -> None:
        root = self.fixture()
        approval = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        run = repository.bind_run(
            root, resolved_plan(approval), run_id="run-1", delegated=False,
            branch=branch, worktree=str(root),
        ).value
        context.append_event(run, "check", {
            "step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": [],
        })
        subject = "rotate the deploy " + "token=" + "example-rotated-value-123456"
        (root / "notes.txt").write_text("unexplained\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "notes.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", subject], check=True)

        discovered = resume.discover_unfinished(root, "plan-a")

        self.assertTrue(discovered.ok, discovered.error)
        self.assertEqual(
            [entry["subject"] for entry in discovered.value[0]["branch"]["unexplained_commits"]],
            [subject],
        )

    def test_retired_run_leaves_default_discovery_but_can_be_explicitly_resumed(self) -> None:
        root = self.fixture()
        approval = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        plan = resolved_plan(approval)
        run = repository.bind_run(
            root, plan, run_id="run-1", delegated=False,
            branch=branch, worktree=str(root),
        ).value

        retired = resume.retire_run(root, plan_key="plan-a", run_id="run-1", reason="start a replacement run")

        self.assertTrue(retired.ok, retired.error)
        self.assertEqual(resume.discover_unfinished(root, "plan-a").value, [])
        self.assertTrue(repository.load_run(root, "plan-a", "run-1").ok)
        self.assertTrue(resume.resume_run(root, plan_key="plan-a", run_id="run-1").ok)
        self.assertEqual(context.load_events(run).value[-1]["event_type"], "resumed")

    def test_delegated_returned_run_can_be_resumed_or_retired(self) -> None:
        for action in ("resume", "retire"):
            with self.subTest(action=action):
                root = self.fixture()
                approval = subprocess.run(
                    ["git", "-C", str(root), "rev-parse", "HEAD"],
                    text=True, capture_output=True, check=True,
                ).stdout.strip()
                branch = subprocess.run(
                    ["git", "-C", str(root), "branch", "--show-current"],
                    text=True, capture_output=True, check=True,
                ).stdout.strip()
                plan = resolved_plan(approval)
                run = repository.bind_run(
                    root, plan, run_id="run-1", delegated=True,
                    branch=branch, worktree=str(root),
                ).value
                self.assertTrue(context.append_event(run, "delegated", {"role": "implementer", "model": "claude-fable-5"}, actor="cycle").ok)
                self.assertTrue(context.append_event(run, "returned", {}, actor="cycle").ok)

                if action == "resume":
                    result = resume.resume_run(root, plan_key="plan-a", run_id="run-1")
                    expected_event = "resumed"
                else:
                    result = resume.retire_run(
                        root, plan_key="plan-a", run_id="run-1", reason="start replacement",
                    )
                    expected_event = "resume-candidate-retired"

                self.assertTrue(result.ok, result.error)
                self.assertEqual(context.load_events(run).value[-1]["event_type"], expected_event)

    def test_completed_run_is_not_discovered_as_unfinished(self) -> None:
        root = self.fixture()
        (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "ignore evidence"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True
        ).stdout.strip()
        plan = resolved_plan(commit)
        run = repository.bind_run(
            root, plan, run_id="run-1", delegated=False,
            branch=branch, worktree=str(root),
        ).value
        context.append_event(run, "check", {
            "step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": [],
        })
        self.assertTrue(context.complete_run(run).ok)
        self.assertEqual(resume.discover_unfinished(root, "plan-a").value, [])

    def test_legacy_resume_is_rejected_without_writing_an_event_or_status(self) -> None:
        root = Path(tempfile.mkdtemp())
        plan = resolved_plan("a" * 40)
        run = repository.bind_run(
            root, plan, run_id="run-1", delegated=False,
        ).value
        binding = storage.read_json(run.binding_path).value
        binding["version"] = 1
        run.binding_path.write_text(json.dumps(binding), encoding="utf-8")
        before = sorted(path.name for path in run.evidence_path.iterdir())
        result = resume.resume_run(root, plan_key="plan-a", run_id="run-1")
        self.assertEqual(result.error.code, "legacy_evidence_unsupported")
        self.assertEqual(sorted(path.name for path in run.evidence_path.iterdir()), before)

    def test_resume_cli_discovers_records_and_reports_the_resume_point(self) -> None:
        root = self.fixture()
        approval = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        plan = resolved_plan(approval)
        bound = repository.bind_run(
            root, plan, run_id="run-1", delegated=False, branch=branch, worktree=str(root),
        )
        self.assertTrue(bound.ok, bound.error)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main(["resume", "--repo", str(root), "--plan-key", "plan-a", "--run-id", "run-1"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["resume_step"], "1")

class ImplementCliTest(RepositoryFixture, unittest.TestCase):
    def test_resolve_cli_reports_each_changed_specification_as_commits_and_diff(self) -> None:
        root = self.fixture()
        approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        (root / "docs/spec/example.md").write_text("# Contract\n\nWording clarified\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "clarify wording"], check=True)
        current = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(["resolve", "--repo", str(root)]), 0)
        changes = json.loads(output.getvalue())["specification_changes"]

        self.assertEqual(len(changes), 1)
        self.assertEqual(set(changes[0]), {"path", "approval_commit", "current_commit", "diff"})
        self.assertEqual(changes[0]["path"], "docs/spec/example.md")
        self.assertEqual((changes[0]["approval_commit"], changes[0]["current_commit"]), (approval, current))
        self.assertIn("+Wording clarified", changes[0]["diff"])

    def test_resolve_cli_reports_no_specification_changes_when_specs_are_unchanged(self) -> None:
        root = self.fixture()

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(["resolve", "--repo", str(root)]), 0)

        self.assertEqual(json.loads(output.getvalue())["specification_changes"], [])

    def test_cli_records_only_the_declared_human_gate_result(self) -> None:
        root = self.fixture()
        plan_path = root / "docs/plans/example.md"
        plan_path.write_text(plan_with_before_edit_gate(), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/plans/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "human gate"], check=True)
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        selector = ["--repo", str(root), "--plan-key", "example", "--run-id", "run-1"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "bind", "--repo", str(root), "--plan-path", "docs/plans/example.md",
                "--run-id", "run-1", "--branch", branch, "--worktree", str(root),
            ]), 0)
            self.assertEqual(cli.main([
                "human-gate", *selector, "--step", "1", "--gate-id", "approve-app",
                "--result", "approved",
            ]), 0)
        run = repository.load_run(root, "example", "run-1").required()
        event = context.load_events(run).required()[-1]

        self.assertEqual(
            {key: event[key] for key in ("event_type", "step", "gate_id", "result")},
            {"event_type": "human_gate", "step": "1", "gate_id": "approve-app", "result": "approved"},
        )

    def test_before_edit_gate_rejects_an_already_modified_target(self) -> None:
        root = self.fixture()
        plan_path = root / "docs/plans/example.md"
        plan_path.write_text(plan_with_before_edit_gate(), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/plans/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "human gate"], check=True)
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "bind", "--repo", str(root), "--plan-path", "docs/plans/example.md",
                "--run-id", "run-1", "--branch", branch, "--worktree", str(root),
            ]), 0)
        (root / "src").mkdir()
        (root / "src/app.py").write_text("value = 1\n", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main([
                "human-gate", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
                "--step", "1", "--gate-id", "approve-app", "--result", "approved",
            ])
    def test_delegated_cli_records_runner_and_model_readable_from_current_status(self) -> None:
        root = self.fixture()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        selector = ["--repo", str(root), "--plan-key", "example", "--run-id", "run-1"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "bind", "--repo", str(root), "--plan-path", "docs/plans/example.md",
                "--run-id", "run-1", "--branch", branch, "--worktree", str(root), "--delegated",
            ]), 0)
            self.assertEqual(cli.main([
                "delegated", *selector, "--role", "codex", "--model", "claude-fable-5",
            ]), 0)
        run = repository.load_run(root, "example", "run-1").required()
        status = json.loads((run.evidence_path / "current-status").read_text(encoding="utf-8"))

        self.assertEqual(
            {key: status["last_event"].get(key) for key in ("event_type", "role", "model")},
            {"event_type": "delegated", "role": "codex", "model": "claude-fable-5"},
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["returned", *selector, "--outcome", "done"]), 0)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["delegated", *selector, "--model", "claude-fable-5"])

    def test_cli_resumes_a_stopped_delegation_after_cycle_returns_it(self) -> None:
        root = self.fixture()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        selector = ["--repo", str(root), "--plan-key", "example", "--run-id", "run-1"]

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main([
                "bind", "--repo", str(root), "--plan-path", "docs/plans/example.md",
                "--run-id", "run-1", "--branch", branch, "--worktree", str(root),
                "--delegated",
            ]), 0)
            self.assertEqual(cli.main(["delegated", *selector, "--role", "implementer", "--model", "claude-fable-5"]), 0)
            self.assertEqual(cli.main(["stop", *selector, "--reason", "human decision"]), 0)
            self.assertEqual(cli.main(["returned", *selector]), 0)
            self.assertEqual(cli.main(["resume", *selector]), 0)
            self.assertEqual(cli.main(["delegated", *selector, "--role", "implementer", "--model", "claude-fable-5"]), 0)
            self.assertEqual(cli.main([
                "stage", *selector, "--step", "1", "--phase", "check",
                "--command", "lint", "--exit-code", "0",
            ]), 0)

        run = repository.load_run(root, "example", "run-1").required()
        self.assertEqual(
            [event["event_type"] for event in context.load_events(run).required()],
            ["worktree-bound", "delegated", "stopped", "returned", "resumed", "delegated", "check"],
        )

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
             "--branch", branch, "--worktree", str(root)],
        ]
        for command in commands:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(command), 0)
        (root / "src").mkdir()
        (root / "src/app.py").write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "src/app.py"], check=True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(
                ["stage", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
                 "--step", "1", "--phase", "check", "--command", "lint", "--exit-code", "0"]
            ), 0)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "implement"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
        ).stdout.strip()
        commands = [
            ["record-commit", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
             "--step", "1", "--commit", commit],
            ["stop", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1", "--reason", "permission"],
            ["rebound", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
             "--approval-commit", commit, "--reason", "approved wording update",
             "--map", "1=1"],
        ]
        for command in commands:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(command), 0)
        run = repository.load_run(root, "example", "run-1").value
        self.assertEqual(
            [event["event_type"] for event in context.load_events(run).value],
            ["worktree-bound", "check", "commit", "stopped", "rebound"],
        )

    def test_cli_records_all_declared_check_commands_in_order(self) -> None:
        root = self.fixture()
        plan_path = root / "docs/plans/example.md"
        plan_path.write_text(PLAN.replace("- `lint`", "- `lint`\n- `test`"), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/plans/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "two checks"], check=True)
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "bind", "--repo", str(root), "--plan-path", "docs/plans/example.md",
                "--run-id", "run-1", "--branch", branch, "--worktree", str(root),
            ]), 0)
            self.assertEqual(cli.main([
                "stage", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
                "--step", "1", "--phase", "check",
                "--command", "lint", "--exit-code", "0",
                "--command", "test", "--exit-code", "0",
            ]), 0)
        run = repository.load_run(root, "example", "run-1").value
        self.assertEqual(
            context.load_events(run).value[-1]["checks"],
            [{"command": "lint", "exit_code": 0}, {"command": "test", "exit_code": 0}],
        )

    def test_bind_and_rebound_cli_reject_caller_step_contracts(self) -> None:
        root = self.fixture()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        selector = ["--repo", str(root), "--plan-path", "docs/plans/example.md", "--run-id", "run-1"]
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["bind", *selector, "--branch", branch, "--worktree", str(root), "--step", "1:check"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["bind", *selector, "--branch", branch, "--worktree", str(root)]), 0)
        approval = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main([
                "rebound", "--repo", str(root), "--plan-key", "example", "--run-id", "run-1",
                "--approval-commit", approval, "--reason", "same plan", "--step", "1:check", "--map", "1=1",
            ])

    def test_cli_accepts_exact_reasons_for_safe_unplanned_paths(self) -> None:
        root = self.fixture()
        (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "ignore evidence"], check=True)
        approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
        plan = resolved_plan(approval)
        bound = repository.bind_run(
            root, plan, run_id="run-1", delegated=False,
            branch=branch, worktree=str(root),
        )
        self.assertTrue(bound.ok, bound.error)
        (root / "helper.py").write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "helper.py"], check=True)
        selector = ["--repo", str(root), "--plan-key", "plan-a", "--run-id", "run-1"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "stage", *selector, "--step", "1", "--phase", "check", "--command", "check",
                "--exit-code", "0", "--unplanned-reason", "helper.py=required helper",
            ]), 0)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "helper"], check=True)
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "record-commit", *selector, "--step", "1", "--commit", commit,
                "--unplanned-reason", "helper.py=required helper",
            ]), 0)
            self.assertEqual(cli.main([
                "stage", *selector, "--step", "1", "--phase", "check", "--command", "check",
                "--exit-code", "0",
            ]), 0)
            self.assertEqual(cli.main(["complete", *selector]), 0)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main([
                "stage", *selector, "--step", "1", "--phase", "check", "--command", "lint",
                "--exit-code", "0", "--unplanned-reason", "helper.py=one",
                "--unplanned-reason", "helper.py=two",
            ])

class ImplementWorktreeSafetyTest(RepositoryFixture, unittest.TestCase):
    def test_completion_rejects_planned_dirty_paths_but_reports_safe_unplanned_dirty_paths(self) -> None:
        outside_root = self.fixture()
        approval = subprocess.run(
            ["git", "-C", str(outside_root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(outside_root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        plan = resolved_plan(approval, expected_paths=("src/app.py",))
        run = repository.bind_run(
            outside_root, plan, run_id="run-1", delegated=False,
            branch=branch, worktree=str(outside_root),
        ).value
        context.append_event(run, "check", {
            "step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": [],
        })
        (outside_root / "notes.txt").write_text("safe outside scope\n", encoding="utf-8")

        outside = context.complete_run(run)

        self.assertTrue(outside.ok, outside.error)
        self.assertEqual(outside.value["uncommitted_outside_scope"], ["notes.txt"])

        inside_root = self.fixture()
        approval = subprocess.run(
            ["git", "-C", str(inside_root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(inside_root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        run = repository.bind_run(
            inside_root, resolved_plan(approval, expected_paths=("src/app.py",)),
            run_id="run-1", delegated=False,
            branch=branch, worktree=str(inside_root),
        ).value
        context.append_event(run, "check", {
            "step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": [],
        })
        (inside_root / "src").mkdir()
        (inside_root / "src/app.py").write_text("planned but uncommitted\n", encoding="utf-8")

        inside = context.complete_run(run)

        self.assertFalse(inside.ok)
        self.assertEqual(inside.error.code, "planned_changes_uncommitted")

    def test_completion_reports_credential_shaped_changes_outside_the_planned_scope(self) -> None:
        root = self.fixture()
        approval = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        run = repository.bind_run(
            root, resolved_plan(approval, expected_paths=("src/app.py",)),
            run_id="run-1", delegated=False, branch=branch, worktree=str(root),
        ).value
        context.append_event(run, "check", {
            "step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": [],
        })
        (root / "notes.txt").write_text("=".join(["password", "example-password-123456"]) + "\n", encoding="utf-8")

        completed = context.complete_run(run)

        self.assertTrue(completed.ok, completed.error)
        self.assertEqual(completed.value["uncommitted_outside_scope"], ["notes.txt"])

    def test_uncommitted_rename_paths_are_parsed_exactly(self) -> None:
        root = self.fixture()
        (root / "safe.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "safe.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "tracked path"], check=True)
        approval = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        plan = resolved_plan(approval, expected_paths=("safe.txt",))
        run = repository.bind_run(
            root, plan, run_id="run-1", delegated=False,
            branch=branch, worktree=str(root),
        ).value
        self.assertTrue(context.append_event(run, "check", {
            "step": "1", "checks": [{"command": "check", "exit_code": 0}], "paths": [],
        }).ok)
        subprocess.run(["git", "-C", str(root), "mv", "safe.txt", "renamed.txt"], check=True)

        summary = resume.summary(run)
        completed = context.complete_run(run)

        self.assertTrue(summary.ok, summary.error)
        self.assertEqual(summary.value["worktree"]["uncommitted_paths"], ["renamed.txt", "safe.txt"])
        self.assertFalse(completed.ok)
        self.assertEqual(completed.error.code, "planned_changes_uncommitted")

    def test_porcelain_parser_keeps_both_copy_paths(self) -> None:
        git_status = importlib.import_module("git_status")

        paths = git_status.parse_porcelain_v1_z("C  copied.txt\0source.txt\0")

        self.assertEqual(paths, ["copied.txt", "source.txt"])

if __name__ == "__main__":
    unittest.main()
