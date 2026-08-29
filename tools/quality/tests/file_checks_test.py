import unittest

from tools.quality.file_checks import select_file_checks


class FileChecksTest(unittest.TestCase):
    def test_python_under_the_canonical_roots_runs_pylint_and_mypy_with_the_shared_configuration(
        self,
    ) -> None:
        for path in (
            "tools/quality/agents/stop_hook.py",
            "tools/quality/tests/probe_test.py",
            "tools/workflow-runtime/implement/runtime/evidence.py",
        ):
            with self.subTest(path=path):
                checks = select_file_checks(path)

                self.assertEqual(
                    [check.name for check in checks],
                    ["python-structure", "python-types"],
                )
                pylint, mypy = checks
                self.assertIn("--rcfile=tools/quality/pylint.rc", pylint.argv)
                self.assertEqual(pylint.argv[-1], path)
                self.assertIn("tools/quality/mypy.ini", mypy.argv)
                self.assertEqual(mypy.argv[-1], path)

    def test_generated_skill_scripts_and_other_python_are_not_checked_per_file(
        self,
    ) -> None:
        for path in (
            "skills/ba0918-implement/scripts/runtime/evidence.py",
            "evals/run.py",
            "tools/quality/pylint.rc",
        ):
            with self.subTest(path=path):
                self.assertEqual(select_file_checks(path), ())

    def test_spec_markdown_runs_textlint_on_that_file(self) -> None:
        checks = select_file_checks("docs/spec/quality-tooling.md")

        self.assertEqual([check.name for check in checks], ["spec-textlint"])
        self.assertEqual(
            checks[0].argv, ("node_modules/.bin/textlint", "docs/spec/quality-tooling.md")
        )

    def test_markdown_outside_the_spec_directory_is_not_checked(self) -> None:
        for path in ("README.md", "docs/plans/next.md", "docs/spec/notes.txt"):
            with self.subTest(path=path):
                self.assertEqual(select_file_checks(path), ())


if __name__ == "__main__":
    unittest.main()
