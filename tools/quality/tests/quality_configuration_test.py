import configparser
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.quality.configuration_contract import uv_command, validate_configuration


PROJECT_ROOT = Path(__file__).resolve().parents[3]
QUALITY_ROOT = PROJECT_ROOT / "tools" / "quality"


def copy_configuration(destination: Path) -> Path:
    quality = destination / "tools" / "quality"
    quality.mkdir(parents=True)
    for name in ("checks.json", "mypy.ini", "pylint.rc"):
        shutil.copy2(QUALITY_ROOT / name, quality / name)
    return quality


class ConfigurationContractTest(unittest.TestCase):
    def test_repository_configuration_matches_the_canonical_contract(self) -> None:
        self.assertEqual(validate_configuration(PROJECT_ROOT), ())

    def test_configuration_weakening_and_alternate_commands_are_rejected(self) -> None:
        replacements = (
            ("pylint.rc", "duplicate-code", ""),
            ("pylint.rc", "plugins.design_checker", ""),
            (
                "pylint.rc",
                "pure-layer-patterns=*/tools/workflow-runtime/review/review_model.py,"
                "*/tools/workflow-runtime/shared/implementation_evidence.py",
                "pure-layer-patterns=",
            ),
            (
                "pylint.rc",
                "pure-layer-forbidden-imports=fcntl,os,pathlib,shutil,socket,subprocess,tempfile",
                "pure-layer-forbidden-imports=",
            ),
            (
                "pylint.rc",
                "pure-layer-forbidden-calls=input,open,print",
                "pure-layer-forbidden-calls=",
            ),
            ("mypy.ini", "strict = True", "strict = False"),
            ("mypy.ini", "[mypy]", "[mypy]\nignore_errors = True"),
            ("mypy.ini", "[mypy]", "[mypy]\nexclude = tools/quality"),
            ("mypy.ini", "[mypy]", "[mypy]\n\n[mypy-tools.quality.*]"),
            ("checks.json", '"tools/workflow-runtime"', '"tools/quality"'),
            ("checks.json", '"--config-file"', '"--strict"'),
            ("checks.json", '"configuration-contract"', '"python-types-weak"'),
        )
        for filename, before, after in replacements:
            with self.subTest(filename=filename, before=before), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                quality = copy_configuration(root)
                target = quality / filename
                text = target.read_text(encoding="utf-8")
                self.assertIn(before, text)
                target.write_text(text.replace(before, after, 1), encoding="utf-8")
                self.assertTrue(validate_configuration(root))

    def test_pure_layer_boundaries_are_declared_in_canonical_configuration(self) -> None:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(QUALITY_ROOT / "pylint.rc", encoding="utf-8")

        self.assertEqual(
            parser.get("BA0918-DESIGN", "pure-layer-patterns", fallback=""),
            "*/tools/workflow-runtime/review/review_model.py,"
            "*/tools/workflow-runtime/shared/implementation_evidence.py",
        )
        self.assertEqual(
            parser.get("BA0918-DESIGN", "pure-layer-forbidden-imports", fallback=""),
            "fcntl,os,pathlib,shutil,socket,subprocess,tempfile",
        )
        self.assertEqual(
            parser.get("BA0918-DESIGN", "pure-layer-forbidden-calls", fallback=""),
            "input,open,print",
        )


class QualityToolConfigurationTest(unittest.TestCase):
    def test_pylint_configuration_detects_required_categories_without_noise_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.py"
            second = root / "second.py"
            repeated = "\n".join(f"    value_{index} = {index}" for index in range(8))
            methods = "\n".join(
                f"    def method_{index}(self):\n        return {index}"
                for index in range(22)
            )
            first.write_text(
                "import os\n\n"
                "def BadName(foo, bar, baz, qux, quux, corge):\n"
                f"{repeated}\n"
                "    return missing\n\n"
                f"class TooLarge:\n{methods}\n",
                encoding="utf-8",
            )
            second.write_text(
                "def duplicate():\n"
                f"{repeated}\n"
                "    return value_7\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    *uv_command("pylint==4.0.5", "python", "-m", "pylint"),
                    f"--rcfile={QUALITY_ROOT / 'pylint.rc'}",
                    str(first),
                    str(second),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        for symbol in (
            "invalid-name",
            "too-many-arguments",
            "too-many-public-methods",
            "undefined-variable",
            "unused-import",
        ):
            self.assertIn(symbol, completed.stdout)
        for disabled in (
            "missing-function-docstring",
            "line-too-long",
            "too-few-public-methods",
            "too-many-instance-attributes",
        ):
            self.assertNotIn(disabled, completed.stdout)

    def test_strict_mypy_rejects_untyped_functions_and_invalid_returns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.py"
            source.write_text(
                "def untyped(value):\n    return value\n\n"
                "def invalid_return() -> int:\n    return 'text'\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    *uv_command("mypy==1.18.2", "mypy"),
                    "--config-file",
                    str(QUALITY_ROOT / "mypy.ini"),
                    str(source),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("no-untyped-def", completed.stdout)
        self.assertIn("return-value", completed.stdout)


if __name__ == "__main__":
    unittest.main()
