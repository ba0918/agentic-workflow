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

    def __init__(self, parent: Path, *, last_event: str = "implementation_green"):
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
        self.plan_path.write_text("# Plan\n\n**Plan ID:** `20260823200534`\n", encoding="utf-8")
        (self.root / "app.py").write_text("def greet():\n    return 'hi'\n", encoding="utf-8")
        git(self.root, "add", ".gitignore", "docs/spec/feature.md", "app.py")
        git(self.root, "commit", "-q", "-m", "base")
        self.base_head = git(self.root, "rev-parse", "HEAD")

        self.worktree = parent / "linked-worktree"
        git(self.root, "worktree", "add", "-q", "-b", BRANCH, str(self.worktree), "main")
        (self.worktree / "app.py").write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
        git(self.worktree, "add", "app.py")
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
        with contextlib.redirect_stdout(stdout):
            code = self.runtime.main(list(argv))
        text = stdout.getvalue().strip()
        return code, (json.loads(text) if text else {})

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


if __name__ == "__main__":
    unittest.main()
