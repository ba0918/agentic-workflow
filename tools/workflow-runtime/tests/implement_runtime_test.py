import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_HOME = ROOT / "tools/workflow-runtime/implement"
sys.path.insert(0, str(RUNTIME_HOME))
planning = importlib.import_module("runtime.planning")
staging = importlib.import_module("runtime.staging")

PLAN = """# Plan

**Target specifications:**

- `docs/spec/example.md`
  - sections: `Contract`

## Scope

```text
src/
  app.py
```
"""

class ImplementPlanBindingTest(unittest.TestCase):
    def fixture(self) -> Path:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "docs/spec").mkdir(parents=True)
        (root / "docs/plans").mkdir(parents=True)
        (root / "docs/spec/example.md").write_text("# Contract\n", encoding="utf-8")
        (root / "docs/plans/example.md").write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "docs/spec/example.md", "docs/plans/example.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "approved"], check=True)
        return root

    def test_resolves_a_committed_plan_without_manual_identity_fields(self) -> None:
        root = self.fixture()
        result = planning.resolve_plan(root, plan_path="docs/plans/example.md")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value.plan_key, "example")
        self.assertEqual(result.value.specifications[0].sections, ("Contract",))
        self.assertEqual(result.value.expected_paths, ("src/app.py",))

    def test_unique_plan_is_selected_automatically(self) -> None:
        root = self.fixture()
        result = planning.resolve_plan(root)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value.path, "docs/plans/example.md")

    def test_multiple_plans_require_an_explicit_path(self) -> None:
        root = self.fixture()
        (root / "docs/plans/other.md").write_text(PLAN, encoding="utf-8")
        result = planning.resolve_plan(root)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "plan_candidate_ambiguous")

    def test_public_runtime_imports_without_legacy_plan_fields(self) -> None:
        module = importlib.import_module("implement_runtime")
        self.assertTrue(callable(module.resolve_plan))
        for path in (
            RUNTIME_HOME / "runtime/types.py",
            RUNTIME_HOME / "runtime/planning.py",
            RUNTIME_HOME / "runtime/repository.py",
            RUNTIME_HOME / "runtime/context.py",
            RUNTIME_HOME / "runtime/resume.py",
            RUNTIME_HOME / "runtime/cli.py",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("plan_identity", source)
            self.assertNotIn("plan_revision", source)
            self.assertNotIn("content_identity", source)

    def test_safe_unplanned_paths_are_reported_instead_of_rejected(self) -> None:
        result = staging.assess_paths(
            ["src/app.py", "tests/app_test.py"],
            expected_paths=["src/app.py"],
            reasons={"tests/app_test.py": "behavior needs coverage"},
        )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value["unplanned"], [{"path": "tests/app_test.py", "reason": "behavior needs coverage"}])

    def test_unplanned_path_requires_a_reason(self) -> None:
        result = staging.assess_paths(["tests/app_test.py"], expected_paths=[])
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "unplanned_reason_missing")

    def test_safety_checks_apply_inside_and_outside_expected_paths(self) -> None:
        for expected in ([".env.production"], []):
            result = staging.assess_paths([".env.production"], expected_paths=expected, reasons={".env.production": "needed"})
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code, "dangerous_path")
        for path in ("run.log", "scratch.tmp", "node_modules/pkg/index.js", ".agents/evidence/x.json"):
            result = staging.assess_paths([path], expected_paths=[path])
            self.assertFalse(result.ok)

    def test_semantically_dangerous_paths_are_returned_for_human_judgment(self) -> None:
        result = staging.assess_paths(
            ["config/release.toml"],
            expected_paths=["config/release.toml"],
            dangerous_paths={"config/release.toml": "production deployment target"},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "human_judgment_required")

if __name__ == "__main__":
    unittest.main()
