import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.quality.agents import post_tool_use
from tools.quality.agents.post_tool_use import edited_path, repository_relative_path
from tools.quality.tests.git_repository import initialize_repository


PROJECT_ROOT = Path(__file__).resolve().parents[3]
POST_TOOL_USE = PROJECT_ROOT / "tools" / "quality" / "agents" / "post_tool_use.py"


def prepare_spec_repository(root: Path) -> None:
    initialize_repository(root)
    os.symlink(PROJECT_ROOT / "node_modules", root / "node_modules")
    shutil.copy2(PROJECT_ROOT / ".textlintrc.json", root / ".textlintrc.json")
    (root / "docs" / "spec").mkdir(parents=True)


def invoke(root: Path, hook_input: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(POST_TOOL_USE), "--root", str(root)],
        cwd=root / "docs",
        input=json.dumps(hook_input),
        text=True,
        capture_output=True,
        check=False,
    )


def write_hook_input(path: Path) -> dict[str, object]:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": ""},
        "tool_response": {"filePath": str(path), "success": True},
    }


class HookInputTest(unittest.TestCase):
    def test_the_default_root_is_the_repository_containing_the_hook(self) -> None:
        self.assertEqual(post_tool_use.default_project_root(), PROJECT_ROOT)

    def test_write_and_edit_inputs_name_the_edited_file(self) -> None:
        for tool in ("Write", "Edit"):
            with self.subTest(tool=tool):
                hook_input = {"tool_name": tool, "tool_input": {"file_path": "/repo/a.py"}}

                self.assertEqual(edited_path(hook_input), "/repo/a.py")

    def test_inputs_without_a_file_path_yield_nothing(self) -> None:
        hook_inputs: tuple[object, ...] = (
            {"tool_name": "Bash", "tool_input": {"command": "ls"}},
            {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/repo/n.ipynb"}},
            {"tool_name": "Write", "tool_input": {"file_path": 3}},
            {"tool_name": "Write"},
            [],
        )
        for hook_input in hook_inputs:
            with self.subTest(hook_input=hook_input):
                self.assertIsNone(edited_path(hook_input))

    def test_paths_inside_the_repository_become_root_relative_posix(self) -> None:
        root = Path("/repo")

        self.assertEqual(
            repository_relative_path("/repo/docs/spec/a.md", root), "docs/spec/a.md"
        )
        self.assertEqual(repository_relative_path("/repo/../repo/x.py", root), "x.py")

    def test_paths_outside_the_repository_yield_nothing(self) -> None:
        root = Path("/repo")

        self.assertIsNone(repository_relative_path("/tmp/scratch.md", root))
        self.assertIsNone(repository_relative_path("/repository/a.md", root))


class PostToolUseHookTest(unittest.TestCase):
    def test_a_clean_spec_file_produces_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_spec_repository(root)
            target = root / "docs" / "spec" / "clean.md"
            target.write_text("# 題\n\n本文です。\n", encoding="utf-8")

            completed = invoke(root, write_hook_input(target))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "")

    def test_a_violating_spec_file_blocks_with_the_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_spec_repository(root)
            target = root / "docs" / "spec" / "mixed.md"
            target.write_text("# 題\n\n本文です。\n\n本文である。\n", encoding="utf-8")

            completed = invoke(root, write_hook_input(target))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        response = json.loads(completed.stdout)
        self.assertEqual(response["decision"], "block")
        self.assertIn("docs/spec/mixed.md", response["reason"])
        self.assertIn("である", response["reason"])

    def test_files_outside_the_checked_set_produce_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_spec_repository(root)
            outside = Path(directory).parent / "scratch.md"
            readme = root / "README.md"
            readme.write_text("本文である。\n", encoding="utf-8")

            for target in (outside, readme):
                with self.subTest(target=target):
                    completed = invoke(root, write_hook_input(target))

                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stdout, "")

    def test_unreadable_hook_input_is_reported_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_spec_repository(root)
            completed = subprocess.run(
                [sys.executable, str(POST_TOOL_USE), "--root", str(root)],
                cwd=root,
                input="not json",
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("hook input", completed.stderr)


if __name__ == "__main__":
    unittest.main()
