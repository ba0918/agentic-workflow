import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.quality.tests.git_repository import (
    initialize_repository,
    install_quality_checks,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = PROJECT_ROOT / "tools" / "quality" / "quality_gate.py"
CODEX_STOP = PROJECT_ROOT / "tools" / "quality" / "agents" / "codex_stop.py"


def write_config(config: Path, exit_code: int) -> None:
    config.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "name": "probe",
                        "argv": [
                            sys.executable,
                            "-c",
                            f"print('probe diagnostic'); raise SystemExit({exit_code})",
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def invoke(
    entrypoint: Path,
    root: Path,
    config: Path,
) -> subprocess.CompletedProcess[str]:
    config_text = config.read_text(encoding="utf-8")
    initialize_repository(root)
    canonical_config = install_quality_checks(root, config_text)
    working_directory = root / "nested"
    working_directory.mkdir(exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            str(entrypoint),
            "--root",
            str(root),
            "--config",
            str(canonical_config),
            "--scope",
            "worktree",
        ],
        cwd=working_directory,
        text=True,
        capture_output=True,
        check=False,
    )


class QualityEntrypointsTest(unittest.TestCase):
    def test_common_cli_uses_standard_exit_codes_outside_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            passing = root / "passing.json"
            failing = root / "failing.json"
            write_config(passing, 0)
            write_config(failing, 7)

            passed = invoke(QUALITY_GATE, root, passing)
            failed = invoke(QUALITY_GATE, root, failing)

        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(passed.stdout, "")
        self.assertEqual(failed.returncode, 1)
        self.assertIn("probe", failed.stderr)
        self.assertIn("probe diagnostic", failed.stderr)

    def test_codex_adapter_translates_common_results_to_stop_responses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            passing = root / "passing.json"
            failing = root / "failing.json"
            write_config(passing, 0)
            write_config(failing, 7)

            passed = invoke(CODEX_STOP, root, passing)
            failed = invoke(CODEX_STOP, root, failing)

        self.assertEqual(passed.returncode, 0)
        self.assertEqual(json.loads(passed.stdout), {"continue": True})
        self.assertEqual(failed.returncode, 0)
        response = json.loads(failed.stdout)
        self.assertEqual(response["decision"], "block")
        self.assertIn("probe diagnostic", response["reason"])

    def test_repository_entrypoints_keep_codex_out_of_the_common_cli(self) -> None:
        lefthook = (PROJECT_ROOT / "lefthook.yml").read_text(encoding="utf-8")
        codex_hooks = json.loads(
            (PROJECT_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8")
        )

        self.assertIn("python3 tools/quality/quality_gate.py --scope staged", lefthook)
        self.assertNotIn("agents/codex_stop.py", lefthook)
        for event in ("Stop", "SubagentStop"):
            command = codex_hooks["hooks"][event][0]["hooks"][0]["command"]
            self.assertIn("tools/quality/agents/codex_stop.py", command)

    def test_codex_configuration_is_the_only_file_under_dot_codex(self) -> None:
        files = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (PROJECT_ROOT / ".codex").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )

        self.assertEqual(files, [".codex/hooks.json"])


if __name__ == "__main__":
    unittest.main()
