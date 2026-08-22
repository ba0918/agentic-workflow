import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
DRAFT_MODULE = ROOT / "skills/ba0918-brainstorm/scripts/draft.py"
SPEC = importlib.util.spec_from_file_location("brainstorm_draft", DRAFT_MODULE)
draft = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(draft)


SESSION = "20260823T050000Z-demo"
SPEC_TEXT = "# 仕様\n\n`EX-001` 表示名は空であってはならない。\n"
ROADMAP_TEXT = "# ROADMAP\n\n## Phase 1\n"


class SaveDraftTest(unittest.TestCase):
    def test_draft_is_saved_per_destination_with_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            receipt = draft.save_draft(
                root, session_id=SESSION, destination="docs/spec/example.md", text=SPEC_TEXT
            )

            self.assertEqual(
                receipt.path.relative_to(root).as_posix(),
                f".agents/tmp/ideas/{SESSION}/example.md",
            )
            self.assertEqual(receipt.path.read_bytes(), SPEC_TEXT.encode("utf-8"))
            self.assertEqual(receipt.content_identity, draft.content_identity(SPEC_TEXT))
            manifest = json.loads((receipt.path.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["drafts"]["docs/spec/example.md"],
                {"path": "example.md", "content_identity": receipt.content_identity},
            )
            self.assertFalse((root / "docs").exists())

    def test_two_destinations_with_the_same_basename_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            first = draft.save_draft(
                root, session_id=SESSION, destination="docs/spec/a/index.md", text=SPEC_TEXT
            )
            second = draft.save_draft(
                root, session_id=SESSION, destination="docs/spec/b/index.md", text=ROADMAP_TEXT
            )

            self.assertNotEqual(first.path, second.path)
            self.assertEqual(first.path.read_text(encoding="utf-8"), SPEC_TEXT)
            self.assertEqual(second.path.read_text(encoding="utf-8"), ROADMAP_TEXT)

    def test_existing_draft_is_replaced_only_when_its_identity_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = draft.save_draft(
                root, session_id=SESSION, destination="docs/spec/example.md", text=SPEC_TEXT
            )
            revised = SPEC_TEXT + "\n`EX-002` 追記。\n"

            with self.assertRaises(draft.DraftConflict):
                draft.save_draft(
                    root, session_id=SESSION, destination="docs/spec/example.md", text=revised
                )
            with self.assertRaises(draft.DraftConflict):
                draft.save_draft(
                    root,
                    session_id=SESSION,
                    destination="docs/spec/example.md",
                    text=revised,
                    replace_identity="sha256:" + "0" * 64,
                )
            self.assertEqual(first.path.read_text(encoding="utf-8"), SPEC_TEXT)

            second = draft.save_draft(
                root,
                session_id=SESSION,
                destination="docs/spec/example.md",
                text=revised,
                replace_identity=first.content_identity,
            )

            self.assertEqual(second.path, first.path)
            self.assertEqual(second.path.read_text(encoding="utf-8"), revised)

    def test_unsafe_destinations_and_session_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for destination in ("/abs/spec.md", "../escape.md", ".agents/artifacts/x.md", "docs/"):
                with self.subTest(destination):
                    with self.assertRaises(draft.UnsafeDraftPath):
                        draft.save_draft(
                            root, session_id=SESSION, destination=destination, text=SPEC_TEXT
                        )
            with self.assertRaises(draft.UnsafeDraftPath):
                draft.save_draft(
                    root, session_id="../evil", destination="docs/spec/example.md", text=SPEC_TEXT
                )
            self.assertFalse((root / ".agents").exists())

    def test_save_cli_reads_stdin_and_prints_path_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(SPEC_TEXT)), contextlib.redirect_stdout(stdout):
                code = draft.main(
                    ["save", "--repo", str(root), "--session-id", SESSION,
                     "--destination", "docs/spec/example.md"]
                )

            self.assertEqual(code, 0)
            printed = json.loads(stdout.getvalue())
            self.assertEqual(printed["path"], f".agents/tmp/ideas/{SESSION}/example.md")
            self.assertEqual(printed["destination"], "docs/spec/example.md")
            self.assertEqual(printed["content_identity"], draft.content_identity(SPEC_TEXT))


class PublishDraftsTest(unittest.TestCase):
    def _two_drafts(self, root: Path) -> dict[str, str]:
        (root / "docs/spec").mkdir(parents=True)
        (root / "docs/spec/example.md").write_text("# 旧仕様\n", encoding="utf-8")
        spec = draft.save_draft(
            root, session_id=SESSION, destination="docs/spec/example.md", text=SPEC_TEXT
        )
        roadmap = draft.save_draft(
            root, session_id=SESSION, destination="ROADMAP.md", text=ROADMAP_TEXT
        )
        return {spec.destination: spec.content_identity, roadmap.destination: roadmap.content_identity}

    def test_approved_drafts_replace_their_destinations_and_leave_no_temporary_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approved = self._two_drafts(root)

            published = draft.publish_drafts(root, session_id=SESSION, approved=approved)

            self.assertEqual((root / "docs/spec/example.md").read_text(encoding="utf-8"), SPEC_TEXT)
            self.assertEqual((root / "ROADMAP.md").read_text(encoding="utf-8"), ROADMAP_TEXT)
            self.assertEqual(sorted(published), ["ROADMAP.md", "docs/spec/example.md"])
            self.assertFalse((root / f".agents/tmp/ideas/{SESSION}").exists())

    def test_one_edited_draft_blocks_every_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approved = self._two_drafts(root)
            edited = ROADMAP_TEXT + "\n人間が直接直した行\n"
            (root / f".agents/tmp/ideas/{SESSION}/ROADMAP.md").write_text(edited, encoding="utf-8")

            with self.assertRaises(draft.IdentityMismatch):
                draft.publish_drafts(root, session_id=SESSION, approved=approved)

            self.assertEqual((root / "docs/spec/example.md").read_text(encoding="utf-8"), "# 旧仕様\n")
            self.assertFalse((root / "ROADMAP.md").exists())
            self.assertEqual(
                (root / f".agents/tmp/ideas/{SESSION}/ROADMAP.md").read_text(encoding="utf-8"), edited
            )

    def test_approval_must_name_every_draft_in_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approved = self._two_drafts(root)
            del approved["ROADMAP.md"]

            with self.assertRaises(draft.IdentityMismatch):
                draft.publish_drafts(root, session_id=SESSION, approved=approved)

            self.assertEqual((root / "docs/spec/example.md").read_text(encoding="utf-8"), "# 旧仕様\n")

    def test_a_failure_after_the_first_move_restores_the_previous_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approved = self._two_drafts(root)
            original_replace = os.replace
            calls = {"n": 0}

            def failing_second_move(src, dst):
                if Path(dst).name == "ROADMAP.md" and Path(src).parent.name == SESSION:
                    raise OSError("disk full")
                original_replace(src, dst)

            with mock.patch.object(draft.os, "replace", failing_second_move):
                with self.assertRaises(OSError):
                    draft.publish_drafts(root, session_id=SESSION, approved=approved)

            self.assertEqual((root / "docs/spec/example.md").read_text(encoding="utf-8"), "# 旧仕様\n")
            self.assertFalse((root / "ROADMAP.md").exists())
            session_dir = root / f".agents/tmp/ideas/{SESSION}"
            self.assertEqual((session_dir / "example.md").read_text(encoding="utf-8"), SPEC_TEXT)
            self.assertEqual((session_dir / "ROADMAP.md").read_text(encoding="utf-8"), ROADMAP_TEXT)

    def test_publish_cli_takes_destination_identity_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approved = self._two_drafts(root)
            stdout = io.StringIO()
            argv = ["publish", "--repo", str(root), "--session-id", SESSION]
            for destination, identity in approved.items():
                argv += ["--approve", f"{destination}={identity}"]
            with contextlib.redirect_stdout(stdout):
                code = draft.main(argv)

            self.assertEqual(code, 0)
            self.assertEqual(sorted(json.loads(stdout.getvalue())["published"]), ["ROADMAP.md", "docs/spec/example.md"])


if __name__ == "__main__":
    unittest.main()
