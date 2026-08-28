import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def isolated_skill(name: str, temporary: Path) -> Path:
    destination = temporary / name
    shutil.copytree(ROOT / "skills" / name, destination)
    return destination


def isolated_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_python(skill: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=skill,
        env=isolated_environment(),
        text=True,
        capture_output=True,
        check=False,
    )


class VendorEntrypointsTest(unittest.TestCase):
    def test_runtime_files_are_vendored_without_directory_markers(self) -> None:
        manifest = (ROOT / "vendor-manifest.yaml").read_text(encoding="utf-8")
        markers = sorted((ROOT / "skills").glob("*/scripts/**/.vendored"))
        review_contract = manifest.split("  review-runtime:", maxsplit=1)[1]

        self.assertNotIn("tools/workflow-runtime/implement/runtime/:", manifest)
        self.assertNotIn("tools/workflow-runtime/review/review_support/:", manifest)
        self.assertIn(
            "tools/workflow-runtime/shared/git_status.py: scripts/git_status.py",
            review_contract,
        )
        self.assertIn(
            "tools/workflow-runtime/review/review_support/finding_validation.py: "
            "scripts/review_support/finding_validation.py",
            review_contract,
        )
        self.assertEqual(markers, [])

    def test_entry_scripts_reach_help_from_an_isolated_skill_copy(self) -> None:
        entries = (
            ("ba0918-brainstorm", "scripts/draft.py"),
            ("ba0918-implement", "scripts/implement_runtime.py"),
            ("ba0918-review", "scripts/review_runtime.py"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for skill_name, script in entries:
                with self.subTest(skill=skill_name):
                    skill = isolated_skill(skill_name, temporary)
                    result = run_python(skill, script, "--help")
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_cli_modules_import_from_an_isolated_skill_copy(self) -> None:
        modules = (
            ("ba0918-brainstorm", "scripts/state.py"),
            ("ba0918-plan", "scripts/plan_artifact.py"),
        )
        loader = (
            "import importlib.util, pathlib, sys; "
            "path=pathlib.Path(sys.argv[1]); "
            "spec=importlib.util.spec_from_file_location('isolated_module', path); "
            "assert spec is not None and spec.loader is not None; "
            "module=importlib.util.module_from_spec(spec); "
            "sys.modules[spec.name]=module; spec.loader.exec_module(module)"
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for skill_name, script in modules:
                with self.subTest(skill=skill_name):
                    skill = isolated_skill(skill_name, temporary)
                    result = run_python(skill, "-c", loader, script)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_helper_cli_help_from_an_isolated_skill_copy(self) -> None:
        entries = (
            ("ba0918-brainstorm", "scripts/state.py", "validate"),
            ("ba0918-plan", "scripts/plan_artifact.py", "validate-candidate"),
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for skill_name, script, command in entries:
                with self.subTest(skill=skill_name):
                    skill = isolated_skill(skill_name, temporary)
                    result = run_python(skill, script, "--help")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
