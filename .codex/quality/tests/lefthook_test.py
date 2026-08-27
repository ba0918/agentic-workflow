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
            "python3 .codex/quality/quality_gate.py --output cli",
        )


if __name__ == "__main__":
    unittest.main()
