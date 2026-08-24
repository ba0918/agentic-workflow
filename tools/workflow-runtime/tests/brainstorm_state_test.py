import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).parents[3]
STATE_MODULE = ROOT / "tools/workflow-runtime/brainstorm/state.py"
SPEC = importlib.util.spec_from_file_location("brainstorm_state", STATE_MODULE)
state = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(state)


def semantic_state(revision: int = 1) -> dict:
    return {
        "session_id": "20260821T220000Z-demo",
        "revision": revision,
        "current_position": "最初のphaseを詳細化している",
        "next_topic": "反例を確認する",
        "items": [
            {"id": "A1", "kind": "agreement", "text": "広い依頼を分割する"},
            {"id": "P1", "kind": "prohibition", "text": "一つの巨大planにしない"},
            {"id": "U1", "kind": "undecided", "text": "保存形式", "reason": "実装へ委任"},
            {"id": "D1", "kind": "delegated", "text": "atomic write方式", "reason": "実装判断"},
            {"id": "R1", "kind": "rejected", "text": "current-session.md", "reason": "上書き競合"},
            {
                "id": "V1",
                "kind": "revision",
                "text": "specとplanは多対多",
                "reason": "旧A1を修正",
                "replaces": ["A1"],
            },
        ],
        "history": [{"revision": revision, "summary": "意味を更新"}],
    }


class StateValidationTest(unittest.TestCase):
    def test_complete_semantic_state_round_trips(self) -> None:
        value = semantic_state()
        value["content_identity"] = state.content_identity(value)

        self.assertEqual(state.validate_state(value), ())
        self.assertEqual(state.decode_markdown(state.encode_markdown(value)), value)

    def test_duplicate_ids_and_broken_revision_are_rejected(self) -> None:
        value = semantic_state()
        value["items"].append({"id": "A1", "kind": "agreement", "text": "duplicate"})
        value["history"][0]["revision"] = 2
        value["content_identity"] = state.content_identity(value)

        errors = state.validate_state(value)

        self.assertIn("duplicate item id: A1", errors)
        self.assertIn("history revision exceeds current revision: 2", errors)

    def test_identity_mismatch_is_rejected(self) -> None:
        value = semantic_state()
        value["content_identity"] = "sha256:" + "0" * 64

        self.assertIn("content identity mismatch", state.validate_state(value))

    def test_broken_revision_reference_is_rejected(self) -> None:
        value = semantic_state()
        value["items"][-1]["replaces"] = ["missing"]
        value["content_identity"] = state.content_identity(value)

        self.assertIn("item V1 replaces unknown id: missing", state.validate_state(value))

    def test_unused_semantic_kinds_are_not_required(self) -> None:
        value = semantic_state()
        value["items"] = [{"id": "A1", "kind": "agreement", "text": "小さな合意"}]
        value["content_identity"] = state.content_identity(value)

        self.assertEqual(state.validate_state(value), ())


class ProgressStoreTest(unittest.TestCase):
    def test_explicit_nonlocal_artifact_policy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / ".agents/artifacts.yml"
            policy.parent.mkdir(parents=True)
            policy.write_text("mode: repository\n", encoding="utf-8")

            with self.assertRaisesRegex(state.UnsafeProgress, "artifact policy"):
                state.save_progress(root, semantic_state(), expected_revision=0)

            self.assertFalse((root / ".agents/artifacts/ideas/progress").exists())

    def test_legacy_idea_store_coexistence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "docs/ideas"
            legacy.mkdir(parents=True)

            with self.assertRaisesRegex(state.UnsafeProgress, "legacy idea store"):
                state.save_progress(root, semantic_state(), expected_revision=0)

            self.assertFalse((root / ".agents/artifacts/ideas/progress").exists())

    def test_unchanged_meaning_does_not_rewrite_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = state.save_progress(root, semantic_state(), expected_revision=0)
            before = first.read_bytes()

            second = state.save_progress(root, semantic_state(), expected_revision=1)

            self.assertEqual(second, first)
            self.assertEqual(first.read_bytes(), before)
            self.assertEqual(state.load_progress(root, "20260821T220000Z-demo")["revision"], 1)

    def test_conflict_preserves_current_and_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state.save_progress(root, semantic_state(), expected_revision=0)
            current = semantic_state(2)
            current["next_topic"] = "現在側の変更"
            state.save_progress(root, current, expected_revision=1)
            candidate = semantic_state(2)
            candidate["next_topic"] = "競合した変更"

            with self.assertRaises(state.RevisionConflict) as caught:
                state.save_progress(root, candidate, expected_revision=1)

            progress = root / ".agents/artifacts/ideas/progress"
            self.assertEqual(state.load_progress(root, candidate["session_id"])["next_topic"], "現在側の変更")
            self.assertTrue(caught.exception.candidate_path.is_file())
            self.assertEqual(state.decode_markdown(caught.exception.candidate_path.read_text())["next_topic"], "競合した変更")
            self.assertEqual(len(list(progress.glob("*.conflict-*.md"))), 1)

    def test_unsafe_session_secret_and_symlink_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsafe = semantic_state()
            unsafe["session_id"] = "../escape"
            with self.assertRaises(state.UnsafeProgress):
                state.save_progress(root, unsafe, expected_revision=0)

            secret = semantic_state()
            secret["items"][0]["text"] = "api_key=<your-secret-key>"
            with self.assertRaises(state.UnsafeProgress):
                state.save_progress(root, secret, expected_revision=0)

            progress = root / ".agents/artifacts/ideas/progress"
            progress.mkdir(parents=True, exist_ok=True)
            outside = root / "outside.md"
            outside.write_text("untouched")
            (progress / "20260821T220000Z-demo.md").symlink_to(outside)
            with self.assertRaises(state.UnsafeProgress):
                state.save_progress(root, semantic_state(), expected_revision=0)
            self.assertEqual(outside.read_text(), "untouched")

    def test_progress_is_removed_only_after_approved_successful_wrap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = state.save_progress(root, semantic_state(), expected_revision=0)

            self.assertFalse(state.finish_wrap(root, path.stem, approved=False, write_succeeded=True))
            self.assertTrue(path.exists())
            self.assertFalse(state.finish_wrap(root, path.stem, approved=True, write_succeeded=False))
            self.assertTrue(path.exists())
            self.assertTrue(state.finish_wrap(root, path.stem, approved=True, write_succeeded=True))
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
