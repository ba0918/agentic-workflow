import importlib.util
import inspect
import itertools
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[3]
PLAN_MODULE = ROOT / "tools/workflow-runtime/plan/plan_artifact.py"
SPEC = importlib.util.spec_from_file_location("plan_artifact", PLAN_MODULE)
plan_artifact = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(plan_artifact)


_DRAFT_SEQUENCE = itertools.count(1)


def publish_text(root: Path, **kwargs):
    """Save the draft first, then publish it: the production path always starts from a draft."""
    text = kwargs.pop("text")
    plan_id = kwargs["plan_id"]
    revision = kwargs["revision"]
    slug = f"draft-{next(_DRAFT_SEQUENCE)}"
    draft = plan_artifact.save_draft(root, plan_id=plan_id, revision=revision, slug=slug, text=text)
    return plan_artifact.publish_plan(root, source=draft.path, **kwargs)


SPEC_PATH = "docs/spec/deployment.md"
SPEC_TEXT = "# 配備の仕様\n\n## 配備の入力\n\n## 配備の確認\n"
SPEC_IDENTITY = plan_artifact.content_identity(SPEC_TEXT)


@contextlib.contextmanager
def plan_root():
    """A temporary repository that already holds the specification the fixture plans cite."""
    with tempfile.TemporaryDirectory() as directory:
        spec = Path(directory) / SPEC_PATH
        spec.parent.mkdir(parents=True)
        spec.write_text(SPEC_TEXT, encoding="utf-8")
        yield directory


PLAN_HEADER = f"""# 小さな変更のplan

**Plan ID:** `20260822022624`
**Plan revision:** `1`

**Target specifications:**

- `docs/spec/deployment.md`
  - content identity: `{SPEC_IDENTITY}`
  - sections: `配備の入力`, `配備の確認`

## 目的

利用者が変更範囲を判断できるplanを作る。

## Scope

```text
config/
  deployment.json
docs/
  guide/
    deploy.md
```
"""

PLAN_TEXT = PLAN_HEADER + """
## Steps

### 1. 配備の入力を整える

**Completion:** test

### 2. 手引きを書く

**Completion:** artifact

### 3. 実機で配備を確かめる

**Completion:** external
"""


PLAN_WITH_CHECK_STEP = PLAN_HEADER + """
## Steps

### 1. 配備の入力を整える

**Completion:** test

### 2. 手引きを書く

**Completion:** artifact

### 3. 実機で配備を確かめる

**Completion:** external

### 4. 配布の複製を作り直す

**Completion:** check

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`

確かめること:

- `git status --porcelain` が何も出さない
"""

CHECK_DECLARATION = (
    "**Checks:**\n\n"
    "- `bunx agentic-skill-vendor gen`\n"
    "- `bunx agentic-skill-vendor verify`\n"
)


PLAN_WITH_HUMAN_GATE = PLAN_HEADER + r"""
## Steps

### 1. 配備前に対象を確認する

**Completion:** artifact

**Human gates:**

```json
{
  "version": 1,
  "gates": [
    {
      "gate_id": "approve-deployment-input",
      "sections": ["配備の入力"],
      "criterion": "対象fileが承認済みの内容である",
      "target": {
        "kind": "files",
        "paths": ["config/deployment.json"]
      },
      "timing": "before_edit",
      "allowed_results": ["approved", "rejected"]
    }
  ]
}
```
"""


class PlanCreationInstructionTest(unittest.TestCase):
    def test_required_human_gate_has_a_versioned_machine_readable_declaration(self) -> None:
        instruction = (
            ROOT / "skills/ba0918-plan/references/creation.md"
        ).read_text(encoding="utf-8")

        self.assertIn("**Human gates:**", instruction)
        self.assertIn('"version": 1', instruction)
        for field in (
            "gate_id",
            "sections",
            "criterion",
            "target",
            "timing",
            "allowed_results",
        ):
            self.assertIn(f'"{field}"', instruction)
        self.assertIn("Omit the declaration when no human gate is required", instruction)


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


class PlanHeaderTest(unittest.TestCase):
    def test_plan_id_revision_and_target_specifications_are_read_from_the_header(self) -> None:
        header = plan_artifact.read_plan_header(PLAN_TEXT)

        self.assertEqual(header.plan_id, "20260822022624")
        self.assertEqual(header.revision, 1)
        self.assertEqual(len(header.specifications), 1)
        self.assertEqual(header.specifications[0].path, "docs/spec/deployment.md")
        self.assertEqual(header.specifications[0].content_identity, SPEC_IDENTITY)
        self.assertEqual(header.specifications[0].sections, ("配備の入力", "配備の確認"))

    def test_unreadable_header_is_rejected_with_the_missing_part_named(self) -> None:
        invalid_plans = {
            "missing plan id": (PLAN_TEXT.replace("**Plan ID:** `20260822022624`\n", ""), "Plan ID"),
            "missing revision": (PLAN_TEXT.replace("**Plan revision:** `1`\n", ""), "Plan revision"),
            "missing target specifications": (PLAN_TEXT.replace("**Target specifications:**", "**References:**"), "Target specifications"),
            "no specification item": (
                PLAN_TEXT.replace("- `docs/spec/deployment.md`\n", "").replace(
                    f"  - content identity: `{SPEC_IDENTITY}`\n  - sections: `配備の入力`, `配備の確認`\n", ""
                ),
                "Target specifications",
            ),
            "malformed identity": (PLAN_TEXT.replace(SPEC_IDENTITY, "sha256:zz"), "content identity"),
            "missing sections": (PLAN_TEXT.replace("  - sections: `配備の入力`, `配備の確認`\n", ""), "sections"),
            "absolute path": (PLAN_TEXT.replace("docs/spec/deployment.md", "/etc/deployment.md"), "/etc/deployment.md"),
            "traversal": (PLAN_TEXT.replace("docs/spec/deployment.md", "../deployment.md"), "../deployment.md"),
        }

        for case, (malformed, named) in invalid_plans.items():
            with self.subTest(case=case):
                with self.assertRaisesRegex(plan_artifact.InvalidPlanFormat, re.escape(named)):
                    plan_artifact.read_plan_header(malformed)

    def test_target_specification_identity_must_match_the_file_in_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = root / SPEC_PATH
            spec.parent.mkdir(parents=True)
            spec.write_text(SPEC_TEXT, encoding="utf-8")

            plan_artifact.verify_target_specifications(root, plan_artifact.read_plan_header(PLAN_TEXT))

            spec.write_text(SPEC_TEXT + "改訂\n", encoding="utf-8")
            with self.assertRaisesRegex(plan_artifact.TargetSpecificationMismatch, SPEC_PATH):
                plan_artifact.verify_target_specifications(root, plan_artifact.read_plan_header(PLAN_TEXT))

    def test_missing_target_specification_file_is_reported_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(plan_artifact.TargetSpecificationMismatch, "docs/spec/deployment.md"):
                plan_artifact.verify_target_specifications(
                    Path(directory), plan_artifact.read_plan_header(PLAN_TEXT)
                )


class PlanScopeAndStepsTest(unittest.TestCase):
    def test_scope_tree_expands_to_repository_relative_paths(self) -> None:
        self.assertEqual(
            plan_artifact.read_plan_scope(PLAN_TEXT),
            ("config/deployment.json", "docs/guide/deploy.md"),
        )

    def test_scope_tree_line_may_hold_several_segments_as_in_the_specification_example(self) -> None:
        nested_root = PLAN_TEXT.replace("config/\n  deployment.json\n", "ops/config/\n  deployment.json\n")

        self.assertEqual(
            plan_artifact.read_plan_scope(nested_root),
            ("ops/config/deployment.json", "docs/guide/deploy.md"),
        )

    def test_scope_tree_accepts_any_consistent_indent_width(self) -> None:
        four_space = PLAN_TEXT.replace("  deployment.json", "    deployment.json").replace(
            "  guide/\n    deploy.md", "    guide/\n        deploy.md"
        )

        self.assertEqual(
            plan_artifact.read_plan_scope(four_space),
            ("config/deployment.json", "docs/guide/deploy.md"),
        )

    def test_unreadable_scope_tree_is_rejected(self) -> None:
        invalid_plans = {
            "annotation": PLAN_TEXT.replace("  deployment.json", "  deployment.json  # 設定"),
            "absolute path": PLAN_TEXT.replace("config/\n", "/config/\n"),
            "traversal": PLAN_TEXT.replace("  deployment.json", "  ../deployment.json"),
            "missing heading": PLAN_TEXT.replace("## Scope", "## Changed files"),
            "empty block": PLAN_TEXT.replace(
                "config/\n  deployment.json\ndocs/\n  guide/\n    deploy.md\n", ""
            ),
            "child without parent directory": PLAN_TEXT.replace("config/\n", "config\n"),
        }

        for case, malformed in invalid_plans.items():
            with self.subTest(case=case):
                with self.assertRaises(plan_artifact.InvalidPlanFormat):
                    plan_artifact.read_plan_scope(malformed)

class SaveDraftTest(unittest.TestCase):
    def test_draft_is_saved_under_the_temporary_plan_store_with_identical_bytes(self) -> None:
        with plan_root() as directory:
            root = Path(directory)

            receipt = plan_artifact.save_draft(
                root, plan_id="20260822022624", revision=1, slug="small-change", text=PLAN_TEXT
            )

            self.assertEqual(
                receipt.path.relative_to(root).as_posix(),
                ".agents/tmp/plans/20260822022624_small-change_r1_draft.md",
            )
            self.assertEqual(receipt.path.read_bytes(), PLAN_TEXT.encode("utf-8"))
            self.assertEqual(receipt.content_identity, plan_artifact.content_identity(PLAN_TEXT))
            self.assertFalse((root / ".agents/artifacts").exists())

    def test_existing_draft_is_replaced_only_when_its_identity_is_named(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            first = plan_artifact.save_draft(
                root, plan_id="20260822022624", revision=1, slug="small-change", text=PLAN_TEXT
            )
            revised = PLAN_TEXT + "\n追記\n"

            with self.assertRaises(plan_artifact.DraftConflict):
                plan_artifact.save_draft(
                    root, plan_id="20260822022624", revision=1, slug="small-change", text=revised
                )
            with self.assertRaises(plan_artifact.DraftConflict):
                plan_artifact.save_draft(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    slug="small-change",
                    text=revised,
                    replace_identity="sha256:" + "0" * 64,
                )
            self.assertEqual(first.path.read_text(encoding="utf-8"), PLAN_TEXT)

            second = plan_artifact.save_draft(
                root,
                plan_id="20260822022624",
                revision=1,
                slug="small-change",
                text=revised,
                replace_identity=first.content_identity,
            )

            self.assertEqual(second.path, first.path)
            self.assertEqual(second.path.read_text(encoding="utf-8"), revised)

    def test_draft_slug_cannot_escape_the_temporary_plan_store(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            for slug in ("../escape", "nested/slug", "/absolute", "UPPER CASE"):
                with self.subTest(slug):
                    with self.assertRaises(plan_artifact.UnsafePlanPath):
                        plan_artifact.save_draft(
                            root, plan_id="20260822022624", revision=1, slug=slug, text=PLAN_TEXT
                        )
            self.assertFalse((root / ".agents").exists())

    def test_draft_cli_reads_stdin_and_prints_path_and_identity(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            stdout = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(PLAN_TEXT)), contextlib.redirect_stdout(stdout):
                code = plan_artifact.main(
                    ["draft", "--repo", str(root), "--plan-id", "20260822022624",
                     "--revision", "1", "--slug", "small-change"]
                )

            self.assertEqual(code, 0)
            printed = json.loads(stdout.getvalue())
            self.assertEqual(printed["path"], ".agents/tmp/plans/20260822022624_small-change_r1_draft.md")
            self.assertEqual(printed["content_identity"], plan_artifact.content_identity(PLAN_TEXT))


class DraftValidationTest(unittest.TestCase):
    def test_a_machine_read_part_that_cannot_be_read_is_named_and_the_draft_is_not_saved(self) -> None:
        cases = {
            "Scope": PLAN_TEXT.replace("```text", "```"),
            "Target specifications": PLAN_TEXT.replace("**Target specifications:**", "**対象仕様:**"),
        }
        for part, unreadable in cases.items():
            with self.subTest(part=part), plan_root() as directory:
                root = Path(directory)

                with self.assertRaisesRegex(plan_artifact.InvalidPlanFormat, part):
                    plan_artifact.save_draft(
                        root, plan_id="20260822022624", revision=1, slug="small-change", text=unreadable
                    )

                self.assertFalse((root / ".agents/tmp/plans").exists())

    def test_plan_citing_a_changed_specification_is_not_saved_as_a_draft(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            (root / SPEC_PATH).write_text(SPEC_TEXT + "改訂\n", encoding="utf-8")

            with self.assertRaisesRegex(plan_artifact.TargetSpecificationMismatch, SPEC_PATH):
                plan_artifact.save_draft(
                    root, plan_id="20260822022624", revision=1, slug="small-change", text=PLAN_TEXT
                )

            self.assertFalse((root / ".agents/tmp/plans").exists())

    def test_a_plan_whose_steps_are_written_freely_is_saved_as_a_draft(self) -> None:
        """Steps are prose the agent reads, so their wording is not a reason to refuse a draft."""
        with plan_root() as directory:
            root = Path(directory)
            free_form = PLAN_TEXT.replace(
                "### 1. 配備の入力を整える\n\n**Completion:** test\n",
                "### 手順その一 — 配備の入力を整える\n\nテストで示します。\n",
            )

            receipt = plan_artifact.save_draft(
                root, plan_id="20260822022624", revision=1, slug="small-change", text=free_form
            )

            self.assertEqual(receipt.path.read_text(encoding="utf-8"), free_form)

    def test_an_id_or_revision_the_prose_does_not_repeat_is_not_a_reason_to_refuse(self) -> None:
        """The id and revision are read out of the prose by the agent, never matched by machine."""
        with plan_root() as directory:
            root = Path(directory)
            for case, plan_id, revision in (("id", "20260822022625", 1), ("revision", "20260822022624", 2)):
                with self.subTest(case=case):
                    receipt = plan_artifact.save_draft(
                        root, plan_id=plan_id, revision=revision, slug=f"case-{case}", text=PLAN_TEXT
                    )
                    self.assertTrue(receipt.path.is_file())

    def test_draft_cli_reports_the_unreadable_part_and_fails(self) -> None:
        with plan_root() as directory:
            unreadable = PLAN_TEXT.replace("## Scope", "## Changed files")
            stdout, stderr = io.StringIO(), io.StringIO()

            with mock.patch("sys.stdin", io.StringIO(unreadable)), contextlib.redirect_stdout(
                stdout
            ), contextlib.redirect_stderr(stderr):
                exit_code = plan_artifact.main(
                    ["draft", "--repo", directory, "--plan-id", "20260822022624", "--revision", "1", "--slug", "x"]
                )

            self.assertNotEqual(exit_code, 0)
            self.assertIn("Scope", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")

    def test_publication_stops_when_the_specification_changed_after_the_draft(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            draft = plan_artifact.save_draft(
                root, plan_id="20260822022624", revision=1, slug="small-change", text=PLAN_TEXT
            )
            (root / SPEC_PATH).write_text(SPEC_TEXT + "改訂\n", encoding="utf-8")

            with self.assertRaisesRegex(plan_artifact.TargetSpecificationMismatch, SPEC_PATH):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                    source=draft.path,
                    approved_identity=draft.content_identity,
                )

            self.assertTrue(draft.path.is_file())
            self.assertFalse((root / ".agents/artifacts/plans").exists())


class PublishPlanTest(unittest.TestCase):
    def test_publication_moves_the_approved_draft_and_leaves_no_temporary_file(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            draft = plan_artifact.save_draft(
                root, plan_id="20260822022624", revision=1, slug="small-change", text=PLAN_TEXT
            )

            result = plan_artifact.publish_plan(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                source=draft.path,
                approved_identity=draft.content_identity,
            )

            self.assertEqual(result.read_text(encoding="utf-8"), PLAN_TEXT)
            self.assertEqual(plan_artifact.content_identity(result.read_text(encoding="utf-8")), draft.content_identity)
            self.assertFalse(draft.path.exists())

    def test_an_edited_draft_is_rejected_and_kept_for_the_dialogue(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            draft = plan_artifact.save_draft(
                root, plan_id="20260822022624", revision=1, slug="small-change", text=PLAN_TEXT
            )
            edited = PLAN_TEXT + "\n人間が直接直した行\n"
            draft.path.write_text(edited, encoding="utf-8")

            with self.assertRaises(plan_artifact.IdentityMismatch):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                    source=draft.path,
                    approved_identity=draft.content_identity,
                )

            self.assertEqual(draft.path.read_text(encoding="utf-8"), edited)
            self.assertFalse((root / ".agents/artifacts").exists())

    def test_a_source_outside_the_temporary_plan_store_is_rejected(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            elsewhere = root / "elsewhere.md"
            elsewhere.write_text(PLAN_TEXT, encoding="utf-8")

            with self.assertRaises(plan_artifact.UnsafePlanPath):
                plan_artifact.publish_plan(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                    source=elsewhere,
                    approved_identity=plan_artifact.content_identity(PLAN_TEXT),
                )

            self.assertTrue(elsewhere.exists())
            self.assertFalse((root / ".agents/artifacts").exists())

    def test_identity_mismatch_writes_nothing(self) -> None:
        with plan_root() as directory:
            root = Path(directory)

            with self.assertRaises(plan_artifact.IdentityMismatch):
                publish_text(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                    text=PLAN_TEXT,
                    approved_identity="sha256:" + "0" * 64,
                )

            self.assertFalse((root / ".agents/artifacts").exists())

    def test_a_second_plan_is_published_alongside_the_first_without_a_confirmation(self) -> None:
        """Nothing is "current", so a second unfinished plan is not a switch to confirm."""
        self.assertNotIn("worktree_dirty", inspect.signature(plan_artifact.publish_plan).parameters)
        self.assertNotIn("switch_confirmed", inspect.signature(plan_artifact.publish_plan).parameters)
        with plan_root() as directory:
            root = Path(directory)
            publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=plan_artifact.content_identity(PLAN_TEXT),
            )
            (root / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
            second = PLAN_TEXT.replace("20260822022624", "20260822022625")

            publish_text(
                root,
                plan_id="20260822022625",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022625_second.md",
                text=second,
                approved_identity=plan_artifact.content_identity(second),
            )

            self.assertTrue((root / ".agents/artifacts/plans/20260822022624_first.md").exists())
            self.assertTrue((root / ".agents/artifacts/plans/20260822022625_second.md").exists())

    def test_paths_outside_the_plan_store_and_symlinks_are_rejected(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)

            with self.assertRaises(plan_artifact.UnsafePlanPath):
                publish_text(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path="../outside.md",
                    text=PLAN_TEXT,
                    approved_identity=identity,
                )

            plans = root / ".agents/artifacts/plans"
            plans.mkdir(parents=True)
            outside = root / "outside.md"
            outside.write_text("untouched", encoding="utf-8")
            (plans / "20260822022624_link.md").symlink_to(outside)
            with self.assertRaises(plan_artifact.UnsafePlanPath):
                publish_text(
                    root,
                    plan_id="20260822022624",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022624_link.md",
                    text=PLAN_TEXT,
                    approved_identity=identity,
                )
            self.assertEqual(outside.read_text(encoding="utf-8"), "untouched")

    def test_new_revision_preserves_the_previous_revision_file(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=plan_artifact.content_identity(PLAN_TEXT),
            )
            revised = PLAN_TEXT.replace("revision:** `1`", "revision:** `2`") + "\n手順を修正する。\n"

            result = publish_text(
                root,
                plan_id="20260822022624",
                revision=2,
                relative_path=".agents/artifacts/plans/20260822022624_small-change-r2.md",
                text=revised,
                approved_identity=plan_artifact.content_identity(revised),
            )

            self.assertEqual(result.read_text(encoding="utf-8"), revised)
            self.assertTrue(
                (root / ".agents/artifacts/plans/20260822022624_small-change.md").is_file()
            )


if __name__ == "__main__":
    unittest.main()
