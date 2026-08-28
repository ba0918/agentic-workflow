import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "tools/workflow-runtime/brainstorm/draft.py"
SPEC = importlib.util.spec_from_file_location("brainstorm_draft", MODULE)
assert SPEC is not None
draft = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(draft)

class BrainstormDocumentWriterTest(unittest.TestCase):
    def test_writes_the_canonical_document_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = draft.write_document(root, destination="docs/spec/example.md", text="# Spec\n")
            self.assertEqual(path, root / "docs/spec/example.md")
            self.assertEqual(path.read_text(encoding="utf-8"), "# Spec\n")
            self.assertFalse((root / ".agents").exists())

    def test_allows_only_spec_agreement_and_root_roadmap_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for destination in (
                "docs/spec/nested/example.md", "docs/agreements/decision.md", "ROADMAP.md"
            ):
                self.assertTrue(draft.write_document(root, destination=destination, text="# Document\n").is_file())
            for destination in (
                ".git/config", "src/app.py", "config/release.md", "docs/README.md",
                "docs/agreements/nested/decision.md", "ROADMAP.txt",
            ):
                with self.assertRaises(draft.UnsafeDocumentPath):
                    draft.write_document(root, destination=destination, text="bad")

    def test_rejects_traversal_agents_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for destination in ("../bad.md", "/bad.md", ".agents/bad.md"):
                with self.assertRaises(draft.UnsafeDocumentPath):
                    draft.write_document(root, destination=destination, text="bad")
            outside = root / "outside"
            outside.mkdir()
            (root / "docs").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(draft.UnsafeDocumentPath):
                draft.write_document(root, destination="docs/spec/example.md", text="bad")

    def test_failed_atomic_replace_keeps_existing_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "docs/spec/example.md"
            destination.parent.mkdir(parents=True)
            destination.write_text("old", encoding="utf-8")
            with mock.patch.object(draft.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    draft.write_document(root, destination="docs/spec/example.md", text="new")
            self.assertEqual(destination.read_text(encoding="utf-8"), "old")

    def test_old_draft_and_publish_apis_are_absent(self) -> None:
        self.assertFalse(hasattr(draft, "save_draft"))
        self.assertFalse(hasattr(draft, "publish_drafts"))
        source = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("content_identity", source)
        self.assertNotIn("manifest", source)

if __name__ == "__main__":
    unittest.main()
