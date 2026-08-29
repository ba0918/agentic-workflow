import json
from pathlib import Path
import subprocess
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LEFTHOOK = PROJECT_ROOT / "node_modules" / ".bin" / "lefthook"


class LefthookConfigurationTest(unittest.TestCase):
    def test_pre_commit_uses_the_repository_quality_gate(self) -> None:
        completed = subprocess.run(
            [str(LEFTHOOK), "dump", "--format", "json"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        configuration = json.loads(completed.stdout)
        self.assertEqual(
            configuration["pre-commit"]["commands"]["quality-gate"]["run"],
            "python3 tools/quality/quality_gate.py --scope staged",
        )

    def test_agent_stop_hooks_check_the_worktree_scope(self) -> None:
        for configuration_path in (
            PROJECT_ROOT / ".codex" / "hooks.json",
            PROJECT_ROOT / ".claude" / "settings.json",
        ):
            configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
            for event in ("Stop", "SubagentStop"):
                command = configuration["hooks"][event][0]["hooks"][0]["command"]
                self.assertTrue(
                    command.endswith("agents/stop_hook.py\" --scope worktree"),
                    f"{configuration_path.name} {event}: {command}",
                )

    def test_claude_code_checks_each_written_file_right_after_the_edit(self) -> None:
        configuration = json.loads(
            (PROJECT_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
        )

        entry = configuration["hooks"]["PostToolUse"][0]
        self.assertEqual(entry["matcher"], "Write|Edit")
        command = entry["hooks"][0]["command"]
        self.assertTrue(command.endswith("agents/post_tool_use.py\""), command)
        self.assertLessEqual(entry["hooks"][0]["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
