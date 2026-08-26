from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/implement"))
from runtime import deps
from runtime import context, deliverables, gates, repository, secret_detect, storage, tdd
from runtime.types import ResolvedPlan

class ImplementDistributionTest(unittest.TestCase):
    def test_plan_reader_is_loaded_from_the_same_distribution(self) -> None:
        self.assertTrue(deps.PLAN_READER_PATH.is_file())
        self.assertEqual(deps.plan_artifact.PLAN_STORE.as_posix(), "docs/plans")

    def test_run_binds_to_approval_commit_under_agents_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ("src/app.py",))
            result = repository.bind_run(root, plan, run_id="run-1", delegated=True)
            self.assertTrue(result.ok, result.error)
            run = result.value
            self.assertEqual(run.evidence_path.relative_to(root).as_posix(), ".agents/evidence/plan-a/run-1")
            binding = storage.read_json(run.binding_path)
            self.assertEqual(binding.value["approval_commit"], "a" * 40)
            self.assertNotIn("identity", str(binding.value))

    def test_bind_validates_every_contract_before_creation_and_cleans_failed_initial_event(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            branch = subprocess.run(
                ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True
            ).stdout.strip()
            approval = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
            ).stdout.strip()
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", approval, "text", (), ())
            invalid = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "unknown"}], branch=branch, worktree=str(root),
            )
            self.assertFalse(invalid.ok)
            self.assertFalse((root / ".agents/evidence/plan-a/run-1").exists())
            with mock.patch("runtime.context.append_event", return_value=context.failure("write_failed", "failed")):
                failed = repository.bind_run(
                    root, plan, run_id="run-1", delegated=False,
                    steps=[{"id": "1", "completion": "check"}], branch=branch, worktree=str(root),
                )
            self.assertFalse(failed.ok)
            self.assertFalse((root / ".agents/evidence/plan-a/run-1").exists())
            retried = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "check"}], branch=branch, worktree=str(root),
            )
            self.assertTrue(retried.ok, retried.error)

    def test_events_are_numbered_append_only_without_a_hash_chain(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).value
            first = context.append_event(run, "delegated", {"role": "implementer"})
            second = context.append_event(run, "returned", {"outcome": "completed"})
            self.assertTrue(first.ok and second.ok)
            names = [path.name for path in sorted(run.evidence_path.glob("*.json"))]
            self.assertEqual(names, ["000001-delegated.json", "000002-returned.json", "binding.json"])
            self.assertTrue((run.evidence_path / "current-status").is_file())
            self.assertNotIn("identity", second.value)
            with self.assertRaises(FileExistsError):
                storage.write_once(first.value["path"], b"replacement")

    def test_direct_implementations_can_append_evidence(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=False).value
            result = context.append_event(run, "recovering", {"reason": "writer contract check"}, actor="implement")
            self.assertTrue(result.ok, result.error)
            blocked = context.append_event(run, "delegated", {}, actor="cycle")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.error.code, "writer_not_allowed")

    def test_cycle_cannot_write_implementation_evidence_during_delegation(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).value
            self.assertTrue(context.append_event(run, "delegated", {"role": "implementer"}, actor="cycle").ok)
            blocked = context.append_event(run, "recovering", {"reason": "not cycle evidence"}, actor="cycle")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.error.code, "writer_not_allowed")
            self.assertTrue(context.append_event(run, "recovering", {"reason": "implement evidence"}, actor="implement").ok)
            wrong_boundary_writer = context.append_event(run, "returned", {}, actor="implement")
            self.assertFalse(wrong_boundary_writer.ok)
            self.assertEqual(wrong_boundary_writer.error.code, "writer_not_allowed")
            self.assertTrue(context.append_event(run, "returned", {"outcome": "returned"}, actor="cycle").ok)

    def test_delegated_implement_cannot_write_before_delegation_starts(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).value
            blocked = context.append_event(run, "recovering", {"reason": "before delegation"}, actor="implement")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.error.code, "writer_not_allowed")

    def test_delegated_implement_cannot_write_after_delegation_finishes(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(root, plan, run_id="run-1", delegated=True).value
            self.assertTrue(context.append_event(run, "delegated", {}, actor="cycle").ok)
            self.assertTrue(context.append_event(run, "returned", {}, actor="cycle").ok)
            blocked = context.append_event(run, "recovering", {"reason": "after delegation"}, actor="implement")
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.error.code, "writer_not_allowed")

    def test_implementation_green_cannot_be_appended_or_faked(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "test"}],
            ).value
            result = context.append_event(run, "implementation_green", {}, actor="implement")
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "event_not_recordable")
            with self.assertRaises(TypeError):
                context.append_event(run, "implementation_green", {}, actor="implement", _derived=True)

    def test_empty_run_and_invalid_test_transition_cannot_complete(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            empty = repository.bind_run(
                root, plan, run_id="empty", delegated=False, steps=[],
            ).value
            self.assertEqual(context.complete_run(empty).error.code, "completion_invalid")
            (root / "tests").mkdir()
            (root / "tests/example_test.py").write_text("test bytes\n", encoding="utf-8")
            run = repository.bind_run(
                root, plan, run_id="ordered", delegated=False,
                steps=[{"id": "1", "completion": "test"}],
            ).value
            self.assertTrue(context.record_stage(
                run, "1", "red", command="test", exit_code=1, test_paths=["tests/example_test.py"],
            ).ok)
            self.assertTrue(context.record_stage(run, "1", "green", command="test", exit_code=0).ok)
            self.assertTrue(context.record_stage(
                run, "1", "red", command="new test", exit_code=1, test_paths=["tests/example_test.py"],
            ).ok)
            invalid = context.record_stage(run, "1", "refactor", command="new test", exit_code=0)
            self.assertFalse(invalid.ok)
            self.assertEqual(invalid.error.code, "transition_invalid")

    def test_stopped_run_accepts_only_resume_or_rebound_and_status_tracks_rebound(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", "a" * 40, "text", (), ())
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "check"}],
            ).value
            self.assertTrue(context.stop_run(run, "important decision").ok)
            blocked = context.append_event(
                run, "check", {"step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": []}
            )
            self.assertFalse(blocked.ok)
            rebound = context.rebound_run(run, "b" * 40, "approved revision")
            self.assertTrue(rebound.ok, rebound.error)
            status = json.loads((run.evidence_path / "current-status").read_text(encoding="utf-8"))
            self.assertEqual(status["plan"]["approval_commit"], "b" * 40)

    def test_completion_is_derived_from_step_commit_safety_and_clean_worktree(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "README.md").write_text("fixture\n", encoding="utf-8")
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            (root / "tests").mkdir()
            test_path = root / "tests/example_test.py"
            test_path.write_text("test bytes\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md", ".gitignore", "tests/example_test.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            branch = subprocess.run(
                ["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True
            ).stdout.strip()
            commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
            ).stdout.strip()
            plan = ResolvedPlan(
                "plan-a", "docs/plans/plan-a.md", commit, "text", (),
                ("README.md", ".gitignore", "tests/example_test.py"),
            )
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "test"}], branch=branch, worktree=str(root),
            ).value
            self.assertTrue(context.record_stage(
                run, "1", "red", command="test cmd", exit_code=1, test_paths=["tests/example_test.py"],
            ).ok)
            command_drift = context.record_stage(run, "1", "green", command="other cmd", exit_code=0)
            self.assertEqual(command_drift.error.code, "frozen_red_mismatch")
            test_path.write_text("changed fixture\n", encoding="utf-8")
            fixture_drift = context.record_stage(run, "1", "green", command="test cmd", exit_code=0)
            self.assertEqual(fixture_drift.error.code, "frozen_red_mismatch")
            test_path.write_text("test bytes\n", encoding="utf-8")
            self.assertTrue(context.record_stage(run, "1", "green", command="test cmd", exit_code=0).ok)
            self.assertTrue(context.record_stage(run, "1", "refactor", command="test cmd", exit_code=0).ok)
            (root / "README.md").write_text("implemented\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "implement"], check=True)
            implementation_commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
            ).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", implementation_commit).ok)
            completed = context.complete_run(run)
            self.assertTrue(completed.ok, completed.error)
            self.assertEqual(completed.value["event_type"], "implementation_green")
            status = json.loads((run.evidence_path / "current-status").read_text(encoding="utf-8"))
            self.assertEqual(status["completed_steps"], ["1"])
            self.assertEqual(status["last_event"]["event_type"], "implementation_green")

    def test_check_without_changed_paths_needs_no_commit(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", commit, "text", (), ())
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "check"}], branch=branch, worktree=str(root),
            ).value
            checked = context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            })
            self.assertTrue(checked.ok, checked.error)
            self.assertEqual(checked.value["changed_paths"], [])
            self.assertTrue(context.complete_run(run).ok)

    def test_dangerous_commit_path_cannot_be_recorded_or_completed(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", approval, "text", (), (".env.production",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "check"}], branch=branch, worktree=str(root),
            ).value
            (root / ".env.production").write_text("SECRET=value\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "-f", ".env.production"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "dangerous"], check=True)
            dangerous = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [".env.production"],
            })
            recorded = context.record_commit(run, "1", dangerous)
            self.assertFalse(recorded.ok)
            self.assertEqual(recorded.error.code, "dangerous_path")
            self.assertFalse(context.complete_run(run).ok)

    def test_secret_shaped_content_is_rejected_without_exposing_its_value(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"], text=True, capture_output=True, check=True).stdout.strip()
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", approval, "text", (), ("config.py",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "check"}], branch=branch, worktree=str(root),
            ).value
            for name in ("api_token", "TOKEN", "Secret", "CREDENTIAL"):
                with self.subTest(name=name):
                    fake_value = f"fake_{name.lower()}_value_123456789"
                    (root / "config.py").write_text(f"{name}={fake_value}\n", encoding="utf-8")
                    subprocess.run(["git", "-C", str(root), "add", "config.py"], check=True)
                    rejected = context.append_event(run, "check", {
                        "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": ["config.py"],
                    })
                    self.assertFalse(rejected.ok)
                    self.assertEqual(rejected.error.code, "secret_content")
                    self.assertNotIn(fake_value, str(rejected.error))

    def test_secret_detector_covers_credentials_and_private_key_headers(self) -> None:
        for assignment in (
            b"Api-Token=fake_api_token_value",
            b"TOKEN: fake_standalone_token",
            b"secret = fake_secret_value",
            b"CREDENTIAL=fake_credential_value",
            b"password=fake_password_value",
        ):
            with self.subTest(assignment=assignment.split(b"=", 1)[0]):
                self.assertTrue(secret_detect.contains_secret(assignment))
        self.assertTrue(secret_detect.contains_secret(b"-----BEGIN FAKE PRIVATE KEY-----\nnot-a-key"))
        self.assertFalse(secret_detect.contains_secret(b"password = os.environ['PASSWORD']"))

    def test_secret_content_in_commit_object_is_rejected_without_value_exposure(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", approval, "text", (), ("config.py",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "check"}], branch="main", worktree=str(root),
            ).value
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            fake_value = "fake_commit_token_123456789"
            (root / "config.py").write_text(f"TOKEN={fake_value}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "config.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "candidate"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            rejected = context.record_commit(run, "1", commit)
            self.assertFalse(rejected.ok)
            self.assertEqual(rejected.error.code, "secret_content")
            self.assertNotIn(fake_value, str(rejected.error))
            evidence = "".join(path.read_text(encoding="utf-8") for path in run.evidence_path.glob("*.json"))
            self.assertNotIn(fake_value, evidence)

    def test_record_commit_rejects_side_branch_and_duplicate_step_assignment(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / ".gitignore").write_text(".agents/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            approval = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            plan = ResolvedPlan("plan-a", "docs/plans/plan-a.md", approval, "text", (), ("app.txt",))
            run = repository.bind_run(
                root, plan, run_id="run-1", delegated=False,
                steps=[{"id": "1", "completion": "check"}, {"id": "2", "completion": "check"}],
                branch="main", worktree=str(root),
            ).value
            subprocess.run(["git", "-C", str(root), "switch", "-qc", "side"], check=True)
            (root / "app.txt").write_text("side\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "side"], check=True)
            side = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            subprocess.run(["git", "-C", str(root), "switch", "-q", "main"], check=True)
            self.assertTrue(context.append_event(run, "check", {
                "step": "1", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            rejected = context.record_commit(run, "1", side)
            self.assertEqual(rejected.error.code, "commit_not_on_branch")
            (root / "app.txt").write_text("main\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "app.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "main change"], check=True)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            self.assertTrue(context.record_commit(run, "1", commit).ok)
            self.assertTrue(context.append_event(run, "check", {
                "step": "2", "checks": [{"command": "lint", "exit_code": 0}], "paths": [],
            }).ok)
            duplicate = context.record_commit(run, "2", commit)
            self.assertEqual(duplicate.error.code, "commit_already_recorded")

    def test_red_test_snapshot_freezes_files_and_command(self) -> None:
        snapshot = tdd.freeze_test(
            {"tests/example_test.py": b"test bytes"},
            command="python3 -m unittest tests.example_test",
        )
        self.assertRegex(snapshot["files"]["tests/example_test.py"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(snapshot["command"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(tdd.frozen_test_matches(
            snapshot,
            {"tests/example_test.py": b"test bytes"},
            command="python3 -m unittest discover",
        ))

    def test_artifact_and_external_results_are_evidence_not_human_approvals(self) -> None:
        artifact = deliverables.artifact_event("2", ["docs/guide.md"], [{"command": "lint", "exit_code": 0}])
        external = deliverables.external_event("3", "device smoke test", "passed")
        self.assertEqual(artifact["event_type"], "artifact")
        self.assertEqual(external["event_type"], "external")
        self.assertNotIn("approval", artifact)
        self.assertNotIn("approval", external)

    def test_human_gates_accept_only_exception_boundaries(self) -> None:
        for kind in ("irreversible", "human_permission", "dangerous_target"):
            self.assertTrue(gates.validate_gate({"kind": kind, "reason": "needed"}).ok)
        for kind in ("artifact", "external", "step_commit", "history"):
            result = gates.validate_gate({"kind": kind, "reason": "ritual"})
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "human_gate_not_allowed")

    def test_recovery_escalates_only_after_diagnosis_and_one_changed_method(self) -> None:
        self.assertEqual(gates.recovery_action(diagnosed=False, method_changed=False, still_stuck=True), "diagnose")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=False, still_stuck=True), "change_method")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=True, still_stuck=True), "human_judgment")
        self.assertEqual(gates.recovery_action(diagnosed=True, method_changed=True, still_stuck=False), "continue")

if __name__ == "__main__":
    unittest.main()
