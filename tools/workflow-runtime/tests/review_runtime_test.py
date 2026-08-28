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
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/review"))
MODEL_PATH = ROOT / "tools/workflow-runtime/review/review_model.py"
MODEL_SPEC = importlib.util.spec_from_file_location("review_model", MODEL_PATH)
assert MODEL_SPEC is not None
review_model = importlib.util.module_from_spec(MODEL_SPEC)
assert MODEL_SPEC.loader is not None
MODEL_SPEC.loader.exec_module(review_model)
sys.modules["review_model"] = review_model
RUNTIME_PATH = ROOT / "tools/workflow-runtime/review/review_runtime.py"
RUNTIME_SPEC = importlib.util.spec_from_file_location("review_runtime", RUNTIME_PATH)
assert RUNTIME_SPEC is not None
runtime = importlib.util.module_from_spec(RUNTIME_SPEC)
assert RUNTIME_SPEC.loader is not None
RUNTIME_SPEC.loader.exec_module(runtime)
from review_model import JsonObject
from review_support.binding import selected_profiles
from review_support.validation import review_execution


def finding(**changes: object) -> JsonObject:
    value: JsonObject = {
        "severity": "critical", "action": "fix_and_verify",
        "specification": {"path": "docs/spec/review.md", "section": "finding"},
        "evidence": {"path": "app.txt", "observation": "wrong"},
        "oracle": "test -f fixed", "oracle_status": "failing", "root_cause": "logic",
        "state": "open", "spec_commit": "a" * 40, "profile": "default",
    }
    value.update(changes)
    value["id"] = review_model.finding_id(value)
    return value

def safety(**changes: object) -> JsonObject:
    value: JsonObject = {"completed": True, "summary": "no unresolved safety issue", "unresolved": []}
    value.update(changes)
    return value

def repository() -> tuple[Path, str, str]:
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


def execution_fixture() -> tuple[Path, str, str]:
    root, base, head = repository()
    store = root / ".agents/evidence/plan-a/run-1"
    store.mkdir(parents=True)
    binding = {
        "version": 2, "plan_key": "plan-a", "run_id": "run-1", "approval_commit": base,
        "branch": "feature", "worktree": str(root),
        "steps": [{"id": "1", "completion": "check"}],
    }
    (store / "binding.json").write_text(json.dumps(binding), encoding="utf-8")
    events = [
        {"version": 2, "sequence": 1, "event_type": "worktree-bound", "branch": "feature", "worktree": str(root)},
        {"version": 2, "sequence": 2, "event_type": "check", "step": "1", "checks": [{"command": "lint", "exit_code": 0}],
         "changed_paths": ["app.txt"], "safety": {"paths": ["app.txt"], "unplanned": []}},
        {"version": 2, "sequence": 3, "event_type": "commit", "step": "1", "commit": head,
         "safety": {"paths": ["app.txt"], "unplanned": []}},
        {"version": 2, "sequence": 4, "event_type": "implementation_green", "completed_steps": ["1"]},
    ]
    for event in events:
        (store / f"{event['sequence']:06d}-{event['event_type']}.json").write_text(json.dumps(event), encoding="utf-8")
    return root, base, head


class ReviewBindingRuntimeTest(unittest.TestCase):

    def test_resolves_real_branch_commits_and_implementation_run(self) -> None:
        root, base, head = execution_fixture()
        execution = runtime.resolve_input(root, review_id="exec", plan_key="plan-a", run_id="run-1")
        branch = runtime.resolve_input(root, review_id="branch", branch="feature", base="main")
        commits = runtime.resolve_input(root, review_id="commits", base=base, head=head)
        self.assertTrue(all(result.ok for result in (execution, branch, commits)))
        self.assertEqual({runtime.input_kind(result.value) for result in (execution, branch, commits)}, {"execution", "branch", "commits"})
        self.assertEqual(branch.value["input"]["base"], base)
        self.assertEqual(branch.value["input"]["head"], head)

    def test_execution_review_accepts_returned_after_implementation_green(self) -> None:
        root, _, _ = execution_fixture()
        store = root / ".agents/evidence/plan-a/run-1"
        binding_path = store / "binding.json"
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        binding["delegated"] = True
        binding_path.write_text(json.dumps(binding), encoding="utf-8")
        returned = {
            "version": 2, "sequence": 5, "event_type": "returned", "writer": "cycle",
            "outcome": "completed",
        }
        (store / "000005-returned.json").write_text(json.dumps(returned), encoding="utf-8")

        result = runtime.resolve_input(root, review_id="returned", plan_key="plan-a", run_id="run-1")

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["implement_sequence"], 5)

    def test_branch_names_are_resolved_only_from_local_branch_references(self) -> None:
        root, base, head = execution_fixture()
        subprocess.run(["git", "-C", str(root), "tag", "feature", base], check=True)

        execution = runtime.resolve_input(root, review_id="exec", plan_key="plan-a", run_id="run-1")
        standalone = runtime.resolve_input(root, review_id="branch", branch="feature", base="main")

        self.assertTrue(execution.ok, execution.error)
        self.assertTrue(standalone.ok, standalone.error)
        self.assertEqual(execution.value["head"], head)
        self.assertEqual(standalone.value["input"]["head"], head)

    def test_document_only_rebound_commit_need_not_be_in_implementation_history(self) -> None:
        root, base, implementation = execution_fixture()
        subprocess.run(["git", "-C", str(root), "switch", "-qc", "specification", base], check=True)
        (root / "docs/spec/review.md").write_text("# Review\n\nClarified wording.\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/review.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "clarify specification"], check=True)
        revised = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True,
        ).stdout.strip()
        subprocess.run(["git", "-C", str(root), "switch", "feature"], check=True)
        store = root / ".agents/evidence/plan-a/run-1"
        (store / "000004-implementation_green.json").unlink()
        rebound = {
            "version": 2, "sequence": 4, "event_type": "rebound", "approval_commit": revised,
            "steps": [{"id": "same", "completion": "check"}],
            "mappings": [{"old": "1", "new": "same"}], "reason": "wording only",
        }
        green = {
            "version": 2, "sequence": 5, "event_type": "implementation_green",
            "completed_steps": ["same"],
        }
        (store / "000004-rebound.json").write_text(json.dumps(rebound), encoding="utf-8")
        (store / "000005-implementation_green.json").write_text(json.dumps(green), encoding="utf-8")

        resolved = runtime.resolve_input(root, review_id="rebound", plan_key="plan-a", run_id="run-1")

        self.assertTrue(resolved.ok, resolved.error)
        self.assertEqual(resolved.value["approval_commit"], revised)
        self.assertEqual(resolved.value["head"], implementation)

    def test_execution_review_rejects_dirty_reviewed_paths_but_records_other_dirty_paths(self) -> None:
        root, _, _ = execution_fixture()
        binding_path = root / ".agents/evidence/plan-a/run-1/binding.json"
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        binding["expected_paths"] = ["app.txt"]
        binding_path.write_text(json.dumps(binding), encoding="utf-8")
        (root / "notes.txt").write_text("outside review scope\n", encoding="utf-8")

        outside = runtime.resolve_input(root, review_id="outside", plan_key="plan-a", run_id="run-1")

        self.assertTrue(outside.ok, outside.error)
        self.assertEqual(outside.value["uncommitted_outside_scope"], ["notes.txt"])
        (root / ".env").write_text("placeholder\n", encoding="utf-8")
        dangerous = runtime.resolve_input(root, review_id="dangerous", plan_key="plan-a", run_id="run-1")
        self.assertEqual(dangerous.error.code, "dangerous_path")
        (root / ".env").unlink()
        (root / "app.txt").write_text("dirty reviewed input\n", encoding="utf-8")
        inside = runtime.resolve_input(root, review_id="inside", plan_key="plan-a", run_id="run-1")
        self.assertEqual(inside.error.code, "review_scope_dirty")

    def test_execution_review_rejects_a_staged_rename_of_a_reviewed_path(self) -> None:
        root, _, _ = execution_fixture()
        subprocess.run(["git", "-C", str(root), "mv", "app.txt", "renamed.txt"], check=True)

        result = runtime.resolve_input(root, review_id="rename", plan_key="plan-a", run_id="run-1")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "review_scope_dirty")

    def test_review_selectors_and_bindings_cannot_escape_the_evidence_store(self) -> None:
        root, base, head = repository()
        outside = root.parent / f"{root.name}-outside" / "review"
        outside.mkdir(parents=True)
        traversal = f"../../../../{outside.parent.name}/review"
        crafted = {
            "version": 2, "kind": "standalone", "review_id": traversal,
            "input": {"kind": "commits", "branch": None, "base": base, "head": head},
            "spec_paths": ["docs/spec/"], "spec_commit": head,
        }
        (outside / "binding.json").write_text(json.dumps(crafted), encoding="utf-8")
        before = sorted(path.name for path in outside.iterdir())
        loaded = runtime.load_review_binding(root, review_id=traversal)
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.error.code, "review_selector_invalid")
        bound = runtime.bind_review(root, crafted, model="model-x")
        self.assertFalse(bound.ok)
        self.assertEqual(sorted(path.name for path in outside.iterdir()), before)

    def test_execution_input_accepts_wording_recovery_and_rebound_revision_tips(self) -> None:
        for boundary in ("recovering", "rebound"):
            root, _, _ = execution_fixture()
            (root / "docs/spec/review.md").write_text("# Review\n\nClarified wording.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "docs/spec/review.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "approved wording"], check=True)
            revised = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
            store = root / ".agents/evidence/plan-a/run-1"
            green = store / "000004-implementation_green.json"
            green.unlink()
            if boundary == "recovering":
                event = {
                    "version": 2, "sequence": 4, "event_type": "recovering",
                    "current_commit": revised, "changed_documents": ["docs/spec/review.md"],
                    "reason": "wording only",
                }
                completed = ["1"]
            else:
                event = {
                    "version": 2, "sequence": 4, "event_type": "rebound",
                    "approval_commit": revised, "steps": [{"id": "same", "completion": "check"}],
                    "mappings": [{"old": "1", "new": "same"}], "reason": "approved revision",
                }
                completed = ["same"]
            (store / f"000004-{boundary}.json").write_text(json.dumps(event), encoding="utf-8")
            (store / "000005-implementation_green.json").write_text(json.dumps({
                "version": 2, "sequence": 5, "event_type": "implementation_green",
                "completed_steps": completed,
            }), encoding="utf-8")
            resolved = runtime.resolve_input(root, review_id=boundary, plan_key="plan-a", run_id="run-1")
            self.assertTrue(resolved.ok, resolved.error)
            self.assertEqual(resolved.value["approval_commit"], revised)
            self.assertEqual(resolved.value["head"], revised)

    def test_rejects_imaginary_branch_sha_and_incomplete_implementation_evidence(self) -> None:
        root, _, head = execution_fixture()
        self.assertEqual(runtime.resolve_input(root, review_id="bad", branch="missing", base="main").error.code, "branch_not_found")
        self.assertEqual(runtime.resolve_input(root, review_id="bad", base="f" * 40, head=head).error.code, "commit_not_found")
        green = root / ".agents/evidence/plan-a/run-1/000004-implementation_green.json"
        green.unlink()
        self.assertEqual(
            runtime.resolve_input(root, review_id="bad", plan_key="plan-a", run_id="run-1").error.code,
            "implementation_incomplete",
        )

    def test_all_implementation_and_review_events_require_version_two(self) -> None:
        root, _, _ = execution_fixture()
        green = root / ".agents/evidence/plan-a/run-1/000004-implementation_green.json"
        payload = json.loads(green.read_text(encoding="utf-8"))
        payload.pop("version")
        green.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(
            runtime.resolve_input(root, review_id="bad", plan_key="plan-a", run_id="run-1").error.code,
            "execution_input_invalid",
        )
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="review-v", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        event = root / ".agents/evidence/reviews/review-v/000001-review-bound.json"
        payload = json.loads(event.read_text(encoding="utf-8"))
        payload["version"] = 3
        event.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(runtime.load_events(root, binding).error.code, "review_event_invalid")

    def test_execution_input_rejects_changed_frozen_red_snapshot(self) -> None:
        root, _, head = execution_fixture()
        store = root / ".agents/evidence/plan-a/run-1"
        binding_path = store / "binding.json"
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        binding["steps"] = [{"id": "1", "completion": "test"}]
        binding_path.write_text(json.dumps(binding), encoding="utf-8")
        for path in store.glob("[0-9]*.json"):
            path.unlink()
        snapshot_a = {"files": {"tests/a.py": "sha256:" + "0" * 64}, "command": "sha256:" + "1" * 64}
        snapshot_b = {"files": {"tests/b.py": "sha256:" + "2" * 64}, "command": "sha256:" + "3" * 64}
        events = [
            {"version": 2, "sequence": 1, "event_type": "worktree-bound", "branch": "feature", "worktree": str(root)},
            {"version": 2, "sequence": 2, "event_type": "red", "step": "1", "command": "tests", "exit_code": 1, "snapshot": snapshot_a},
            {"version": 2, "sequence": 3, "event_type": "green", "step": "1", "command": "tests", "exit_code": 0, "snapshot": snapshot_b},
            {"version": 2, "sequence": 4, "event_type": "refactor", "step": "1", "command": "tests", "exit_code": 0, "snapshot": snapshot_b},
            {"version": 2, "sequence": 5, "event_type": "commit", "step": "1", "commit": head, "safety": {"paths": ["app.txt"], "unplanned": []}},
            {"version": 2, "sequence": 6, "event_type": "implementation_green", "completed_steps": ["1"]},
        ]
        for event in events:
            (store / f"{event['sequence']:06d}-{event['event_type']}.json").write_text(json.dumps(event), encoding="utf-8")
        result = runtime.resolve_input(root, review_id="bad-red", plan_key="plan-a", run_id="run-1")
        self.assertEqual(result.error.code, "frozen_red_mismatch")

    def test_branch_base_uses_explicit_then_pr_then_unique_default(self) -> None:
        root, base, _ = repository()
        explicit = runtime.resolve_input(root, review_id="one", branch="feature", base="main")
        pull_request = runtime.resolve_input(root, review_id="two", branch="feature", pull_request_target="main")
        default = runtime.resolve_input(root, review_id="three", branch="feature")
        self.assertEqual([item.value["input"]["base"] for item in (explicit, pull_request, default)], [base, base, base])

class ReviewLifecycleRuntimeTest(unittest.TestCase):
    def test_empty_findings_cannot_fake_initial_final_and_completion(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="review-1", branch="feature", base="main").value
        self.assertTrue(runtime.bind_review(
            root, binding, model="model-x", level="light", profiles=["skill"],
            model_source="explicit", second_reviewer="codex", second_model="model-y",
        ).ok)
        stored = runtime.load_review_binding(root, review_id="review-1").value
        self.assertEqual(stored["review_options"], {
            "level": "light", "profiles": ["skill"], "profile_source": "explicit",
            "model": "model-x", "model_source": "explicit",
            "second_reviewer": "codex", "second_model": "model-y",
        })
        second = runtime.record_second_review(
            root, stored, status="unavailable", actual_model=None,
            summary="runner unavailable; continuing with first reviewer",
        )
        self.assertTrue(second.ok, second.error)
        self.assertEqual(second.value["event_type"], "second-review-recorded")
        self.assertNotIn("actual_model", second.value)
        initial = runtime.begin_stage(root, binding, reviewer_context="reviewer-initial")
        self.assertEqual(initial.value["event_type"], "initial-full-review-started")
        self.assertEqual(runtime.begin_stage(root, binding, reviewer_context="same").error.code, "stage_results_required")
        unsafe = runtime.record_findings(
            root, binding, stage="initial", findings=[],
            safety=safety(completed=False, unresolved=["secret scan unavailable"]),
            reviewer_context="reviewer-initial", actual_model="model-x",
        )
        self.assertEqual(unsafe.error.code, "safety_check_required")
        self.assertTrue(runtime.record_findings(
            root, binding, stage="initial", findings=[], safety=safety(), reviewer_context="reviewer-initial", actual_model="model-x",
        ).ok)
        final = runtime.begin_stage(root, binding, reviewer_context="reviewer-final")
        self.assertEqual(final.value["event_type"], "final-full-review-started")
        self.assertEqual(runtime.complete_review(root, binding).error.code, "final_results_required")
        self.assertTrue(runtime.record_findings(
            root, binding, stage="final", findings=[], safety=safety(), reviewer_context="reviewer-final", actual_model="model-z",
        ).ok)
        completed = runtime.complete_review(root, binding)
        self.assertTrue(completed.ok, completed.error)
        self.assertEqual(completed.value["event_type"], "review-complete")
        self.assertNotIn("review-completed", [event["event_type"] for event in runtime.load_events(root, binding).value])

    def test_loader_rejects_malformed_findings_and_final_without_initial_review(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="forged", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        directory = runtime.review_directory(root, binding)
        forged = [
            {"version": 2, "sequence": 2, "event_type": "final-full-review-started", "reviewer_context": "final"},
            {"version": 2, "sequence": 3, "event_type": "final-findings-recorded", "findings": [],
             "safety": safety(), "reviewer_context": "final", "actual_model": "model-x"},
        ]
        for event in forged:
            (directory / f"{event['sequence']:06d}-{event['event_type']}.json").write_text(json.dumps(event), encoding="utf-8")
        loaded = runtime.load_events(root, binding)
        self.assertEqual(loaded.error.code, "review_transition_invalid")
        self.assertFalse(runtime.complete_review(root, binding).ok)

        other, _, _ = repository()
        other_binding = runtime.resolve_input(other, review_id="malformed", branch="feature", base="main").value
        runtime.bind_review(other, other_binding, model="model-x")
        directory = runtime.review_directory(other, other_binding)
        started = {"version": 2, "sequence": 2, "event_type": "initial-full-review-started", "reviewer_context": "initial"}
        malformed = {"version": 2, "sequence": 3, "event_type": "initial-findings-recorded", "findings": [{}],
                     "safety": safety(), "reviewer_context": "initial", "actual_model": "model-x"}
        for event in (started, malformed):
            (directory / f"{event['sequence']:06d}-{event['event_type']}.json").write_text(json.dumps(event), encoding="utf-8")
        loaded = runtime.load_events(other, other_binding)
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.error.code, "review_event_invalid")

    def test_targeted_close_requires_trailer_and_progress_then_stale_can_rebound(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="review-1", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="reviewer-initial")
        item = finding(spec_commit=binding["spec_commit"])
        self.assertTrue(runtime.record_findings(
            root, binding, stage="initial", findings=[item], safety=safety(), reviewer_context="reviewer-initial", actual_model="model-x",
        ).ok)
        bypass = runtime.close_finding(
            root, binding, item["id"], oracle_exit_code=0, fix_commits=[],
            operation="python3 -m unittest", result_summary="local test passed",
        )
        self.assertEqual(bypass.error.code, "targeted_review_required")
        self.assertEqual(runtime.begin_stage(root, binding, reviewer_context="reviewer-targeted").value["event_type"], "targeted-review-started")
        (root / "fixed").write_text("fixed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "fixed"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", f"fix finding\n\nFinding: {item['id']}"], check=True)
        fix_commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        closed = runtime.close_finding(
            root, binding, item["id"], oracle_exit_code=0, fix_commits=[fix_commit],
            operation="python3 -m unittest", result_summary="local test passed",
        )
        self.assertTrue(closed.ok, closed.error)
        self.assertEqual(closed.value["event_type"], "targeted-review-result")
        progress = runtime.record_progress(root, binding)
        self.assertTrue(progress.ok, progress.error)
        self.assertEqual(progress.value["before"], (0, 1, 0))
        self.assertEqual(progress.value["after"], (0, 0, 0))
        self.assertTrue(runtime.mark_stale(root, binding, reason="important spec change").ok)
        self.assertEqual(runtime.begin_stage(root, binding, reviewer_context="blocked").error.code, "findings_stale")
        self.assertTrue(runtime.rebound_findings(root, binding, spec_commit=fix_commit, reason="human approved revision").ok)
        rebound_finding = finding(oracle="new-spec", spec_commit=fix_commit)
        added = runtime.add_findings(root, binding, candidates=[rebound_finding], related_ids={rebound_finding["id"]})
        self.assertTrue(added.ok, added.error)

    def test_final_targeted_close_accepts_required_progress_before_completion(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="final-targeted", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="initial")
        self.assertTrue(runtime.record_findings(
            root, binding, stage="initial", findings=[], safety=safety(),
            reviewer_context="initial", actual_model="model-x",
        ).ok)
        runtime.begin_stage(root, binding, reviewer_context="final")
        item = finding(spec_commit=binding["spec_commit"])
        self.assertTrue(runtime.record_findings(
            root, binding, stage="final", findings=[item], safety=safety(),
            reviewer_context="final", actual_model="model-x",
        ).ok)
        self.assertTrue(runtime.begin_stage(root, binding, reviewer_context="targeted").ok)
        (root / "fixed").write_text("fixed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "fixed"], check=True)
        subprocess.run([
            "git", "-C", str(root), "commit", "-qm", f"fix\n\nFinding: {item['id']}",
        ], check=True)
        fix_commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
        self.assertTrue(runtime.close_finding(
            root, binding, item["id"], oracle_exit_code=0, fix_commits=[fix_commit],
            operation="python3 -m unittest", result_summary="local test passed",
        ).ok)

        before_progress = runtime.complete_review(root, binding)
        progress = runtime.record_progress(root, binding)
        completed = runtime.complete_review(root, binding)
        after_completion = runtime.mark_stale(root, binding, reason="must remain terminal")

        self.assertEqual(before_progress.error.code, "progress_assessment_required")
        self.assertTrue(progress.ok, progress.error)
        self.assertEqual(progress.value["event_type"], "progress-assessed")
        self.assertTrue(completed.ok, completed.error)
        self.assertEqual(completed.value["event_type"], "review-complete")
        self.assertEqual(after_completion.error.code, "review_already_completed")

    def test_dynamic_findings_and_stalled_progress_are_runtime_events(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="review-1", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="reviewer-initial")
        original = finding(spec_commit=binding["spec_commit"])
        runtime.record_findings(
            root, binding, stage="initial", findings=[original], safety=safety(),
            reviewer_context="reviewer-initial", actual_model="model-x",
        )
        related = finding(severity="warn", oracle="related", spec_commit=binding["spec_commit"])
        unrelated = finding(severity="warn", oracle="unrelated", spec_commit=binding["spec_commit"])
        added = runtime.add_findings(root, binding, candidates=[related, unrelated], related_ids={related["id"]})
        self.assertEqual([item["id"] for item in added.value["findings"]], [related["id"]])
        self.assertEqual([item["id"] for item in added.value["terminal_observations"]], [unrelated["id"]])
        actions = []
        for index in range(3):
            self.assertTrue(runtime.begin_stage(root, binding, reviewer_context=f"targeted-{index}").ok)
            self.assertTrue(runtime.record_targeted_result(
                root, binding, original["id"], oracle_exit_code=1, fix_commits=[],
                operation="python3 -m unittest", result_summary="local test still fails",
            ).ok)
            self.assertTrue(runtime.record_targeted_result(
                root, binding, related["id"], oracle_exit_code=1, fix_commits=[],
                operation="python3 -m unittest", result_summary="local test still fails",
            ).ok)
            actions.append(runtime.record_progress(root, binding).value["next_action"])
        self.assertEqual(actions, ["diagnose", "change_method", "human_judgment"])

class ReviewFindingRuntimeTest(unittest.TestCase):
    def test_human_decision_closes_an_open_finding_without_oracle_or_commit(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="review-1", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="reviewer-initial")
        item = finding(action="human_judgment", oracle="", oracle_status="unavailable",
                       oracle_unavailable_reason="scope decision", spec_commit=binding["spec_commit"])
        self.assertTrue(runtime.record_findings(
            root, binding, stage="initial", findings=[item], safety=safety(),
            reviewer_context="reviewer-initial", actual_model="model-x",
        ).ok)
        self.assertTrue(runtime.begin_stage(root, binding, reviewer_context="reviewer-targeted").ok)
        missing_reason = runtime.record_human_decision(
            root, binding, item["id"], decision="do_not_fix", reason="",
        )
        self.assertEqual(missing_reason.error.code, "human_decision_invalid")
        decided = runtime.record_human_decision(
            root, binding, item["id"], decision="do_not_fix", reason="accepted risk",
        )
        self.assertTrue(decided.ok, decided.error)
        self.assertEqual(decided.value["event_type"], "human-finding-decided")
        self.assertEqual(runtime.current_findings(runtime.load_events(root, binding).value)[0]["state"], "closed")
        progress = runtime.record_progress(root, binding)
        self.assertTrue(progress.ok, progress.error)
        self.assertEqual(progress.value["after"], (0, 0, 0))
        later = runtime.record_targeted_result(
            root, binding, item["id"], oracle_exit_code=0, fix_commits=[],
            operation="python3 -m unittest", result_summary="local test passed",
        )
        self.assertEqual(later.error.code, "finding_not_open")

    def test_targeted_result_records_reviewer_operation_and_rejects_unsafe_proposals(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="safe-operation", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="initial")
        item = finding(spec_commit=binding["spec_commit"])
        runtime.record_findings(
            root, binding, stage="initial", findings=[item], safety=safety(),
            reviewer_context="initial", actual_model="model-x",
        )
        runtime.begin_stage(root, binding, reviewer_context="targeted")

        unsafe = runtime.record_targeted_result(
            root, binding, item["id"], oracle_exit_code=1, fix_commits=[],
            operation="rm -rf /", result_summary="proposal was not executed",
        )
        safe = runtime.record_targeted_result(
            root, binding, item["id"], oracle_exit_code=1, fix_commits=[],
            operation="python3 -m unittest tests.review_test", result_summary="local test still fails",
        )

        self.assertEqual(unsafe.error.code, "review_operation_unsafe")
        self.assertTrue(safe.ok, safe.error)
        self.assertEqual(safe.value["execution"], {
            "operation": "python3 -m unittest tests.review_test", "working_directory": ".",
            "exit_code": 1, "summary": "local test still fails",
        })
        self.assertEqual(item["oracle"], "test -f fixed")

    def test_targeted_result_rejects_destructive_git_shell_and_interpreter_operations(self) -> None:
        operations = (
            "git reset --hard",
            "git clean -fd",
            "sh -c 'rm -rf build'",
            "python3 -c \"from pathlib import Path; Path('result').write_text('changed')\"",
        )

        for operation in operations:
            with self.subTest(operation=operation):
                result = review_execution(operation, 1, "operation was not executed")
                self.assertFalse(result.ok)
                self.assertEqual(result.required_error().code, "review_operation_unsafe")

    def test_review_operations_reject_side_effect_options_and_keep_read_only_checks(self) -> None:
        unsafe_operations = (
            "sed -i s/old/new/ app.txt",
            "git diff --output=result.patch",
            "rg --pre formatter.py pattern app.txt",
        )
        safe_operations = (
            "python3 -m unittest tests.review_test",
            "git diff --check",
            "rg -n pattern app.txt",
        )

        for operation in unsafe_operations:
            with self.subTest(operation=operation):
                result = review_execution(operation, 1, "operation was not executed")
                self.assertFalse(result.ok)
                self.assertEqual(result.required_error().code, "review_operation_unsafe")
        for operation in safe_operations:
            with self.subTest(operation=operation):
                result = review_execution(operation, 0, "local read-only check passed")
                self.assertTrue(result.ok, result.error)

    def test_review_operations_exclude_sed_and_retain_read_only_alternatives(self) -> None:
        sed_operations = (
            "sed -ibak s/old/new/ app.txt",
            "sed -n 'e touch result.txt' app.txt",
            "sed -n 1,20p app.txt",
        )
        read_only_alternatives = (
            "rg -n pattern app.txt",
            "git grep -n pattern",
            "python3 -m unittest tests.review_test",
        )

        for operation in sed_operations:
            with self.subTest(operation=operation):
                result = review_execution(operation, 1, "operation was not executed")
                self.assertFalse(result.ok)
                self.assertEqual(result.required_error().code, "review_operation_unsafe")
        for operation in read_only_alternatives:
            with self.subTest(operation=operation):
                result = review_execution(operation, 0, "safe alternative passed")
                self.assertTrue(result.ok, result.error)

    def test_stale_state_blocks_every_operation_except_rebound(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="stale", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="initial")
        item = finding(action="human_judgment", oracle="", oracle_status="unavailable",
                       oracle_unavailable_reason="decision", spec_commit=binding["spec_commit"])
        runtime.record_findings(root, binding, stage="initial", findings=[item], safety=safety(), reviewer_context="initial", actual_model="model-x")
        runtime.mark_stale(root, binding, reason="spec changed")
        self.assertEqual(runtime.record_human_decision(
            root, binding, item["id"], decision="accept", reason="human choice",
        ).error.code, "findings_stale")
        self.assertEqual(runtime.record_findings(
            root, binding, stage="final", findings=[], safety=safety(), reviewer_context="final", actual_model="model-x",
        ).error.code, "findings_stale")
        self.assertEqual(runtime.complete_review(root, binding).error.code, "findings_stale")

    def test_fix_commits_are_derived_from_the_bound_branch_range(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="range", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="initial")
        item = finding(spec_commit=binding["spec_commit"])
        runtime.record_findings(root, binding, stage="initial", findings=[item], safety=safety(), reviewer_context="initial", actual_model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="targeted")
        subprocess.run(["git", "-C", str(root), "switch", "-qc", "side", "main"], check=True)
        (root / "side.txt").write_text("side\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "side.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", f"unrelated\n\nFinding: {item['id']}"], check=True)
        side = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        result = runtime.close_finding(
            root, binding, item["id"], oracle_exit_code=0, fix_commits=[side],
            operation="python3 -m unittest", result_summary="local test passed",
        )
        self.assertEqual(result.error.code, "fix_commit_unlinked")

    def test_two_commit_review_closes_with_exact_descendant_fix_range(self) -> None:
        root, base, head = repository()
        binding = runtime.resolve_input(root, review_id="commits-fix", base=base, head=head).value
        runtime.bind_review(root, binding, model="model-x")
        runtime.begin_stage(root, binding, reviewer_context="initial")
        item = finding(spec_commit=binding["spec_commit"])
        runtime.record_findings(
            root, binding, stage="initial", findings=[item], safety=safety(),
            reviewer_context="initial", actual_model="model-x",
        )
        runtime.begin_stage(root, binding, reviewer_context="targeted")
        (root / "fixed").write_text("fixed\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "fixed"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", f"fix\n\nFinding: {item['id']}"], check=True)
        fix = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        closed = runtime.close_finding(
            root, binding, item["id"], oracle_exit_code=0, fix_commits=[fix],
            operation="python3 -m unittest", result_summary="local test passed",
        )
        self.assertTrue(closed.ok, closed.error)

        other, other_base, other_head = repository()
        other_binding = runtime.resolve_input(
            other, review_id="commits-side", base=other_base, head=other_head,
        ).value
        runtime.bind_review(other, other_binding, model="model-x")
        runtime.begin_stage(other, other_binding, reviewer_context="initial")
        other_item = finding(spec_commit=other_binding["spec_commit"])
        runtime.record_findings(
            other, other_binding, stage="initial", findings=[other_item], safety=safety(),
            reviewer_context="initial", actual_model="model-x",
        )
        runtime.begin_stage(other, other_binding, reviewer_context="targeted")
        subprocess.run(["git", "-C", str(other), "switch", "-qc", "side", "main"], check=True)
        (other / "side-fix").write_text("side\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(other), "add", "side-fix"], check=True)
        subprocess.run(["git", "-C", str(other), "commit", "-qm", f"side\n\nFinding: {other_item['id']}"], check=True)
        side = subprocess.run(["git", "-C", str(other), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        rejected = runtime.close_finding(
            other, other_binding, other_item["id"], oracle_exit_code=0, fix_commits=[side],
            operation="python3 -m unittest", result_summary="local test passed",
        )
        self.assertEqual(rejected.error.code, "fix_commit_unlinked")

    def test_review_options_use_known_profiles_and_valid_second_reviewer_pairs(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="options", branch="feature", base="main").value
        self.assertEqual(runtime.bind_review(root, binding, model="m", profiles=["unknown"]).error.code, "review_profile_invalid")
        self.assertEqual(runtime.bind_review(root, binding, model="m", second_model="m2").error.code, "second_reviewer_invalid")
        eval_binding = runtime.resolve_input(root, review_id="eval", branch="feature", base="main").value
        (root / "evals/cases/ba0918-review").mkdir(parents=True)
        (root / "evals/cases/ba0918-review/case.md").write_text("case\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "evals"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "eval case"], check=True)
        eval_binding["input"]["head"] = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        selected, source = selected_profiles(root, eval_binding, [])
        self.assertIn("skill", selected)
        self.assertNotIn("document", selected)
        self.assertEqual(source, "changed_files")

    def test_bounded_review_text_rejects_secrets_and_stage_records_actual_model(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="text", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="requested")
        runtime.begin_stage(root, binding, reviewer_context="initial")
        missing_model = runtime.record_findings(
            root, binding, stage="initial", findings=[], safety=safety(), reviewer_context="initial",
        )
        self.assertEqual(missing_model.error.code, "actual_model_required")
        fake_secret = "API_TOKEN=fake-review-secret-value"
        rejected = runtime.record_findings(
            root, binding, stage="initial", findings=[], safety=safety(summary=fake_secret),
            reviewer_context="initial", actual_model="actual-model",
        )
        self.assertEqual(rejected.error.code, "bounded_text_invalid")
        self.assertNotIn(fake_secret, str(rejected))
        recorded = runtime.record_findings(
            root, binding, stage="initial", findings=[], safety=safety(),
            reviewer_context="initial", actual_model="actual-model",
        )
        self.assertTrue(recorded.ok, recorded.error)
        self.assertEqual(recorded.value["actual_model"], "actual-model")

    def test_finding_text_and_binding_fields_are_validated_before_any_write(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="finding-boundary", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="model-x", profiles=["default"])
        runtime.begin_stage(root, binding, reviewer_context="initial")
        directory = runtime.review_directory(root, binding)
        before = sorted(path.name for path in directory.iterdir())
        secret = "API_TOKEN=fake-finding-secret-value"
        secret_item = finding(
            evidence={"path": "app.txt", "observation": secret}, spec_commit=binding["spec_commit"],
        )
        rejected = runtime.record_findings(
            root, binding, stage="initial", findings=[secret_item], safety=safety(),
            reviewer_context="initial", actual_model="model-x",
        )
        self.assertEqual(rejected.error.code, "finding_content_invalid")
        self.assertNotIn(secret, str(rejected))
        self.assertEqual(sorted(path.name for path in directory.iterdir()), before)
        mismatched = finding(profile="skill", spec_commit="f" * 40)
        rejected = runtime.record_findings(
            root, binding, stage="initial", findings=[mismatched], safety=safety(),
            reviewer_context="initial", actual_model="model-x",
        )
        self.assertEqual(rejected.error.code, "finding_binding_invalid")
        self.assertEqual(sorted(path.name for path in directory.iterdir()), before)

    def test_second_review_and_human_decision_do_not_persist_secret_shaped_text(self) -> None:
        root, _, _ = repository()
        binding = runtime.resolve_input(root, review_id="secret-text", branch="feature", base="main").value
        runtime.bind_review(root, binding, model="first", second_reviewer="codex", second_model="second")
        secret = "CREDENTIAL=fake-review-credential"
        second = runtime.record_second_review(
            root, binding, status="completed", actual_model="second", summary=secret,
        )
        self.assertEqual(second.error.code, "second_review_invalid")
        self.assertNotIn(secret, str(second))
        runtime.begin_stage(root, binding, reviewer_context="initial")
        item = finding(action="human_judgment", oracle="", oracle_status="unavailable",
                       oracle_unavailable_reason="decision", spec_commit=binding["spec_commit"])
        runtime.record_findings(root, binding, stage="initial", findings=[item], safety=safety(), reviewer_context="initial", actual_model="first")
        decided = runtime.record_human_decision(
            root, binding, item["id"], decision="accept", reason=secret,
        )
        self.assertEqual(decided.error.code, "human_decision_invalid")
        self.assertNotIn(secret, str(decided))

class ReviewCliRuntimeTest(unittest.TestCase):
    def test_cli_binds_real_branch_and_starts_initial_review(self) -> None:
        root, _, _ = repository()
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
