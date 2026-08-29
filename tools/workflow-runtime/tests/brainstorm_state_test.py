import importlib.util
import json
import multiprocessing
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "tools/workflow-runtime/brainstorm/state.py"
SPEC = importlib.util.spec_from_file_location("brainstorm_state", MODULE)
assert SPEC is not None
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)

def progress(revision: int, topic: str = "next") -> dict[str, object]:
    return {"session_id": "session-1", "revision": revision, "current_position": "here", "next_topic": topic, "items": []}


def run_state(*arguments: str, document: object | None = None) -> subprocess.CompletedProcess[str]:
    input_text = None if document is None else json.dumps(document)
    return subprocess.run(
        [sys.executable, str(MODULE), *arguments],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )

class BrainstormStateTest(unittest.TestCase):
    def test_cli_help_lists_the_state_operations(self) -> None:
        result = run_state("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("validate", "load", "save", "finish"):
            self.assertIn(command, result.stdout)

    def test_cli_round_trips_state_through_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = progress(1)

            validated = run_state("validate", document=value)
            saved = run_state(
                "save", "--repo", str(root), "--expected-revision", "0", document=value,
            )
            loaded = run_state("load", "--repo", str(root), "--session-id", "session-1")
            finished = run_state(
                "finish", "--repo", str(root), "--session-id", "session-1",
                "--approved", "--write-succeeded",
            )

            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(json.loads(validated.stdout), value)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertEqual(json.loads(saved.stdout), {"path": ".agents/tmp/ideas/session-1.md"})
            self.assertEqual(loaded.returncode, 0, loaded.stderr)
            self.assertEqual(json.loads(loaded.stdout), value)
            self.assertEqual(finished.returncode, 0, finished.stderr)
            self.assertEqual(json.loads(finished.stdout), {"removed": True})
            self.assertFalse(root.joinpath(".agents/tmp/ideas/session-1.md").exists())

    def test_cli_preserves_the_revision_conflict_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = run_state(
                "save", "--repo", str(root), "--expected-revision", "0", document=progress(1),
            )
            conflict = run_state(
                "save", "--repo", str(root), "--expected-revision", "0", document=progress(2),
            )

            self.assertEqual(initial.returncode, 0, initial.stderr)
            self.assertNotEqual(conflict.returncode, 0)
            self.assertIn("revision conflict", conflict.stderr)
            self.assertEqual(state.load_progress(root, "session-1"), progress(1))

    def test_credential_shaped_item_text_is_saved_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            texts = ("".join(("pass", "word", ": ", "example-value")), "sk-example-key-value")
            value = {**progress(1), "items": [
                {"id": f"item-{index}", "kind": "agreement", "text": text}
                for index, text in enumerate(texts)
            ]}

            saved = run_state(
                "save", "--repo", str(root), "--expected-revision", "0", document=value,
            )

            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertEqual(state.load_progress(root, "session-1"), value)

    def test_cli_rejects_unexpected_state_keys(self) -> None:
        result = run_state("validate", document={**progress(1), "unexpected": "value"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected progress key", result.stderr)

    def test_progress_lives_in_the_temporary_ideas_directory_without_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = state.save_progress(root, progress(1), expected_revision=0)
            self.assertEqual(path.relative_to(root).as_posix(), ".agents/tmp/ideas/session-1.md")
            self.assertEqual(state.load_progress(root, "session-1"), progress(1))
            self.assertNotIn("identity", path.read_text(encoding="utf-8"))

    def test_revision_conflict_preserves_both_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state.save_progress(root, progress(1), expected_revision=0)
            state.save_progress(root, progress(2, "current"), expected_revision=1)
            with self.assertRaises(state.RevisionConflict) as caught:
                state.save_progress(root, progress(2, "candidate"), expected_revision=1)
            self.assertEqual(state.load_progress(root, "session-1")["next_topic"], "current")
            self.assertEqual(state.decode_markdown(caught.exception.candidate_path.read_text(encoding="utf-8"))["next_topic"], "candidate")
            self.assertRegex(caught.exception.candidate_path.name, r"session-1\.conflict-\d{8}T\d{6}\.md")

    def test_item_schema_ids_and_revision_references_are_validated(self) -> None:
        valid = {**progress(1), "items": [
            {"id": "A1", "kind": "agreement", "text": "agreed"},
            {"id": "V1", "kind": "revision", "text": "revised", "reason": "clarified", "replaces": ["A1"]},
        ]}
        self.assertEqual(state.validate_state(valid), ())
        invalid_values = (
            {**valid, "items": [{"id": "A1", "kind": "agreement", "text": "one"}, {"id": "A1", "kind": "agreement", "text": "two"}]},
            {**valid, "items": [{"id": "A1", "kind": "unknown", "text": "bad"}]},
            {**valid, "items": [{"id": "V1", "kind": "revision", "text": "bad", "reason": "missing", "replaces": ["A404"]}]},
        )
        for value in invalid_values:
            self.assertTrue(state.validate_state(value))

    def test_parallel_writers_preserve_the_losing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state.save_progress(root, progress(1), expected_revision=0)
            process_context = multiprocessing.get_context("fork")
            start = process_context.Event()
            outcomes = process_context.Queue()

            def writer(topic: str) -> None:
                original = getattr(state, "write_atomic")
                def slow_write(path: Path, text: str) -> None:
                    if path.name == "session-1.md":
                        time.sleep(0.15)
                    original(path, text)
                setattr(state, "write_atomic", slow_write)
                start.wait()
                try:
                    state.save_progress(root, progress(2, topic), expected_revision=1)
                    outcomes.put(("saved", topic))
                except state.RevisionConflict as error:
                    outcomes.put(("conflict", error.candidate_path.name))

            processes = [process_context.Process(target=writer, args=(topic,)) for topic in ("first", "second")]
            for process in processes:
                process.start()
            start.set()
            for process in processes:
                process.join(5)
                self.assertEqual(process.exitcode, 0)
            results = [outcomes.get(timeout=1) for _ in processes]
            self.assertEqual(sorted(result[0] for result in results), ["conflict", "saved"])
            conflict_name = next(result[1] for result in results if result[0] == "conflict")
            self.assertRegex(conflict_name, r"session-1\.conflict-\d{8}T\d{6}(?:-\d+)?\.md")
            self.assertTrue((root / ".agents/tmp/ideas" / conflict_name).is_file())

    def test_successful_approved_wrap_removes_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = state.save_progress(root, progress(1), expected_revision=0)
            self.assertTrue(state.finish_wrap(root, "session-1", approved=True, write_succeeded=True))
            self.assertFalse(path.exists())

    def test_unsafe_session_and_symlink_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(state.UnsafeProgress):
                state.save_progress(root, {**progress(1), "session_id": "../bad"}, expected_revision=0)
            target = root / "outside"
            target.write_text("safe", encoding="utf-8")
            ideas = root / ".agents/tmp/ideas"
            ideas.mkdir(parents=True)
            (ideas / "session-1.md").symlink_to(target)
            with self.assertRaises(state.UnsafeProgress):
                state.save_progress(root, progress(1), expected_revision=0)
            self.assertEqual(target.read_text(encoding="utf-8"), "safe")

if __name__ == "__main__":
    unittest.main()
