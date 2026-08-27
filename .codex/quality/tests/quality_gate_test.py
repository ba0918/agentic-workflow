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
    output: str | None = None,
) -> subprocess.CompletedProcess[str]:
    arguments = [sys.executable, str(QUALITY_GATE), "--config", str(config)]
    if project_root is not None:
        arguments.extend(["--root", str(project_root)])
    if output is not None:
        arguments.extend(["--output", output])
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

    def test_all_successful_checks_allow_the_turn_to_stop(self) -> None:
        completed = self.run_gate(
            [
                {
                    "name": "passing-check",
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                }
            ]
        )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout), {"continue": True})

    def test_failed_check_keeps_the_turn_running_with_its_diagnostic(self) -> None:
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

        response = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(response["decision"], "block")
        self.assertIn("broken-check", response["reason"])
        self.assertIn("repair this", response["reason"])

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

        response = json.loads(completed.stdout)
        self.assertEqual(response["decision"], "block")
        self.assertIn("missing-check", response["reason"])

    def test_empty_check_list_blocks_instead_of_silently_disabling_the_gate(self) -> None:
        completed = self.run_gate([])

        response = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(response["decision"], "block")
        self.assertIn("no checks configured", response["reason"])

    def test_invalid_check_definition_blocks_with_a_configuration_diagnostic(self) -> None:
        completed = self.run_gate([{"name": "missing-command"}])

        response = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(response["decision"], "block")
        self.assertIn("configuration", response["reason"])
        self.assertIn("argv", response["reason"])

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
        self.assertEqual(json.loads(completed.stdout), {"continue": True})

    def test_cli_output_returns_failure_to_the_calling_git_hook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "checks.json"
            write_config(
                config,
                [
                    {
                        "name": "broken-check",
                        "argv": [
                            sys.executable,
                            "-c",
                            "print('repair this'); raise SystemExit(7)",
                        ],
                    }
                ],
            )
            completed = invoke_gate(config, root, output="cli")

        self.assertEqual(completed.returncode, 1)
        self.assertIn("broken-check", completed.stderr)
        self.assertIn("repair this", completed.stderr)

    def test_cli_output_allows_the_calling_git_hook_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "checks.json"
            write_config(
                config,
                [
                    {
                        "name": "passing-check",
                        "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    }
                ],
            )
            completed = invoke_gate(config, root, output="cli")

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
