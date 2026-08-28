import importlib
import inspect
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
IMPLEMENT_HOME = ROOT / "tools/workflow-runtime/implement"
sys.path.insert(0, str(IMPLEMENT_HOME))
implement_runtime = importlib.import_module("implement_runtime")


def signature_contract(value: object) -> tuple[tuple[str, str, str], ...]:
    signature = inspect.signature(value)
    return tuple(
        (
            parameter.name,
            parameter.kind.name,
            "required" if parameter.default is inspect.Parameter.empty else repr(parameter.default),
        )
        for parameter in signature.parameters.values()
    )


class ImplementFacadeContractTest(unittest.TestCase):
    def test_public_symbols_keep_their_signatures(self) -> None:
        expected = {
            "Run": (("run_id", "POSITIONAL_OR_KEYWORD", "required"), ("plan_key", "POSITIONAL_OR_KEYWORD", "required"), ("root", "POSITIONAL_OR_KEYWORD", "required"), ("evidence_path", "POSITIONAL_OR_KEYWORD", "required"), ("binding_path", "POSITIONAL_OR_KEYWORD", "required")),
            "RuntimeFailure": (("code", "POSITIONAL_OR_KEYWORD", "required"), ("message", "POSITIONAL_OR_KEYWORD", "required"), ("detail", "POSITIONAL_OR_KEYWORD", "None")),
            "RuntimeResult": (("value", "POSITIONAL_OR_KEYWORD", "required"), ("error", "POSITIONAL_OR_KEYWORD", "required")),
            "locate_plan": (("project_root", "POSITIONAL_OR_KEYWORD", "required"), ("plan_path", "POSITIONAL_OR_KEYWORD", "None")),
            "plan_candidates": (("project_root", "POSITIONAL_OR_KEYWORD", "required"),),
            "resolve_plan": (("project_root", "POSITIONAL_OR_KEYWORD", "required"), ("plan_path", "KEYWORD_ONLY", "None")),
            "bind_run": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("plan", "POSITIONAL_OR_KEYWORD", "required"), ("run_id", "KEYWORD_ONLY", "required"), ("delegated", "KEYWORD_ONLY", "required"), ("branch", "KEYWORD_ONLY", "None"), ("worktree", "KEYWORD_ONLY", "None")),
            "append_event": (("run", "POSITIONAL_OR_KEYWORD", "required"), ("event_type", "POSITIONAL_OR_KEYWORD", "required"), ("fields", "POSITIONAL_OR_KEYWORD", "required"), ("actor", "KEYWORD_ONLY", "None")),
            "load_events": (("run", "POSITIONAL_OR_KEYWORD", "required"),),
            "freeze_test": (("files", "POSITIONAL_OR_KEYWORD", "required"), ("command", "KEYWORD_ONLY", "required")),
            "frozen_test_matches": (("snapshot", "POSITIONAL_OR_KEYWORD", "required"), ("files", "POSITIONAL_OR_KEYWORD", "required"), ("command", "KEYWORD_ONLY", "required")),
            "main": (("argv", "POSITIONAL_OR_KEYWORD", "None"),),
        }
        self.assertEqual(
            {name: signature_contract(getattr(implement_runtime, name)) for name in expected},
            expected,
        )


if __name__ == "__main__":
    unittest.main()
