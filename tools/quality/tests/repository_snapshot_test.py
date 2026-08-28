from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


from tools.quality.repository_snapshot import SnapshotError, create_repository_snapshot
from tools.quality.tests.git_repository import initialize_python_repository


class RepositorySnapshotTest(unittest.TestCase):
    def test_staged_snapshot_contains_index_bytes_not_worktree_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = initialize_python_repository(root)
            source.write_text("value = 'staged'\n", encoding="utf-8")
            subprocess.run(["git", "add", "tools/quality/probe.py"], cwd=root, check=True)
            source.write_text("value = 'worktree'\n", encoding="utf-8")

            with create_repository_snapshot(root, "staged") as snapshot:
                content = (snapshot.root / "tools" / "quality" / "probe.py").read_text(
                    encoding="utf-8"
                )

        self.assertEqual(content, "value = 'staged'\n")

    def test_all_snapshot_contains_tracked_worktree_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = initialize_python_repository(root)
            source.write_text("value = 'worktree'\n", encoding="utf-8")

            with create_repository_snapshot(root, "all") as snapshot:
                content = (snapshot.root / "tools" / "quality" / "probe.py").read_text(
                    encoding="utf-8"
                )

        self.assertEqual(content, "value = 'worktree'\n")

    def test_snapshot_creation_preserves_index_and_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = initialize_python_repository(root)
            source.write_text("value = 'staged'\n", encoding="utf-8")
            subprocess.run(["git", "add", "tools/quality/probe.py"], cwd=root, check=True)
            source.write_text("value = 'worktree'\n", encoding="utf-8")
            status_before = subprocess.run(
                ["git", "status", "--porcelain=v1", "-z"],
                cwd=root,
                capture_output=True,
                check=True,
            ).stdout
            index_before = subprocess.run(
                ["git", "show", ":tools/quality/probe.py"],
                cwd=root,
                capture_output=True,
                check=True,
            ).stdout

            with create_repository_snapshot(root, "staged"):
                pass

            status_after = subprocess.run(
                ["git", "status", "--porcelain=v1", "-z"],
                cwd=root,
                capture_output=True,
                check=True,
            ).stdout
            index_after = subprocess.run(
                ["git", "show", ":tools/quality/probe.py"],
                cwd=root,
                capture_output=True,
                check=True,
            ).stdout

        self.assertEqual(status_after, status_before)
        self.assertEqual(index_after, index_before)

    def test_each_scope_rejects_non_regular_python_sources(self) -> None:
        for scope in ("worktree", "staged", "all"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = initialize_python_repository(root)
                source.unlink()
                source.symlink_to("missing.py")
                if scope in {"staged", "all"}:
                    subprocess.run(
                        ["git", "add", "tools/quality/probe.py"],
                        cwd=root,
                        check=True,
                    )
                if scope == "all":
                    subprocess.run(
                        ["git", "commit", "-qm", "track symlink"],
                        cwd=root,
                        check=True,
                    )

                with self.assertRaisesRegex(
                    SnapshotError,
                    "tools/quality/probe.py is not a regular file",
                ):
                    with create_repository_snapshot(root, scope):
                        pass

    def test_worktree_scope_rejects_non_regular_python_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = initialize_python_repository(root)
            quality_root = source.parent
            shutil.rmtree(quality_root)
            replacement = root / "replacement"
            replacement.mkdir()
            (replacement / "probe.py").write_text("value = 1\n", encoding="utf-8")
            quality_root.symlink_to(replacement, target_is_directory=True)

            with self.assertRaisesRegex(
                SnapshotError,
                "tools/quality is not a regular directory",
            ):
                with create_repository_snapshot(root, "worktree"):
                    pass

    def test_worktree_scope_rejects_non_regular_python_package_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = initialize_python_repository(root)
            replacement = root / "replacement"
            replacement.mkdir()
            (replacement / "module.py").write_text("value = 1\n", encoding="utf-8")
            package = source.parent / "nested"
            package.symlink_to(replacement, target_is_directory=True)

            with self.assertRaisesRegex(
                SnapshotError,
                "tools/quality/nested is not a regular directory",
            ):
                with create_repository_snapshot(root, "worktree"):
                    pass


if __name__ == "__main__":
    unittest.main()
