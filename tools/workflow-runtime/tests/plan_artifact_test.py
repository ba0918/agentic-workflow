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

    def test_steps_are_read_in_order_with_their_completion_kind(self) -> None:
        steps = plan_artifact.read_plan_steps(PLAN_TEXT)

        self.assertEqual([step.number for step in steps], [1, 2, 3])
        self.assertEqual(steps[0].title, "配備の入力を整える")
        self.assertEqual(
            [step.completion_kind for step in steps],
            ["test", "artifact", "external"],
        )

    def test_unreadable_steps_are_rejected(self) -> None:
        invalid_plans = {
            "missing steps heading": PLAN_TEXT.replace("## Steps", "## Procedure"),
            "no step": PLAN_HEADER + "\n## Steps\n\n本文だけ\n",
            "gap in numbering": PLAN_TEXT.replace("### 2.", "### 4."),
            "duplicate number": PLAN_TEXT.replace("### 2.", "### 1."),
            "not starting at one": PLAN_TEXT.replace("### 1.", "### 0."),
            "missing completion kind": PLAN_TEXT.replace(
                "**Completion:** test\n", ""
            ),
            "two completion kinds": PLAN_TEXT.replace(
                "**Completion:** test\n",
                "**Completion:** test\n**Completion:** external\n",
            ),
            "unknown completion kind": PLAN_TEXT.replace("**Completion:** test", "**Completion:** demo"),
        }

        for case, malformed in invalid_plans.items():
            with self.subTest(case=case):
                with self.assertRaises(plan_artifact.InvalidPlanFormat):
                    plan_artifact.read_plan_steps(malformed)


class RegisteredPlanConsumerTest(unittest.TestCase):
    def test_human_gate_declaration_is_returned_as_an_immutable_consumer_view(self) -> None:
        gates = plan_artifact.read_plan_human_gates(PLAN_WITH_HUMAN_GATE)

        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_id, "approve-deployment-input")
        self.assertEqual(gates[0].step_id, "step-1")
        self.assertEqual(gates[0].sections, ("配備の入力",))
        self.assertEqual(gates[0].target.kind, "files")
        self.assertEqual(gates[0].target.paths, ("config/deployment.json",))
        self.assertEqual(gates[0].timing, "before_edit")
        self.assertEqual(gates[0].allowed_results, ("approved", "rejected"))

    def test_human_gate_declaration_rejects_unknown_fields(self) -> None:
        malformed = PLAN_WITH_HUMAN_GATE.replace(
            '"allowed_results": ["approved", "rejected"]',
            '"allowed_results": ["approved", "rejected"],\n      "extra": true',
        )

        with self.assertRaisesRegex(
            plan_artifact.InvalidHumanGateDeclaration,
            "unknown or missing fields",
        ):
            plan_artifact.read_plan_human_gates(malformed)

    def test_human_gate_declaration_rejects_invalid_contract_values(self) -> None:
        second_step = PLAN_WITH_HUMAN_GATE.split("### 1.", 1)[1]
        duplicate_gate = (
            PLAN_WITH_HUMAN_GATE
            + "\n### 2. commit前に同じgateを確認する\n"
            + second_step.split("\n", 1)[1].replace("配備の入力", "配備の確認")
        )
        invalid_plans = {
            "legacy clause field": PLAN_WITH_HUMAN_GATE.replace(
                '"sections": ["配備の入力"]',
                '"clauses": ["CY-096"]',
            ),
            "empty sections": PLAN_WITH_HUMAN_GATE.replace(
                '"sections": ["配備の入力"]',
                '"sections": []',
            ),
            "unsupported timing": PLAN_WITH_HUMAN_GATE.replace("before_edit", "during_edit"),
            "unsupported results": PLAN_WITH_HUMAN_GATE.replace(
                '["approved", "rejected"]',
                '["approved"]',
            ),
            "absolute path": PLAN_WITH_HUMAN_GATE.replace(
                "config/deployment.json",
                "/etc/deployment.json",
            ),
            "traversal": PLAN_WITH_HUMAN_GATE.replace(
                "config/deployment.json",
                "config/../deployment.json",
            ),
            "duplicate gate id": duplicate_gate,
        }

        for case, malformed in invalid_plans.items():
            with self.subTest(case=case):
                with self.assertRaises(plan_artifact.InvalidHumanGateDeclaration):
                    plan_artifact.read_plan_human_gates(malformed)

    def test_human_gate_section_must_be_listed_under_the_plan_target_specifications(self) -> None:
        unlisted = PLAN_WITH_HUMAN_GATE.replace('"sections": ["配備の入力"]', '"sections": ["配備の取消"]')

        with self.assertRaisesRegex(plan_artifact.InvalidHumanGateDeclaration, "配備の取消"):
            plan_artifact.read_plan_human_gates(unlisted)

    def test_human_gate_section_is_compared_without_the_backquotes(self) -> None:
        bracketed = PLAN_WITH_HUMAN_GATE.replace('"sections": ["配備の入力"]', '"sections": ["`配備の入力`"]')

        with self.assertRaises(plan_artifact.InvalidHumanGateDeclaration):
            plan_artifact.read_plan_human_gates(bracketed)

    def test_human_gate_event_target_requires_an_immutable_content_identity(self) -> None:
        event_plan = PLAN_WITH_HUMAN_GATE.replace(
            '"kind": "files",\n        "paths": ["config/deployment.json"]',
            '"kind": "event",\n        "content_identity": "sha256:' + "1" * 64 + '"',
        )

        gates = plan_artifact.read_plan_human_gates(event_plan)

        self.assertEqual(gates[0].target.kind, "event")
        self.assertEqual(gates[0].target.paths, ())
        self.assertEqual(gates[0].target.content_identity, "sha256:" + "1" * 64)

    def test_current_registered_plan_is_returned_without_writing(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)
            publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=identity,
                switch_confirmed=False,
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
        with plan_root() as directory:
            root = Path(directory)
            first_identity = plan_artifact.content_identity(PLAN_TEXT)
            publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=first_identity,
                switch_confirmed=False,
            )
            second = PLAN_TEXT.replace("20260822022624", "20260822022625")
            publish_text(
                root,
                plan_id="20260822022625",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022625_second.md",
                text=second,
                approved_identity=plan_artifact.content_identity(second),
                switch_confirmed=True,
            )

            registered = plan_artifact.read_registered_plan(
                root,
                ".agents/artifacts/plans/20260822022624_first.md",
            )

            self.assertEqual(registered.plan_id, "20260822022624")
            self.assertEqual(registered.state, "held")

    def test_missing_registration_is_distinct_from_an_empty_publication_index(self) -> None:
        with plan_root() as directory:
            root = Path(directory)

            with self.assertRaises(plan_artifact.PlanRegistrationMissing):
                plan_artifact.read_registered_plan(root)

            self.assertFalse((root / ".agents").exists())

    def test_registered_plan_identity_mismatch_is_rejected_without_repair(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)
            target = publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=identity,
                switch_confirmed=False,
            )
            target.write_text(PLAN_TEXT + "changed\n", encoding="utf-8")
            index_before = (target.parent / "open-plans.json").read_bytes()

            with self.assertRaises(plan_artifact.RegisteredPlanMismatch):
                plan_artifact.read_registered_plan(root)

            self.assertEqual((target.parent / "open-plans.json").read_bytes(), index_before)
            self.assertEqual(target.read_text(encoding="utf-8"), PLAN_TEXT + "changed\n")

    def test_unsafe_registered_path_is_rejected(self) -> None:
        with plan_root() as directory:
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
    def test_unreadable_plan_is_not_saved_as_a_draft_and_the_part_is_named(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            unreadable = PLAN_TEXT.replace("**Completion:** test\n", "")

            with self.assertRaisesRegex(plan_artifact.InvalidPlanFormat, "Completion"):
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

    def test_draft_plan_id_and_revision_must_match_the_plan_header(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            for case, plan_id, revision in (("id", "20260822022625", 1), ("revision", "20260822022624", 2)):
                with self.subTest(case=case):
                    with self.assertRaisesRegex(plan_artifact.InvalidPlanFormat, "Plan"):
                        plan_artifact.save_draft(
                            root, plan_id=plan_id, revision=revision, slug="small-change", text=PLAN_TEXT
                        )
            self.assertFalse((root / ".agents/tmp/plans").exists())

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
                    switch_confirmed=False,
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
                switch_confirmed=False,
            )

            self.assertEqual(result.read_text(encoding="utf-8"), PLAN_TEXT)
            self.assertFalse(draft.path.exists())
            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["plans"][0]["content_identity"], draft.content_identity)

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
                    switch_confirmed=False,
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
                    switch_confirmed=False,
                )

            self.assertTrue(elsewhere.exists())
            self.assertFalse((root / ".agents/artifacts").exists())

    def test_a_failed_index_write_restores_the_draft(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            draft = plan_artifact.save_draft(
                root, plan_id="20260822022624", revision=1, slug="small-change", text=PLAN_TEXT
            )
            original_write = plan_artifact._atomic_write

            def failing_index_write(path: Path, text: str) -> None:
                if path.name == plan_artifact.INDEX_NAME:
                    raise OSError("disk full")
                original_write(path, text)

            with mock.patch.object(plan_artifact, "_atomic_write", failing_index_write):
                with self.assertRaises(OSError):
                    plan_artifact.publish_plan(
                        root,
                        plan_id="20260822022624",
                        revision=1,
                        relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                        source=draft.path,
                        approved_identity=draft.content_identity,
                        switch_confirmed=False,
                    )

            self.assertEqual(draft.path.read_text(encoding="utf-8"), PLAN_TEXT)
            self.assertFalse((root / ".agents/artifacts/plans/20260822022624_small-change.md").exists())

    def test_confirmed_draft_is_written_and_registered_as_current(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            identity = plan_artifact.content_identity(PLAN_TEXT)

            result = publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_small-change.md",
                text=PLAN_TEXT,
                approved_identity=identity,
                switch_confirmed=False,
            )

            self.assertEqual(result.read_text(encoding="utf-8"), PLAN_TEXT)
            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["current"], "20260822022624")
            self.assertEqual(index["plans"][0]["content_identity"], identity)
            self.assertEqual(index["plans"][0]["state"], "current")

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
                    switch_confirmed=False,
                )

            self.assertFalse((root / ".agents/artifacts").exists())

    def test_existing_current_plan_requires_confirmed_switch(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            first_identity = plan_artifact.content_identity(PLAN_TEXT)
            publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=first_identity,
                switch_confirmed=False,
            )

            with self.assertRaises(plan_artifact.CurrentPlanConflict):
                publish_text(
                    root,
                    plan_id="20260822022625",
                    revision=1,
                    relative_path=".agents/artifacts/plans/20260822022625_second.md",
                    text=PLAN_TEXT.replace("20260822022624", "20260822022625"),
                    approved_identity=plan_artifact.content_identity(
                        PLAN_TEXT.replace("20260822022624", "20260822022625")
                    ),
                    switch_confirmed=False,
                )

            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index["current"], "20260822022624")
            self.assertEqual(len(index["plans"]), 1)

    def test_a_dirty_worktree_is_not_a_reason_to_refuse_a_confirmed_switch(self) -> None:
        self.assertNotIn("worktree_dirty", inspect.signature(plan_artifact.publish_plan).parameters)
        with plan_root() as directory:
            root = Path(directory)
            publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=plan_artifact.content_identity(PLAN_TEXT),
                switch_confirmed=False,
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
                switch_confirmed=True,
            )

            self.assertTrue((root / ".agents/artifacts/plans/20260822022625_second.md").exists())
            self.assertEqual(plan_artifact.read_registered_plan(root, None).plan_id, "20260822022625")

    def test_confirmed_switch_holds_the_previous_plan(self) -> None:
        with plan_root() as directory:
            root = Path(directory)
            publish_text(
                root,
                plan_id="20260822022624",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022624_first.md",
                text=PLAN_TEXT,
                approved_identity=plan_artifact.content_identity(PLAN_TEXT),
                switch_confirmed=False,
            )
            second = PLAN_TEXT.replace("20260822022624", "20260822022625")
            publish_text(
                root,
                plan_id="20260822022625",
                revision=1,
                relative_path=".agents/artifacts/plans/20260822022625_second.md",
                text=second,
                approved_identity=plan_artifact.content_identity(second),
                switch_confirmed=True,
            )

            index = json.loads(
                (root / ".agents/artifacts/plans/open-plans.json").read_text(encoding="utf-8")
            )
            states = {item["id"]: item["state"] for item in index["plans"]}
            self.assertEqual(index["current"], "20260822022625")
            self.assertEqual(states["20260822022624"], "held")
            self.assertEqual(states["20260822022625"], "current")

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
                    switch_confirmed=False,
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
                    switch_confirmed=False,
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
                switch_confirmed=False,
            )
            revised = PLAN_TEXT.replace("revision:** `1`", "revision:** `2`") + "\n手順を修正する。\n"

            result = publish_text(
                root,
                plan_id="20260822022624",
                revision=2,
                relative_path=".agents/artifacts/plans/20260822022624_small-change-r2.md",
                text=revised,
                approved_identity=plan_artifact.content_identity(revised),
                switch_confirmed=False,
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
