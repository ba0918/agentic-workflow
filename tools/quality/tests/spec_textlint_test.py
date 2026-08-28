import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.quality.tests.git_repository import initialize_repository


SPEC_TEXTLINT = Path(__file__).parents[1] / "spec_textlint.py"


class SpecTextlintTest(unittest.TestCase):
    def initialize_repository(self, root: Path) -> None:
        initialize_repository(root)
        spec = root / "docs" / "spec"
        spec.mkdir(parents=True)
        (spec / "tracked.md").write_text("baseline\n", encoding="utf-8")
        (spec / "other.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs/spec"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)

    def install_fake_textlint(self, root: Path) -> Path:
        executable = root / "node_modules" / ".bin" / "textlint"
        executable.parent.mkdir(parents=True)
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "from pathlib import Path\n"
            "import sys\n"
            "capture = os.environ.get('TEXTLINT_CAPTURE')\n"
            "if capture:\n"
            "    Path(capture).write_text('\\0'.join(sys.argv[1:]))\n"
            "content_capture = os.environ.get('TEXTLINT_CONTENT_CAPTURE')\n"
            "if content_capture:\n"
            "    Path(content_capture).write_text(sys.stdin.read())\n"
            "print(os.environ.get('TEXTLINT_STDOUT', ''))\n"
            "print(os.environ.get('TEXTLINT_STDERR', ''), file=sys.stderr)\n"
            "raise SystemExit(int(os.environ.get('TEXTLINT_EXIT', '0')))\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def track_spec_symlink(self, root: Path) -> Path:
        link = root / "docs" / "spec" / "typed.md"
        link.symlink_to("tracked.md")
        subprocess.run(["git", "add", str(link)], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "track symlink"],
            cwd=root,
            check=True,
        )
        return link

    def invoke(
        self,
        root: Path,
        scope: str,
        capture: Path,
        **environment: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SPEC_TEXTLINT), "--root", str(root)],
            cwd=root,
            env={
                **os.environ,
                "AGENTIC_QUALITY_SCOPE": scope,
                "TEXTLINT_CAPTURE": str(capture),
                **environment,
            },
            text=True,
            capture_output=True,
            check=False,
        )

    def test_worktree_scope_lints_changed_and_added_spec_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            (root / "docs" / "spec" / "tracked.md").write_text("changed\n")
            nested = root / "docs" / "spec" / "nested"
            nested.mkdir()
            (nested / "added.md").write_text("new\n")
            (root / "outside.md").write_text("ignored\n")

            completed = self.invoke(root, "worktree", capture)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                set(capture.read_text(encoding="utf-8").split("\0")),
                {"docs/spec/tracked.md", "docs/spec/nested/added.md"},
            )

    def test_staged_scope_lints_only_staged_spec_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            tracked = root / "docs" / "spec" / "tracked.md"
            other = root / "docs" / "spec" / "other.md"
            tracked.write_text("staged\n")
            subprocess.run(["git", "add", str(tracked)], cwd=root, check=True)
            other.write_text("unstaged\n")

            completed = self.invoke(root, "staged", capture)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                capture.read_text(encoding="utf-8"),
                "--stdin\0--stdin-filename\0docs/spec/tracked.md",
            )

    def test_staged_scope_lints_content_from_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            content_capture = root / "content-capture"
            tracked = root / "docs" / "spec" / "tracked.md"
            tracked.write_text("staged content\n", encoding="utf-8")
            subprocess.run(["git", "add", str(tracked)], cwd=root, check=True)
            tracked.write_text("unstaged content\n", encoding="utf-8")

            completed = self.invoke(
                root,
                "staged",
                capture,
                TEXTLINT_CONTENT_CAPTURE=str(content_capture),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                content_capture.read_text(encoding="utf-8"),
                "staged content\n",
            )
            self.assertEqual(
                capture.read_text(encoding="utf-8"),
                "--stdin\0--stdin-filename\0docs/spec/tracked.md",
            )

    def test_staged_scope_lints_added_file_missing_from_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            content_capture = root / "content-capture"
            added = root / "docs" / "spec" / "added.md"
            added.write_text("staged addition\n", encoding="utf-8")
            subprocess.run(["git", "add", str(added)], cwd=root, check=True)
            added.unlink()

            completed = self.invoke(
                root,
                "staged",
                capture,
                TEXTLINT_CONTENT_CAPTURE=str(content_capture),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                content_capture.read_text(encoding="utf-8"),
                "staged addition\n",
            )
            self.assertEqual(
                capture.read_text(encoding="utf-8"),
                "--stdin\0--stdin-filename\0docs/spec/added.md",
            )

    def test_worktree_scope_lints_markdown_changed_from_symlink_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            changed = self.track_spec_symlink(root)
            changed.unlink()
            changed.write_text("regular file\n", encoding="utf-8")

            completed = self.invoke(root, "worktree", capture)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                capture.read_text(encoding="utf-8"),
                "docs/spec/typed.md",
            )

    def test_staged_scope_lints_markdown_changed_from_symlink_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            content_capture = root / "content-capture"
            changed = self.track_spec_symlink(root)
            changed.unlink()
            changed.write_text("staged regular file\n", encoding="utf-8")
            subprocess.run(["git", "add", str(changed)], cwd=root, check=True)

            completed = self.invoke(
                root,
                "staged",
                capture,
                TEXTLINT_CONTENT_CAPTURE=str(content_capture),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                content_capture.read_text(encoding="utf-8"),
                "staged regular file\n",
            )
            self.assertEqual(
                capture.read_text(encoding="utf-8"),
                "--stdin\0--stdin-filename\0docs/spec/typed.md",
            )

    def test_no_changed_spec_does_not_start_textlint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            (root / "outside.md").write_text("ignored\n")

            completed = self.invoke(root, "worktree", capture)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(capture.exists())

    def test_textlint_failure_preserves_exit_code_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            (root / "docs" / "spec" / "tracked.md").write_text("changed\n")

            completed = self.invoke(
                root,
                "worktree",
                capture,
                TEXTLINT_EXIT="7",
                TEXTLINT_STDOUT="line 1: violation",
                TEXTLINT_STDERR="textlint failed",
            )

            self.assertEqual(completed.returncode, 7)
            self.assertIn("line 1: violation", completed.stdout)
            self.assertIn("textlint failed", completed.stderr)

    def test_worktree_scope_rejects_spec_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            link = root / "docs" / "spec" / "linked.md"
            link.symlink_to("tracked.md")

            completed = self.invoke(root, "worktree", capture)

            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "docs/spec/linked.md is not a regular file",
                completed.stderr,
            )
            self.assertFalse(capture.exists())

    def test_staged_scope_rejects_spec_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            link = root / "docs" / "spec" / "linked.md"
            link.symlink_to("tracked.md")
            subprocess.run(["git", "add", str(link)], cwd=root, check=True)

            completed = self.invoke(root, "staged", capture)

            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "docs/spec/linked.md is not a regular file",
                completed.stderr,
            )
            self.assertFalse(capture.exists())

    def test_all_scope_lints_every_tracked_spec_in_a_clean_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"

            completed = self.invoke(root, "all", capture)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                set(capture.read_text(encoding="utf-8").split("\0")),
                {"docs/spec/other.md", "docs/spec/tracked.md"},
            )

    def test_all_scope_rejects_tracked_spec_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            self.install_fake_textlint(root)
            capture = root / "capture"
            self.track_spec_symlink(root)

            completed = self.invoke(root, "all", capture)

            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "docs/spec/typed.md is not a regular file",
                completed.stderr,
            )
            self.assertFalse(capture.exists())


if __name__ == "__main__":
    unittest.main()
