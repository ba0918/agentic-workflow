import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "tools/workflow-runtime/plan/plan_artifact.py"
SPEC = importlib.util.spec_from_file_location("plan_artifact", MODULE_PATH)
assert SPEC is not None
plan_artifact = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(plan_artifact)

PLAN = """# Example

**Verification coverage:**

- `docs/spec/example.md` / `Contract` -> `1:test`
- `docs/spec/example.md` / `Failure handling` -> `2:check`

## Scope

```text
src/
  app.py
tests/
  app_test.py
```

## Step 1: Implement behavior

Run the behavior test.

## Step 2: Validate generated output

**Checks:**

- `first-check`
- `second-check`
"""

class PlanArtifactTest(unittest.TestCase):
    def make_repository(self) -> Path:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "docs/spec").mkdir(parents=True)
        (root / "docs/plans").mkdir(parents=True)
        (root / "docs/spec/example.md").write_text(
            "# Contract\n\nBody\n\n## Failure handling\n\nFailure body\n", encoding="utf-8",
        )
        (root / "docs/plans/example.md").write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md", "docs/plans/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
        return root

    def test_reads_coverage_scope_and_step_contracts(self) -> None:
        header = plan_artifact.read_plan_header(PLAN)
        self.assertEqual(header.specifications[0].path, "docs/spec/example.md")
        self.assertEqual(header.specifications[0].sections, ("Contract", "Failure handling"))
        self.assertEqual(
            [(item.path, item.section, item.step_id, item.completion) for item in header.coverage],
            [
                ("docs/spec/example.md", "Contract", "1", "test"),
                ("docs/spec/example.md", "Failure handling", "2", "check"),
            ],
        )
        self.assertEqual(
            [(step.id, step.completion, step.checks) for step in header.steps],
            [("1", "test", ()), ("2", "check", ("first-check", "second-check"))],
        )
        self.assertEqual(plan_artifact.read_plan_scope(PLAN), ("src/app.py", "tests/app_test.py"))

    def test_rejects_legacy_target_specifications(self) -> None:
        legacy = PLAN.replace(
            "**Verification coverage:**\n\n"
            "- `docs/spec/example.md` / `Contract` -> `1:test`\n"
            "- `docs/spec/example.md` / `Failure handling` -> `2:check`",
            "**Target specifications:**\n\n"
            "- `docs/spec/example.md`\n"
            "  - sections: `Contract`, `Failure handling`",
        )
        with self.assertRaises(plan_artifact.InvalidPlanFormat):
            plan_artifact.read_plan_header(legacy)

    def test_rejects_invalid_coverage_rows(self) -> None:
        invalid_values = (
            "- `docs/spec/example.md` / `Contract` => `1:test`",
            "- `../example.md` / `Contract` -> `1:test`",
            "- `docs/spec/example.md` / `Contract` -> `1:unknown`",
            "- `docs/spec/example.md` / `Contract` -> `0:test`",
        )
        original = "- `docs/spec/example.md` / `Contract` -> `1:test`"
        for invalid in invalid_values:
            with self.subTest(invalid=invalid), self.assertRaises(plan_artifact.InvalidPlanFormat):
                plan_artifact.read_plan_header(PLAN.replace(original, invalid))

    def test_verification_coverage_must_be_one_contiguous_block(self) -> None:
        duplicate_label = PLAN.replace(
            "## Scope",
            "**Verification coverage:**\n\n"
            "- `docs/spec/example.md` / `Failure handling` -> `2:check`\n\n"
            "## Scope",
        )
        split_rows = PLAN.replace(
            "- `docs/spec/example.md` / `Contract` -> `1:test`\n"
            "- `docs/spec/example.md` / `Failure handling` -> `2:check`",
            "- `docs/spec/example.md` / `Contract` -> `1:test`\n\n"
            "- `docs/spec/example.md` / `Failure handling` -> `2:check`",
        )
        for invalid in (duplicate_label, split_rows):
            with self.subTest(), self.assertRaises(plan_artifact.InvalidPlanFormat):
                plan_artifact.read_plan_header(invalid)

    def test_step_headings_must_be_contiguous_and_unique(self) -> None:
        for invalid in (
            PLAN.replace("## Step 2:", "## Step 3:"),
            PLAN.replace("## Step 2:", "## Step 1:"),
        ):
            with self.subTest(), self.assertRaises(plan_artifact.InvalidPlanFormat):
                plan_artifact.read_plan_header(invalid)

    def test_coverage_and_steps_must_cover_each_other(self) -> None:
        unreferenced_step = PLAN.replace(
            "- `docs/spec/example.md` / `Failure handling` -> `2:check`\n", "",
        )
        missing_step = PLAN.replace(" -> `2:check`", " -> `3:check`")
        for invalid in (unreferenced_step, missing_step):
            with self.subTest(), self.assertRaises(plan_artifact.InvalidPlanFormat):
                plan_artifact.read_plan_header(invalid)

    def test_same_step_must_have_one_completion_kind(self) -> None:
        invalid = PLAN.replace(" -> `2:check`", " -> `1:check`")
        with self.assertRaises(plan_artifact.InvalidPlanFormat):
            plan_artifact.read_plan_header(invalid)

    def test_checks_are_required_only_for_check_steps(self) -> None:
        missing = PLAN.replace("**Checks:**\n\n- `first-check`\n- `second-check`\n", "")
        empty = PLAN.replace("- `first-check`\n- `second-check`", "")
        misplaced = PLAN.replace(
            "Run the behavior test.\n", "Run the behavior test.\n\n**Checks:**\n\n- `test-check`\n",
        )
        for invalid in (missing, empty, misplaced):
            with self.subTest(), self.assertRaises(plan_artifact.InvalidPlanFormat):
                plan_artifact.read_plan_header(invalid)

    def test_checks_must_belong_to_the_step_section(self) -> None:
        invalid = PLAN.replace(
            "**Checks:**\n\n- `first-check`\n- `second-check`\n",
            "## Completion\n\n**Checks:**\n\n- `unrelated-check`\n",
        )
        with self.assertRaises(plan_artifact.InvalidPlanFormat):
            plan_artifact.read_plan_header(invalid)

    def test_plan_path_is_directly_under_docs_plans(self) -> None:
        root = self.make_repository()
        loaded = plan_artifact.read_plan(root, "docs/plans/example.md")
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(loaded.approval_commit, head)
        with self.assertRaises(plan_artifact.UnsafePlanPath):
            plan_artifact.read_plan(root, "docs/plans/../spec/example.md")

    def test_symlinked_plan_is_rejected(self) -> None:
        root = self.make_repository()
        (root / "docs/plans/link.md").symlink_to(root / "docs/plans/example.md")
        with self.assertRaises(plan_artifact.UnsafePlanPath):
            plan_artifact.read_plan(root, "docs/plans/link.md")

    def test_uncommitted_or_post_approval_plan_bytes_are_rejected(self) -> None:
        root = self.make_repository()
        (root / "docs/plans/example.md").write_bytes(PLAN.encode("utf-8") + b"\nUnapproved edit\n")
        with self.assertRaises(plan_artifact.PlanArtifactError):
            plan_artifact.read_plan(root, "docs/plans/example.md")

    def test_target_sections_must_exist_in_committed_specifications(self) -> None:
        root = self.make_repository()
        plan_artifact.validate_plan(root, PLAN, approval_commit="HEAD")
        with self.assertRaises(plan_artifact.TargetSpecificationMismatch):
            plan_artifact.validate_plan(
                root, PLAN.replace(" / `Contract` ->", " / `Missing` ->"), approval_commit="HEAD",
            )

    def test_target_sections_must_be_unique_in_committed_specifications(self) -> None:
        root = self.make_repository()
        path = root / "docs/spec/example.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n## Contract\n\nDuplicate\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "duplicate heading"], check=True)
        with self.assertRaises(plan_artifact.TargetSpecificationMismatch):
            plan_artifact.validate_plan(root, PLAN, approval_commit="HEAD")

    def test_uncommitted_target_specification_is_rejected(self) -> None:
        root = self.make_repository()
        (root / "docs/spec/example.md").write_text("# Contract\n\nChanged\n", encoding="utf-8")
        with self.assertRaises(plan_artifact.TargetSpecificationMismatch):
            plan_artifact.validate_plan(root, PLAN, approval_commit="HEAD")

    def test_approved_plan_can_expose_committed_specification_wording_drift(self) -> None:
        root = self.make_repository()
        (root / "docs/spec/example.md").write_text("# Contract\n\nBody clarified\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "clarify spec"], check=True)
        loaded = plan_artifact.read_plan(root, "docs/plans/example.md")
        self.assertEqual(len(loaded.specification_changes), 1)
        change = loaded.specification_changes[0]
        self.assertIn("Body\n", change.approved_text)
        self.assertIn("Body clarified", change.current_text)
        self.assertIn("+Body clarified", change.diff)

    def test_old_identity_and_publication_apis_are_absent(self) -> None:
        for name in ("content_identity", "save_draft", "publish_plan"):
            self.assertFalse(hasattr(plan_artifact, name))
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("Plan ID", source)
        self.assertNotIn("Plan revision", source)

if __name__ == "__main__":
    unittest.main()
