import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "tools/workflow-runtime/plan/plan_artifact.py"
SPEC = importlib.util.spec_from_file_location("plan_artifact", MODULE_PATH)
plan_artifact = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(plan_artifact)

PLAN = """# Example

**Target specifications:**

- `docs/spec/example.md`
  - sections: `Contract`

## Scope

```text
src/
  app.py
tests/
  app_test.py
```
"""

class PlanArtifactTest(unittest.TestCase):
    def make_repository(self) -> Path:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "docs/spec").mkdir(parents=True)
        (root / "docs/plans").mkdir(parents=True)
        (root / "docs/spec/example.md").write_text("# Contract\n\nBody\n", encoding="utf-8")
        (root / "docs/plans/example.md").write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md", "docs/plans/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
        return root

    def test_reads_only_target_specifications_and_scope(self) -> None:
        header = plan_artifact.read_plan_header(PLAN)
        self.assertEqual(header.specifications[0].path, "docs/spec/example.md")
        self.assertEqual(header.specifications[0].sections, ("Contract",))
        self.assertEqual(plan_artifact.read_plan_scope(PLAN), ("src/app.py", "tests/app_test.py"))

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

    def test_target_sections_must_exist_in_committed_specifications(self) -> None:
        root = self.make_repository()
        plan_artifact.validate_plan(root, PLAN, approval_commit="HEAD")
        with self.assertRaises(plan_artifact.TargetSpecificationMismatch):
            plan_artifact.validate_plan(root, PLAN.replace("`Contract`", "`Missing`"), approval_commit="HEAD")

    def test_uncommitted_target_specification_is_rejected(self) -> None:
        root = self.make_repository()
        (root / "docs/spec/example.md").write_text("# Contract\n\nChanged\n", encoding="utf-8")
        with self.assertRaises(plan_artifact.TargetSpecificationMismatch):
            plan_artifact.validate_plan(root, PLAN, approval_commit="HEAD")

    def test_old_identity_and_publication_apis_are_absent(self) -> None:
        for name in ("content_identity", "save_draft", "publish_plan"):
            self.assertFalse(hasattr(plan_artifact, name))
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("Plan ID", source)
        self.assertNotIn("Plan revision", source)

if __name__ == "__main__":
    unittest.main()
