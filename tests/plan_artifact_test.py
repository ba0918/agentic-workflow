import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
PLAN_MODULE = ROOT / "skills/ba0918-plan/scripts/plan_artifact.py"
SPEC = importlib.util.spec_from_file_location("plan_artifact", PLAN_MODULE)
plan_artifact = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(plan_artifact)


PLAN_TEXT = """# 小さな変更のplan

**Plan ID:** `20260822022624`
**Plan revision:** `1`

## 目的

利用者が変更範囲を判断できるplanを作る。
"""


class ContentIdentityTest(unittest.TestCase):
    def test_same_content_has_same_identity_and_changed_content_does_not(self) -> None:
        first = plan_artifact.content_identity(PLAN_TEXT)

        self.assertEqual(first, plan_artifact.content_identity(PLAN_TEXT))
        self.assertTrue(first.startswith("sha256:"))
        self.assertNotEqual(first, plan_artifact.content_identity(PLAN_TEXT + "\n変更"))

    def test_identity_cli_reads_the_unwritten_draft_from_stdin(self) -> None:
        output = io.StringIO()

        with mock.patch("sys.stdin", io.StringIO(PLAN_TEXT)), contextlib.redirect_stdout(output):
            exit_code = plan_artifact.main(["identity"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue().strip(), plan_artifact.content_identity(PLAN_TEXT))


class RegisteredPlanConsumerTest(unittest.TestCase):
    def test_current_registered_plan_is_returned_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=identity,
                switch_confirmed=False,
                worktree_dirty=False,
            )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            registered = plan_artifact.read_registered_plan(root)

            self.assertEqual(registered.plan_id, "20260822022624")
            self.assertEqual(registered.revision, 1)
            self.assertEqual(registered.content_identity, identity)
            self.assertEqual(registered.state, "current")
            self.assertEqual(registered.text, PLAN_TEXT)
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_explicit_registered_plan_may_be_held(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_identity = plan_artifact.content_identity(PLAN_TEXT)
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=first_identity,
                switch_confirmed=False,
                worktree_dirty=False,
            )
            second = PLAN_TEXT.replace("20260822022624", "20260822022625")
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022625",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022625_second.md",
                text=second,
                approved_identity=plan_artifact.content_identity(second),
                switch_confirmed=True,
                worktree_dirty=False,
            )

            registered = plan_artifact.read_registered_plan(
                root,
                ".agents/artifacts/plans/20260822022624_first.md",
            )

            self.assertEqual(registered.plan_id, "20260822022624")
            self.assertEqual(registered.state, "held")

    def test_missing_registration_is_distinct_from_an_empty_publication_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaises(plan_artifact.PlanRegistrationMissing):
                plan_artifact.read_registered_plan(root)

            self.assertFalse((root / ".agents").exists())

    def test_registered_plan_identity_mismatch_is_rejected_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)
            target = plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=identity,
                switch_confirmed=False,
                worktree_dirty=False,
            )
            target.write_text(PLAN_TEXT + "changed\n", encoding="utf-8")
            index_before = (target.parent / "open-plans.json").read_bytes()

            with self.assertRaises(plan_artifact.RegisteredPlanMismatch):
                plan_artifact.read_registered_plan(root)

            self.assertEqual((target.parent / "open-plans.json").read_bytes(), index_before)
            self.assertEqual(target.read_text(encoding="utf-8"), PLAN_TEXT + "changed\n")

    def test_unsafe_registered_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plans = root / ".agents/artifacts/plans"
            plans.mkdir(parents=True)
            (plans / "open-plans.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "current": "20260822022624",
                        "plans": [
                            {
                                "id": "20260822022624",
                                "path": "../outside.md",
                                "revision": 1,
                                "content_identity": "sha256:" + "0" * 64,
                                "state": "current",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(plan_artifact.UnsafePlanPath):
                plan_artifact.read_registered_plan(root)


class PublishPlanTest(unittest.TestCase):
    def test_confirmed_draft_is_written_and_registered_as_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)

            result = plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=identity,
                switch_confirmed=False,
                worktree_dirty=False,
            )

            self.assertEqual(result.read_text(encoding="utf-8"), PLAN_TEXT)
            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["current"], "20260822022624")
            self.assertEqual(index["plans"][0]["content_identity"], identity)
            self.assertEqual(index["plans"][0]["state"], "current")

    def test_identity_mismatch_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaises(plan_artifact.IdentityMismatch):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                    text=PLAN_TEXT,
                    approved_identity="sha256:" + "0" * 64,
                    switch_confirmed=False,
                    worktree_dirty=False,
                )

            self.assertFalse((root / ".agents").exists())

    def test_existing_current_plan_requires_confirmed_switch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_identity = plan_artifact.content_identity(PLAN_TEXT)
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=first_identity,
                switch_confirmed=False,
                worktree_dirty=False,
            )

            with self.assertRaises(plan_artifact.CurrentPlanConflict):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022625",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022625_second.md",
                    text=PLAN_TEXT.replace("20260822022624", "20260822022625"),
                    approved_identity=plan_artifact.content_identity(
                        PLAN_TEXT.replace("20260822022624", "20260822022625")
                    ),
                    switch_confirmed=False,
                    worktree_dirty=False,
                )

            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["current"], "20260822022624")
            self.assertEqual(len(index["plans"]), 1)

    def test_dirty_worktree_blocks_even_a_confirmed_switch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=plan_artifact.content_identity(PLAN_TEXT),
                switch_confirmed=False,
                worktree_dirty=False,
            )
            second = PLAN_TEXT.replace("20260822022624", "20260822022625")

            with self.assertRaises(plan_artifact.DirtyWorktree):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022625",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022625_second.md",
                    text=second,
                    approved_identity=plan_artifact.content_identity(second),
                    switch_confirmed=True,
                    worktree_dirty=True,
                )

            self.assertFalse(
                (root / ".agents/artifacts/plans/20260822022625_second.md").exists()
            )

    def test_confirmed_switch_holds_the_previous_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=plan_artifact.content_identity(PLAN_TEXT),
                switch_confirmed=False,
                worktree_dirty=False,
            )
            second = PLAN_TEXT.replace("20260822022624", "20260822022625")
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022625",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022625_second.md",
                text=second,
                approved_identity=plan_artifact.content_identity(second),
                switch_confirmed=True,
                worktree_dirty=False,
            )

            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            states = {item["id"]: item["state"] for item in index["plans"]}
            self.assertEqual(index["current"], "20260822022625")
            self.assertEqual(states["20260822022624"], "held")
            self.assertEqual(states["20260822022625"], "current")

    def test_paths_outside_the_plan_store_and_symlinks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)

            with self.assertRaises(plan_artifact.UnsafePlanPath):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path="../outside.md",
                    text=PLAN_TEXT,
                    approved_identity=identity,
                    switch_confirmed=False,
                    worktree_dirty=False,
                )

            plans = root / ".agents/artifacts/plans"
            plans.mkdir(parents=True)
            outside = root / "outside.md"
            outside.write_text("untouched", encoding="utf-8")
            (plans / "20260822022624_link.md").symlink_to(outside)
            with self.assertRaises(plan_artifact.UnsafePlanPath):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022624_link.md",
                    text=PLAN_TEXT,
                    approved_identity=identity,
                    switch_confirmed=False,
                    worktree_dirty=False,
                )
            self.assertEqual(outside.read_text(encoding="utf-8"), "untouched")

    def test_new_revision_preserves_the_previous_revision_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=plan_artifact.content_identity(PLAN_TEXT),
                switch_confirmed=False,
                worktree_dirty=False,
            )
            revised = PLAN_TEXT.replace("revision:** `1`", "revision:** `2`") + "\n手順を修正する。\n"

            result = plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=2,
                relative_path=".agents/artifacts/plans/20260822022624_small-change-r2.md",
                text=revised,
                approved_identity=plan_artifact.content_identity(revised),
                switch_confirmed=False,
                worktree_dirty=False,
            )

            self.assertEqual(result.read_text(encoding="utf-8"), revised)
            self.assertTrue(
                (root / ".agents/artifacts/plans/20260822022624_small-change.md").is_file()
            )
            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(index["plans"]), 1)
            self.assertEqual(index["plans"][0]["revision"], 2)
            self.assertEqual(index["plans"][0]["path"], result.relative_to(root).as_posix())


if __name__ == "__main__":
    unittest.main()
