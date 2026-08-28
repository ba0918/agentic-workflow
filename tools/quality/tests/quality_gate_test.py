import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


QUALITY_GATE = Path(__file__).parents[1] / "quality_gate.py"


def write_config(config: Path, checks: list[dict[str, object]]) -> None:
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"checks": checks}), encoding="utf-8")


def invoke_gate(
    config: Path,
    working_directory: Path,
    project_root: Path | None = None,
    scope: str | None = None,
) -> subprocess.CompletedProcess[str]:
    arguments = [sys.executable, str(QUALITY_GATE), "--config", str(config)]
    if project_root is not None:
        arguments.extend(["--root", str(project_root)])
    if scope is not None:
        arguments.extend(["--scope", scope])
    return subprocess.run(
        arguments,
        cwd=working_directory,
        input=json.dumps({"hook_event_name": "Stop"}),
        text=True,
        capture_output=True,
        check=False,
    )


class QualityGateTest(unittest.TestCase):
    def run_gate(self, checks: list[dict[str, object]]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "checks.json"
            write_config(config, checks)
            return invoke_gate(config, root)

    def test_all_successful_checks_return_success(self) -> None:
        completed = self.run_gate(
            [
                {
                    "name": "passing-check",
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                }
            ]
        )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")

    def test_failed_check_returns_failure_with_its_diagnostic(self) -> None:
        completed = self.run_gate(
            [
                {
                    "name": "broken-check",
                    "argv": [
                        sys.executable,
                        "-c",
                        "import sys; print('repair this'); raise SystemExit(7)",
                    ],
                }
            ]
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("broken-check", completed.stderr)
        self.assertIn("repair this", completed.stderr)

    def test_unavailable_check_does_not_hide_later_check_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "later-check-ran"
            config = root / "checks.json"
            write_config(
                config,
                [
                    {
                        "name": "missing-check",
                        "argv": ["command-that-does-not-exist-quality-gate"],
                    },
                    {
                        "name": "later-check",
                        "argv": [
                            sys.executable,
                            "-c",
                            f"from pathlib import Path; Path({str(marker)!r}).touch()",
                        ],
                    },
                ],
            )
            completed = invoke_gate(config, root)

            self.assertTrue(marker.exists())

        self.assertEqual(completed.returncode, 1)
        self.assertIn("missing-check", completed.stderr)

    def test_empty_check_list_blocks_instead_of_silently_disabling_the_gate(self) -> None:
        completed = self.run_gate([])

        self.assertEqual(completed.returncode, 1)
        self.assertIn("no checks configured", completed.stderr)

    def test_invalid_check_definition_blocks_with_a_configuration_diagnostic(self) -> None:
        completed = self.run_gate([{"name": "missing-command"}])

        self.assertEqual(completed.returncode, 1)
        self.assertIn("configuration", completed.stderr)
        self.assertIn("argv", completed.stderr)

    def test_checks_run_from_the_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_directory = root / ".codex" / "quality"
            config = config_directory / "checks.json"
            expected_root = repr(str(root))
            write_config(
                config,
                [
                    {
                        "name": "working-directory",
                        "argv": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; "
                            f"raise SystemExit(0 if Path.cwd() == Path({expected_root}) else 9)",
                        ],
                    }
                ],
            )
            completed = invoke_gate(config, root / ".codex", project_root=root)

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")

    def test_selected_scope_is_forwarded_to_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "scope"
            config = root / "checks.json"
            write_config(
                config,
                [
                    {
                        "name": "scope-reader",
                        "argv": [
                            sys.executable,
                            "-c",
                            "import os, pathlib; "
                            f"pathlib.Path({str(marker)!r}).write_text("
                            "os.environ['AGENTIC_QUALITY_SCOPE'])",
                        ],
                    }
                ],
            )
            completed = invoke_gate(config, root, scope="staged")

            self.assertEqual(marker.read_text(encoding="utf-8"), "staged")

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
