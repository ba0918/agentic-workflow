import importlib.util
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "tools/workflow-runtime/brainstorm/state.py"
SPEC = importlib.util.spec_from_file_location("brainstorm_state", MODULE)
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)

def progress(revision: int, topic: str = "next") -> dict:
    return {"session_id": "session-1", "revision": revision, "current_position": "here", "next_topic": topic, "items": []}

class BrainstormStateTest(unittest.TestCase):
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
                original = state._write_atomic
                def slow_write(path: Path, text: str) -> None:
                    if path.name == "session-1.md":
                        time.sleep(0.15)
                    original(path, text)
                state._write_atomic = slow_write
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
