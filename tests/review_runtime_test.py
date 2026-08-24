import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
RUNTIME_MODULE = ROOT / "skills/ba0918-review/scripts/review_runtime.py"


def load_runtime():
    assert RUNTIME_MODULE.exists(), "review_runtime.py does not exist yet"
    spec = importlib.util.spec_from_file_location("review_runtime", RUNTIME_MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


def identity_of(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_identity(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


PLAN_ID = "20260823200534"
ATTEMPT_ID = "20260823t111228-8bc96e30"
BRANCH = f"implement/{ATTEMPT_ID}"


class Scenario:
    """A main checkout, an implement worktree, and hand-written implement evidence."""

    def __init__(
        self,
        parent: Path,
        *,
        last_event: str = "implementation_green",
        skill_change: bool = False,
        plan_text: str = "# Plan\n\n**Plan ID:** `20260823200534`\n",
    ):
        self.root = parent / "repository"
        self.root.mkdir()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "reviewer@example.invalid")
        git(self.root, "config", "user.name", "Review Scenario")
        (self.root / ".gitignore").write_text("/.agents/\n", encoding="utf-8")
        self.spec_path = self.root / "docs/spec/feature.md"
        self.spec_path.parent.mkdir(parents=True)
        self.spec_path.write_text("# Feature\n\n## Behaviour\n\nGreet.\n", encoding="utf-8")
        self.plan_path = self.root / f".agents/artifacts/plans/{PLAN_ID}_feature.md"
        self.plan_path.parent.mkdir(parents=True)
        self.plan_path.write_text(plan_text, encoding="utf-8")
        (self.root / "app.py").write_text("def greet():\n    return 'hi'\n", encoding="utf-8")
        git(self.root, "add", ".gitignore", "docs/spec/feature.md", "app.py")
        git(self.root, "commit", "-q", "-m", "base")
        self.base_head = git(self.root, "rev-parse", "HEAD")

        self.worktree = parent / "linked-worktree"
        git(self.root, "worktree", "add", "-q", "-b", BRANCH, str(self.worktree), "main")
        (self.worktree / "app.py").write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
        git(self.worktree, "add", "app.py")
        if skill_change:
            skill = self.worktree / "skills/demo/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# Demo skill\n", encoding="utf-8")
            git(self.worktree, "add", "skills/demo/SKILL.md")
        git(self.worktree, "commit", "-q", "-m", "step 1")
        self.step_commit = git(self.worktree, "rev-parse", "HEAD")

        self.evidence = self.root / f".agents/artifacts/executions/{PLAN_ID}/{ATTEMPT_ID}"
        self.evidence.mkdir(parents=True)
        self.binding = {
            "version": 1,
            "attempt_id": ATTEMPT_ID,
            "plan": {
                "id": PLAN_ID,
                "path": f".agents/artifacts/plans/{PLAN_ID}_feature.md",
                "revision": 1,
                "content_identity": file_identity(self.plan_path),
            },
            "specs": [
                {"path": "docs/spec/feature.md", "content_identity": file_identity(self.spec_path)}
            ],
            "repository_identity": "sha256:" + "4" * 64,
            "base_head": self.base_head,
            "branch": BRANCH,
            "worktree": str(self.worktree),
            "write_scope": ["app.py", "tests/app_test.py"],
            "human_gates": [],
            "executor": {
                "executor": "claude-code",
                "backend": "unavailable",
                "session_id": "unavailable",
                "reason": "not exposed safely",
            },
        }
        self.write_json(self.evidence / "binding.json", self.binding)
        self.profiles = parent / "profiles"
        self.profiles.mkdir()
        (self.profiles / "default.md").write_text("# default profile\n", encoding="utf-8")
        (self.profiles / "skill.md").write_text("# skill profile\n\nCovers: `skills/`\n", encoding="utf-8")
        self.events = []
        self.append_event("worktree-bound", {"outcome": "bound"})
        self.append_event("commit", {"step_id": "step-1", "commit_sha": self.step_commit, "outcome": "committed"})
        if last_event == "implementation_green":
            self.append_event("implementation_green", {"commits": [self.step_commit]})
        elif last_event == "stopped":
            self.append_event("stopped", {"reason": "unexpected_red"})

    def append_event(self, event_type: str, details: dict) -> dict:
        sequence = len(self.events) + 1
        previous = self.events[-1]["content_identity"] if self.events else None
        event = {
            "version": 1,
            "sequence": sequence,
            "event_type": event_type,
            "attempt_id": ATTEMPT_ID,
            "plan_identity": self.binding["plan"]["content_identity"],
            "spec_identities": {
                spec["path"]: spec["content_identity"] for spec in self.binding["specs"]
            },
            "previous_identity": previous,
            **details,
        }
        event["content_identity"] = identity_of(event)
        self.write_json(self.evidence / f"{sequence:06d}-{event_type}.json", event)
        self.events.append(event)
        return event

    @staticmethod
    def write_json(path: Path, value) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    def review_dir(self) -> Path:
        return self.evidence / "review"

    def review_events(self) -> list[dict]:
        if not self.review_dir().exists():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.review_dir().glob("0*.json"))
        ]

    def implement_files(self) -> dict[str, str]:
        return {
            path.name: file_identity(path)
            for path in self.evidence.iterdir()
            if path.is_file()
        }


class RuntimeCase(unittest.TestCase):
    def setUp(self):
        self.runtime = load_runtime()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)

    def run_cli(self, *argv: str) -> tuple[int, dict]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = self.runtime.main(list(argv))
            except SystemExit:
                self.fail(f"command {argv[0]} is not implemented")
        text = stdout.getvalue().strip()
        return code, (json.loads(text) if text else {})

    def command(self, scenario: Scenario, name: str, *extra: str) -> tuple[int, dict]:
        return self.run_cli(
            name,
            "--repo", str(scenario.root),
            "--plan-id", PLAN_ID,
            "--attempt-id", ATTEMPT_ID,
            *extra,
        )

    def write_findings(self, scenario: Scenario, findings: list, *, security_done: bool = True) -> Path:
        path = self.parent / "findings.json"
        path.write_text(
            json.dumps({"findings": findings, "security_check": {"completed": security_done}}),
            encoding="utf-8",
        )
        return path

    def bind(self, scenario: Scenario, *extra: str) -> tuple[int, dict]:
        return self.run_cli(
            "bind",
            "--repo", str(scenario.root),
            "--plan-id", PLAN_ID,
            "--attempt-id", ATTEMPT_ID,
            "--model", "claude-fable-5",
            "--model-source", "explicit",
            *extra,
        )


class BindTest(RuntimeCase):
    def test_a_green_execution_with_a_matching_worktree_starts_the_review_record(self):
        scenario = Scenario(self.parent)
        code, payload = self.bind(scenario)
        self.assertEqual(code, 0, payload)
        events = scenario.review_events()
        self.assertEqual([e["event_type"] for e in events], ["review-bound", "model-selected"])
        self.assertEqual(events[0]["implement_event_identity"], scenario.events[-1]["content_identity"])
        self.assertEqual(events[1]["model"], "claude-fable-5")
        self.assertEqual(events[1]["model_source"], "explicit")
        self.assertEqual(payload["review_id"], events[0]["review_id"])

    def test_an_execution_that_stopped_is_refused_before_anything_is_written(self):
        scenario = Scenario(self.parent, last_event="stopped")
        code, payload = self.bind(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "implementation_incomplete")
        self.assertEqual(scenario.review_events(), [])

    def test_a_plan_that_changed_after_implementation_is_refused(self):
        scenario = Scenario(self.parent)
        scenario.plan_path.write_text("# Plan (revised)\n", encoding="utf-8")
        code, payload = self.bind(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "plan_drift")
        self.assertEqual(scenario.review_events(), [])

    def test_a_specification_that_changed_after_implementation_is_refused(self):
        scenario = Scenario(self.parent)
        scenario.spec_path.write_text("# Feature\n\n## Behaviour\n\nWave.\n", encoding="utf-8")
        code, payload = self.bind(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "spec_drift")
        self.assertEqual(scenario.review_events(), [])

    def test_a_missing_worktree_is_refused(self):
        scenario = Scenario(self.parent)
        git(scenario.root, "worktree", "remove", "--force", str(scenario.worktree))
        code, payload = self.bind(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "worktree_missing")
        self.assertEqual(scenario.review_events(), [])

    def test_a_worktree_on_another_branch_is_refused(self):
        scenario = Scenario(self.parent)
        git(scenario.worktree, "checkout", "-q", "-b", "somewhere-else")
        code, payload = self.bind(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "branch_mismatch")
        self.assertEqual(scenario.review_events(), [])

    def test_an_unfinished_review_is_shown_and_not_restarted_without_the_human(self):
        scenario = Scenario(self.parent)
        first_code, _ = self.bind(scenario)
        self.assertEqual(first_code, 0)
        code, payload = self.bind(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "review_in_progress")
        self.assertEqual(payload["review"]["last_event"], "model-selected")
        self.assertEqual(len(scenario.review_events()), 2)
        continued_code, continued = self.bind(scenario, "--continue")
        self.assertEqual(continued_code, 0, continued)
        self.assertEqual(len(scenario.review_events()), 2)
        self.assertEqual(continued["review_id"], payload["review"]["review_id"])

    def test_a_model_alias_or_an_unknown_source_is_refused(self):
        scenario = Scenario(self.parent)
        code, payload = self.run_cli(
            "bind", "--repo", str(scenario.root), "--plan-id", PLAN_ID, "--attempt-id", ATTEMPT_ID,
            "--model", "opus", "--model-source", "explicit",
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "model_id_invalid")
        code, payload = self.run_cli(
            "bind", "--repo", str(scenario.root), "--plan-id", PLAN_ID, "--attempt-id", ATTEMPT_ID,
            "--model", "claude-fable-5", "--model-source", "guess",
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "model_source_invalid")
        self.assertEqual(scenario.review_events(), [])

    def test_the_implement_evidence_is_never_modified(self):
        scenario = Scenario(self.parent)
        before = scenario.implement_files()
        self.bind(scenario)
        self.assertEqual(scenario.implement_files(), before)


FAILING_ORACLE = {"kind": "command", "command": "python3 -c 'import sys; sys.exit(1)'", "cwd": "."}
PASSING_ORACLE = {"kind": "command", "command": "python3 -c 'pass'", "cwd": "."}


UNSET = object()


def finding(scenario: Scenario, *, oracle=UNSET, severity="warn", action="fix_and_verify", **overrides) -> dict:
    value = {
        "severity": severity,
        "action": action,
        "spec_refs": [{"path": "docs/spec/feature.md", "section": "Behaviour"}],
        "evidence": {"files": ["app.py"], "lines": [[1, 2]], "summary": "greeting is wrong"},
        "oracle": dict(FAILING_ORACLE) if oracle is UNSET else oracle,
        "oracle_unavailable_reason": None,
        "root_cause_key": "greeting",
        "state": "open",
        "spec_identities": {"docs/spec/feature.md": scenario.binding["specs"][0]["content_identity"]},
        "profile": "default",
    }
    value.update(overrides)
    return value


class InputsTest(RuntimeCase):
    def inputs(self, scenario: Scenario, *extra: str) -> tuple[int, dict]:
        return self.command(scenario, "inputs", "--profile-dir", str(scenario.profiles), *extra)

    def test_code_only_changes_select_the_default_profile(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        code, payload = self.inputs(scenario, "--level", "standard")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["profiles"], {"default": ["app.py"]})
        self.assertEqual(payload["level"], "standard")
        self.assertEqual(payload["base"], scenario.base_head)
        self.assertEqual(payload["head"], scenario.step_commit)

    def test_skill_documents_select_the_skill_profile_and_mixed_changes_select_both(self):
        scenario = Scenario(self.parent, skill_change=True)
        self.bind(scenario)
        code, payload = self.inputs(scenario, "--level", "standard")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["profiles"], {"default": ["app.py"], "skill": ["skills/demo/SKILL.md"]})

    def test_an_explicit_profile_overrides_the_automatic_choice(self):
        scenario = Scenario(self.parent, skill_change=True)
        self.bind(scenario)
        code, payload = self.inputs(scenario, "--level", "standard", "--profile", "skill")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["profiles"], {"skill": ["app.py", "skills/demo/SKILL.md"]})

    def test_a_new_profile_is_selected_for_its_declared_paths_without_a_script_change(self):
        scenario = Scenario(self.parent)
        guide = scenario.worktree / "docs/guide.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text("# Guide\n", encoding="utf-8")
        git(scenario.worktree, "add", "docs/guide.md")
        git(scenario.worktree, "commit", "-q", "-m", "docs change")
        (scenario.profiles / "docs.md").write_text("# docs profile\n\nCovers: `docs/`\n", encoding="utf-8")
        self.bind(scenario)
        code, payload = self.inputs(scenario, "--level", "standard")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["profiles"], {"default": ["app.py"], "docs": ["docs/guide.md"]})
        self.assertIn("docs", payload["profile_identities"])

    def test_a_diff_above_the_threshold_stops_and_no_threshold_does_not(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        code, payload = self.inputs(scenario, "--level", "standard", "--max-diff-lines", "1")
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "input_too_large")
        code, payload = self.inputs(scenario, "--level", "standard")
        self.assertEqual(code, 0, payload)

    def test_the_profile_files_are_reported_with_their_identities(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        code, payload = self.inputs(scenario, "--level", "light")
        self.assertEqual(code, 0, payload)
        self.assertEqual(
            payload["profile_identities"], {"default": file_identity(scenario.profiles / "default.md")}
        )


class RegisterTest(RuntimeCase):
    def register(self, scenario: Scenario, findings_path: Path, *extra: str) -> tuple[int, dict]:
        return self.command(
            scenario, "register", "--profile-dir", str(scenario.profiles), "--findings", str(findings_path), *extra
        )

    def test_findings_whose_oracle_fails_now_are_fixed_as_the_set(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        path = self.write_findings(scenario, [finding(scenario)])
        code, payload = self.register(scenario, path, "--level", "standard")
        self.assertEqual(code, 0, payload)
        self.assertEqual(len(payload["admitted"]), 1)
        fixed = scenario.review_events()[-1]
        self.assertEqual(fixed["event_type"], "findings-fixed")
        self.assertEqual(fixed["findings_identity"], payload["findings_identity"])
        self.assertEqual(fixed["model"], "claude-fable-5")
        self.assertEqual(fixed["model_source"], "explicit")
        self.assertEqual(fixed["level"], "standard")
        self.assertEqual(fixed["reviewed_paths"], ["app.py"])
        self.assertEqual(fixed["profile_identities"], {"default": file_identity(scenario.profiles / "default.md")})

    def test_a_finding_whose_oracle_already_passes_is_not_admitted(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        path = self.write_findings(
            scenario, [finding(scenario), finding(scenario, oracle=dict(PASSING_ORACLE))]
        )
        code, payload = self.register(scenario, path, "--level", "standard")
        self.assertEqual(code, 0, payload)
        self.assertEqual(len(payload["admitted"]), 1)
        self.assertEqual(payload["not_admitted"][0]["reason"], "oracle_already_passing")
        self.assertEqual(len(scenario.review_events()[-1]["findings"]), 1)

    def test_a_human_judgment_finding_is_admitted_without_running_anything(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        path = self.write_findings(
            scenario,
            [finding(scenario, action="human_judgment", oracle=None, oracle_unavailable_reason="taste")],
        )
        code, payload = self.register(scenario, path, "--level", "standard")
        self.assertEqual(code, 0, payload)
        self.assertEqual(len(payload["admitted"]), 1)

    def test_light_level_refuses_warn_findings(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        path = self.write_findings(scenario, [finding(scenario, severity="warn")])
        code, payload = self.register(scenario, path, "--level", "light")
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "level_excludes_severity")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "model-selected")

    def test_without_the_security_check_the_set_is_not_fixed_and_the_review_is_incomplete(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        path = self.write_findings(scenario, [finding(scenario)], security_done=False)
        code, payload = self.register(scenario, path, "--level", "standard")
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "security_check_incomplete")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "review-incomplete")

    def test_an_invalid_finding_is_refused_before_any_oracle_runs(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        path = self.write_findings(scenario, [finding(scenario, severity="blocker")])
        code, payload = self.register(scenario, path, "--level", "standard")
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "severity_invalid")

    def test_the_set_cannot_be_fixed_twice(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        path = self.write_findings(scenario, [finding(scenario)])
        self.register(scenario, path, "--level", "standard")
        code, payload = self.register(scenario, path, "--level", "standard")
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "findings_already_fixed")

    def test_unsafe_oracle_commands_are_refused(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        unsafe = [
            {"kind": "command", "command": "cat /etc/hostname", "cwd": "."},
            {"kind": "command", "command": "python3 ../outside.py", "cwd": "."},
            # The secret-shaped values in this file are assembled at runtime so its own bytes
            # never resemble a credential assignment under implement's staging scan.
            {"kind": "command", "command": "curl -H to" + "ken=abcdefgh1234 http://x", "cwd": "."},
        ]
        for oracle in unsafe:
            with self.subTest(command=oracle["command"]):
                path = self.write_findings(scenario, [finding(scenario, oracle=oracle)])
                code, payload = self.register(scenario, path, "--level", "standard")
                self.assertNotEqual(code, 0)
                self.assertEqual(payload["reason"], "oracle_command_unsafe")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "model-selected")


class SecondOpinionTest(RuntimeCase):
    def make_second_reviewer(self, *, exit_code: int = 0) -> tuple[Path, Path]:
        calls = self.parent / "calls.log"
        script = self.parent / "second.py"
        script.write_text(
            "import sys, pathlib\n"
            f"pathlib.Path({str(calls)!r}).open('a').write(sys.argv[1] + '\\n')\n"
            "print('second opinion: nothing found')\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )
        return script, calls

    def second_opinion(self, scenario: Scenario, script: Path, *extra: str) -> tuple[int, dict]:
        return self.command(
            scenario,
            "second-opinion",
            "--second-reviewer", "codex",
            "--second-model", "gpt-5.4",
            "--command", f"python3 {script}",
            *extra,
        )

    def test_the_package_holds_only_the_plan_and_the_diff_and_is_sent_once(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        script, calls = self.make_second_reviewer()
        code, payload = self.second_opinion(scenario, script)
        self.assertEqual(code, 0, payload)
        self.assertEqual(len(calls.read_text().splitlines()), 1)
        package = Path(calls.read_text().splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("**Plan ID:** `20260823200534`", package)
        self.assertIn("-    return 'hi'", package)
        self.assertNotIn("Greet.", package)
        self.assertNotIn("findings", package)
        self.assertEqual(Path(payload["output"]).read_text(encoding="utf-8").strip(), "second opinion: nothing found")

    def test_a_package_with_a_secret_shaped_value_is_not_sent(self):
        scenario = Scenario(
            self.parent, plan_text="# Plan\n\n**Plan ID:** `20260823200534`\n\nto" + "ken=abcdefgh12345678\n"
        )
        scenario.binding["plan"]["content_identity"] = file_identity(scenario.plan_path)
        scenario.write_json(scenario.evidence / "binding.json", scenario.binding)
        for path in scenario.evidence.glob("0*.json"):
            path.unlink()
        scenario.events = []
        scenario.append_event("worktree-bound", {"outcome": "bound"})
        scenario.append_event("implementation_green", {"commits": [scenario.step_commit]})
        self.bind(scenario)
        script, calls = self.make_second_reviewer()
        code, payload = self.second_opinion(scenario, script)
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["reason"], "secret_detected")
        self.assertFalse(calls.exists())

    def test_an_unavailable_second_reviewer_records_a_warning_and_does_not_stop(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        script, _ = self.make_second_reviewer(exit_code=3)
        code, payload = self.second_opinion(scenario, script)
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["warning"], "second_reviewer_unavailable")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "warning")


APP_FIXED_ORACLE = {
    "kind": "command",
    "command": 'python3 -c \'import sys; sys.exit(0 if "hola" in open("app.py").read() else 1)\'',
    "cwd": ".",
}


class ReverifyCase(RuntimeCase):
    def fixed_set(self, scenario: Scenario, findings: list) -> dict:
        self.bind(scenario)
        path = self.write_findings(scenario, findings)
        code, payload = self.command(
            scenario, "register", "--profile-dir", str(scenario.profiles),
            "--findings", str(path), "--level", "standard",
        )
        self.assertEqual(code, 0, payload)
        return payload

    def fix_commit(self, scenario: Scenario, trailers: list, *, path="app.py",
                   content="def greet():\n    return 'hola'\n") -> str:
        target = scenario.worktree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        git(scenario.worktree, "add", path)
        git(scenario.worktree, "commit", "-q", "-m", "fix: adjust\n\n" + "\n".join(trailers))
        return git(scenario.worktree, "rev-parse", "HEAD")

    def reverify(self, scenario: Scenario, *extra: str) -> tuple[int, dict]:
        return self.command(scenario, "reverify", *extra)

    def fixed_event_bytes(self, scenario: Scenario) -> bytes:
        target = next(path for path in scenario.review_dir().glob("*findings-fixed*"))
        return target.read_bytes()


class ReverifyTest(ReverifyCase):
    def test_a_passing_oracle_closes_and_a_failing_one_stays_open_with_a_count(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(
            scenario, [finding(scenario, oracle=dict(APP_FIXED_ORACLE)), finding(scenario)]
        )
        closing_id, failing_id = payload["admitted"]
        sha = self.fix_commit(scenario, [f"Finding: {closing_id}", f"Finding: {failing_id}"])
        code, result = self.reverify(scenario)
        self.assertEqual(code, 0, result)
        verdicts = {v["finding_id"]: v for v in result["verdicts"]}
        self.assertEqual(verdicts[closing_id]["state"], "closed")
        self.assertEqual(verdicts[failing_id]["state"], "open")
        self.assertEqual(verdicts[failing_id]["oracle_failures"], 1)
        event = scenario.review_events()[-1]
        self.assertEqual(event["event_type"], "reverify")
        self.assertEqual(event["commits"], [sha])

    def test_a_commit_without_a_finding_trailer_is_out_of_scope(self):
        scenario = Scenario(self.parent)
        self.fixed_set(scenario, [finding(scenario)])
        self.fix_commit(scenario, [])
        code, result = self.reverify(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "commit_without_finding_trailer")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "findings-fixed")

    def test_a_revised_specification_stales_the_findings_instead_of_closing(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(scenario, [finding(scenario, oracle=dict(APP_FIXED_ORACLE))])
        scenario.spec_path.write_text("# Feature\n\n## Behaviour\n\nWave.\n", encoding="utf-8")
        self.fix_commit(scenario, [f"Finding: {payload['admitted'][0]}"])
        code, result = self.reverify(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "findings_stale")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "findings_stale")

    def test_a_revised_specification_marks_each_open_finding_stale_in_the_terminal_event(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(scenario, [finding(scenario)])
        scenario.spec_path.write_text("# Feature\n\n## Behaviour\n\nWave.\n", encoding="utf-8")
        code, result = self.reverify(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "findings_stale")
        event = scenario.review_events()[-1]
        self.assertEqual(event["event_type"], "findings_stale")
        self.assertEqual(event["verdicts"], [{"finding_id": payload["admitted"][0], "state": "stale"}])

    def test_a_trailer_naming_a_finding_outside_the_set_is_refused(self):
        scenario = Scenario(self.parent)
        self.fixed_set(scenario, [finding(scenario)])
        self.fix_commit(scenario, ["Finding: cmd-0000000000000000"])
        code, result = self.reverify(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "finding_not_in_set")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "findings-fixed")

    def test_a_fix_outside_the_reviewed_paths_becomes_a_rereview_candidate(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(scenario, [finding(scenario)])
        before = self.fixed_event_bytes(scenario)
        self.fix_commit(scenario, [f"Finding: {payload['admitted'][0]}"], path="other.py", content="new = True\n")
        code, result = self.reverify(scenario)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["rereview_candidates"]["paths"], ["other.py"])
        kinds = [event["event_type"] for event in scenario.review_events()]
        self.assertIn("rereview-candidate", kinds)
        self.assertEqual(self.fixed_event_bytes(scenario), before)

    def test_failures_reaching_the_limit_escalate_to_human_judgment(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(scenario, [finding(scenario)])
        stubborn = payload["admitted"][0]
        self.fix_commit(scenario, [f"Finding: {stubborn}"], content="attempt = 1\n")
        code, result = self.reverify(scenario, "--max-failures", "2")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["human_decisions"], [])
        self.fix_commit(scenario, [f"Finding: {stubborn}"], content="attempt = 2\n")
        code, result = self.reverify(scenario, "--max-failures", "2")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["human_decisions"], [stubborn])
        verdicts = {v["finding_id"]: v for v in result["verdicts"]}
        self.assertEqual(verdicts[stubborn]["oracle_failures"], 2)
        code, result = self.command(scenario, "decide", "--finding", stubborn, "--result", "accepted")
        self.assertEqual(code, 0, result)
        self.assertEqual(scenario.review_events()[-1]["event_type"], "decision")

    def test_without_a_limit_the_count_grows_and_nothing_escalates(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(scenario, [finding(scenario)])
        self.fix_commit(scenario, [f"Finding: {payload['admitted'][0]}"], content="attempt = 1\n")
        code, result = self.reverify(scenario)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["human_decisions"], [])
        self.assertEqual(result["verdicts"][0]["oracle_failures"], 1)


class HumanDecisionTest(ReverifyCase):
    def test_a_human_judgment_finding_closes_only_by_decision(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(
            scenario,
            [finding(scenario, action="human_judgment", oracle=None, oracle_unavailable_reason="taste")],
        )
        judged = payload["admitted"][0]
        self.fix_commit(scenario, [f"Finding: {judged}"])
        code, result = self.reverify(scenario)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["human_decisions"], [judged])
        verdicts = {v["finding_id"]: v for v in result["verdicts"]}
        self.assertEqual(verdicts[judged]["state"], "open")
        code, result = self.command(scenario, "decide", "--finding", judged, "--result", "accepted")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["remaining_human_decisions"], [])
        event = scenario.review_events()[-1]
        self.assertEqual((event["event_type"], event["result"]), ("decision", "accepted"))

    def test_a_decision_on_a_machine_checked_finding_is_refused(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(scenario, [finding(scenario)])
        code, result = self.command(
            scenario, "decide", "--finding", payload["admitted"][0], "--result", "accepted"
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "transition_invalid")


class DeferTest(ReverifyCase):
    def defer(self, scenario: Scenario, findings: list, *extra: str) -> tuple[int, dict]:
        path = self.parent / "deferred.json"
        path.write_text(json.dumps({"findings": findings}), encoding="utf-8")
        return self.command(scenario, "defer", "--findings", str(path), *extra)

    def test_deferred_findings_are_recorded_apart_and_the_set_is_unchanged(self):
        scenario = Scenario(self.parent)
        self.fixed_set(scenario, [finding(scenario)])
        before = self.fixed_event_bytes(scenario)
        code, result = self.defer(scenario, [finding(scenario, oracle=dict(PASSING_ORACLE))])
        self.assertEqual(code, 0, result)
        self.assertEqual(len(result["deferred"]), 1)
        self.assertEqual(scenario.review_events()[-1]["event_type"], "deferred")
        self.assertEqual(self.fixed_event_bytes(scenario), before)

    def test_only_introduced_findings_that_fail_now_join_the_set(self):
        scenario = Scenario(self.parent)
        self.fixed_set(scenario, [finding(scenario)])
        code, result = self.defer(
            scenario,
            [
                finding(scenario, oracle=dict(APP_FIXED_ORACLE), root_cause_key="regression"),
                finding(scenario, oracle=dict(PASSING_ORACLE), root_cause_key="regression"),
            ],
            "--introduced",
        )
        self.assertEqual(code, 0, result)
        self.assertEqual(len(result["added"]), 1)
        self.assertEqual(result["not_added"][0]["reason"], "oracle_already_passing")
        event = scenario.review_events()[-1]
        self.assertEqual(event["event_type"], "findings-added")
        self.assertEqual(len(event["findings"]), 1)


class MergeTest(ReverifyCase):
    def merge(self, scenario: Scenario, findings: list) -> tuple[int, dict]:
        path = self.parent / "finishing.json"
        path.write_text(json.dumps({"findings": findings}), encoding="utf-8")
        return self.command(scenario, "merge", "--findings", str(path))

    def test_finishing_review_findings_that_fail_now_join_the_set_and_close_by_reverify(self):
        scenario = Scenario(self.parent)
        self.fixed_set(scenario, [finding(scenario)])
        code, result = self.merge(
            scenario,
            [
                finding(scenario, oracle=dict(APP_FIXED_ORACLE), root_cause_key="finishing"),
                finding(scenario, oracle=dict(PASSING_ORACLE), root_cause_key="finishing"),
            ],
        )
        self.assertEqual(code, 0, result)
        self.assertEqual(len(result["added"]), 1)
        self.assertEqual(result["not_added"][0]["reason"], "oracle_already_passing")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "findings-added")
        joined = result["added"][0]
        self.fix_commit(scenario, [f"Finding: {joined}"])
        code, result = self.reverify(scenario)
        self.assertEqual(code, 0, result)
        self.assertIn(joined, result["closed"])

    def test_merge_before_the_set_is_frozen_is_refused(self):
        scenario = Scenario(self.parent)
        self.bind(scenario)
        code, result = self.merge(scenario, [finding(scenario)])
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "findings_not_fixed")


class ReviewingContextGuardTest(ReverifyCase):
    def test_reverify_refuses_a_worktree_that_left_the_bound_branch(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(scenario, [finding(scenario)])
        self.fix_commit(scenario, [f"Finding: {payload['admitted'][0]}"])
        git(scenario.worktree, "checkout", "-q", "-b", "somewhere-else")
        code, result = self.reverify(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "branch_mismatch")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "findings-fixed")

    def test_reverify_refuses_uncommitted_changes_so_verdicts_attach_to_commits(self):
        scenario = Scenario(self.parent)
        self.fixed_set(scenario, [finding(scenario, oracle=dict(APP_FIXED_ORACLE))])
        (scenario.worktree / "app.py").write_text("def greet():\n    return 'hola'\n", encoding="utf-8")
        code, result = self.reverify(scenario)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "worktree_dirty")
        self.assertEqual(scenario.review_events()[-1]["event_type"], "findings-fixed")

    def test_decide_refuses_when_the_hand_off_no_longer_verifies(self):
        scenario = Scenario(self.parent)
        payload = self.fixed_set(
            scenario,
            [finding(scenario, action="human_judgment", oracle=None, oracle_unavailable_reason="taste")],
        )
        git(scenario.worktree, "checkout", "-q", "-b", "somewhere-else")
        code, result = self.command(scenario, "decide", "--finding", payload["admitted"][0], "--result", "accepted")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "branch_mismatch")


if __name__ == "__main__":
    unittest.main()
