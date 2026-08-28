import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.quality.configuration_contract import uv_command


PROJECT_ROOT = Path(__file__).parents[3]
PLUGIN_ROOT = PROJECT_ROOT / "tools" / "quality"


class DesignCheckerTest(unittest.TestCase):
    def run_pylint(
        self, source: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                *uv_command("pylint==4.0.5", "python", "-m", "pylint"),
                "--load-plugins=plugins.design_checker",
                "--disable=all",
                *arguments,
                str(source),
            ],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(PLUGIN_ROOT),
                "UV_CACHE_DIR": "/tmp/agentic-workflow-uv-cache",
            },
            text=True,
            capture_output=True,
            check=False,
        )

    def test_suppression_comments_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "suppressed.py"
            source.write_text("value = missing  # pylint: disable=undefined-variable\n")

            completed = self.run_pylint(
                source,
                "--enable=forbidden-lint-suppression",
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("E9001", completed.stdout)
        self.assertIn("Inline lint suppression is forbidden", completed.stdout)

    def test_declared_pure_layer_rejects_infrastructure_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            domain = Path(directory) / "domain"
            domain.mkdir()
            source = domain / "rules.py"
            source.write_text("import subprocess\n", encoding="utf-8")

            completed = self.run_pylint(
                source,
                "--enable=forbidden-layer-import",
                "--pure-layer-patterns=*/domain/*.py",
                "--pure-layer-forbidden-imports=subprocess,pathlib,requests",
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("E9002", completed.stdout)
        self.assertIn("Pure layer cannot import subprocess", completed.stdout)

    def test_any_type_escape_hatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "untyped.py"
            source.write_text(
                "from typing import Any\n\ndef decode(value: Any) -> Any:\n    return value\n",
                encoding="utf-8",
            )

            completed = self.run_pylint(
                source,
                "--enable=forbidden-type-escape-hatch",
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("E9003", completed.stdout)
        self.assertIn("Type escape hatch Any is forbidden", completed.stdout)

    def test_typing_alias_cannot_hide_any_type_escape_hatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "aliased.py"
            source.write_text(
                "import typing as typing_module\n\n"
                "def decode(value: typing_module.Any) -> typing_module.Any:\n"
                "    return value\n",
                encoding="utf-8",
            )

            completed = self.run_pylint(
                source,
                "--enable=forbidden-type-escape-hatch",
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("E9003", completed.stdout)
        self.assertIn("Type escape hatch Any is forbidden", completed.stdout)

    def test_declared_pure_layer_rejects_direct_io_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            domain = Path(directory) / "domain"
            domain.mkdir()
            source = domain / "reader.py"
            source.write_text(
                "reader = open\n\ndef read() -> str:\n"
                "    with reader('state.txt') as handle:\n        return handle.read()\n",
                encoding="utf-8",
            )

            completed = self.run_pylint(
                source,
                "--enable=forbidden-pure-layer-call",
                "--pure-layer-patterns=*/domain/*.py",
                "--pure-layer-forbidden-calls=open,input,print",
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("E9004", completed.stdout)
        self.assertIn("Pure layer cannot call open directly", completed.stdout)

    def test_canonical_pure_layer_rejects_direct_io_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = (
                Path(directory)
                / "tools"
                / "workflow-runtime"
                / "review"
                / "review_model.py"
            )
            source.parent.mkdir(parents=True)
            source.write_text(
                "import pathlib\n\n"
                "def read_state() -> str:\n"
                "    return open('state.txt').read()\n",
                encoding="utf-8",
            )

            completed = self.run_pylint(
                source,
                f"--rcfile={PLUGIN_ROOT / 'pylint.rc'}",
                "--enable=forbidden-layer-import,forbidden-pure-layer-call",
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("E9002", completed.stdout)
        self.assertIn("E9004", completed.stdout)


if __name__ == "__main__":
    unittest.main()
