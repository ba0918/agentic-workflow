import importlib
import inspect
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
IMPLEMENT_HOME = ROOT / "tools/workflow-runtime/implement"
sys.path.insert(0, str(IMPLEMENT_HOME))
implement_runtime = importlib.import_module("implement_runtime")
REVIEW_HOME = ROOT / "tools/workflow-runtime/review"
sys.path.insert(0, str(REVIEW_HOME))
review_runtime = importlib.import_module("review_runtime")


def signature_contract(value: object) -> tuple[tuple[str, str, str], ...]:
    if not callable(value):
        raise TypeError("facade symbol is not callable")
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


class ReviewFacadeContractTest(unittest.TestCase):
    def test_public_symbols_keep_their_signatures(self) -> None:
        expected = {
            "RuntimeFailure": (("code", "POSITIONAL_OR_KEYWORD", "required"), ("message", "POSITIONAL_OR_KEYWORD", "required")),
            "RuntimeResult": (("value", "POSITIONAL_OR_KEYWORD", "required"), ("error", "POSITIONAL_OR_KEYWORD", "required")),
            "ok": (("value", "POSITIONAL_OR_KEYWORD", "None"),),
            "failure": (("code", "POSITIONAL_OR_KEYWORD", "required"), ("message", "POSITIONAL_OR_KEYWORD", "required")),
            "execution_binding": (("plan_key", "POSITIONAL_OR_KEYWORD", "required"), ("run_id", "POSITIONAL_OR_KEYWORD", "required"), ("approval_commit", "POSITIONAL_OR_KEYWORD", "required"), ("implement_sequence", "KEYWORD_ONLY", "required"), ("branch", "KEYWORD_ONLY", "None"), ("head", "KEYWORD_ONLY", "None"), ("worktree", "KEYWORD_ONLY", "None")),
            "standalone_binding": (("review_id", "POSITIONAL_OR_KEYWORD", "required"), ("base", "KEYWORD_ONLY", "required"), ("head", "KEYWORD_ONLY", "required"), ("spec_paths", "KEYWORD_ONLY", "required"), ("branch", "KEYWORD_ONLY", "None")),
            "input_kind": (("binding", "POSITIONAL_OR_KEYWORD", "required"),),
            "choose_comparison_base": (("explicit", "KEYWORD_ONLY", "required"), ("pull_request_target", "KEYWORD_ONLY", "required"), ("default_branch", "KEYWORD_ONLY", "required")),
            "requires_full_review": (("changed_dimensions", "POSITIONAL_OR_KEYWORD", "required"),),
            "resolve_input": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("review_id", "KEYWORD_ONLY", "required"), ("plan_key", "KEYWORD_ONLY", "None"), ("run_id", "KEYWORD_ONLY", "None"), ("branch", "KEYWORD_ONLY", "None"), ("base", "KEYWORD_ONLY", "None"), ("head", "KEYWORD_ONLY", "None"), ("pull_request_target", "KEYWORD_ONLY", "None"), ("spec_paths", "KEYWORD_ONLY", "None")),
            "review_directory": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required")),
            "append_event": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("event_type", "POSITIONAL_OR_KEYWORD", "required"), ("fields", "POSITIONAL_OR_KEYWORD", "required")),
            "load_events": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required")),
            "bind_review": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("model", "KEYWORD_ONLY", "required"), ("level", "KEYWORD_ONLY", "'standard'"), ("profiles", "KEYWORD_ONLY", "None"), ("model_source", "KEYWORD_ONLY", "'explicit'"), ("second_reviewer", "KEYWORD_ONLY", "None"), ("second_model", "KEYWORD_ONLY", "None")),
            "current_findings": (("events", "POSITIONAL_OR_KEYWORD", "required"),),
            "record_second_review": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("status", "KEYWORD_ONLY", "required"), ("actual_model", "KEYWORD_ONLY", "required"), ("summary", "KEYWORD_ONLY", "required")),
            "begin_stage": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("reviewer_context", "KEYWORD_ONLY", "required")),
            "record_findings": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("stage", "KEYWORD_ONLY", "required"), ("findings", "KEYWORD_ONLY", "required"), ("safety", "KEYWORD_ONLY", "required"), ("reviewer_context", "KEYWORD_ONLY", "required"), ("actual_model", "KEYWORD_ONLY", "None")),
            "close_finding": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("finding_id", "POSITIONAL_OR_KEYWORD", "required"), ("oracle_exit_code", "KEYWORD_ONLY", "required"), ("fix_commits", "KEYWORD_ONLY", "required"), ("operation", "KEYWORD_ONLY", "required"), ("result_summary", "KEYWORD_ONLY", "required")),
            "record_human_decision": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("finding_id", "POSITIONAL_OR_KEYWORD", "required"), ("decision", "KEYWORD_ONLY", "required"), ("reason", "KEYWORD_ONLY", "required")),
            "record_targeted_result": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("finding_id", "POSITIONAL_OR_KEYWORD", "required"), ("oracle_exit_code", "KEYWORD_ONLY", "required"), ("fix_commits", "KEYWORD_ONLY", "required"), ("operation", "KEYWORD_ONLY", "required"), ("result_summary", "KEYWORD_ONLY", "required")),
            "add_findings": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("candidates", "KEYWORD_ONLY", "required"), ("related_ids", "KEYWORD_ONLY", "required")),
            "record_progress": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required")),
            "mark_stale": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("reason", "KEYWORD_ONLY", "required")),
            "rebound_findings": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required"), ("spec_commit", "KEYWORD_ONLY", "required"), ("reason", "KEYWORD_ONLY", "required")),
            "complete_review": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("binding", "POSITIONAL_OR_KEYWORD", "required")),
            "load_review_binding": (("root", "POSITIONAL_OR_KEYWORD", "required"), ("review_id", "KEYWORD_ONLY", "None"), ("plan_key", "KEYWORD_ONLY", "None"), ("run_id", "KEYWORD_ONLY", "None")),
            "main": (("argv", "POSITIONAL_OR_KEYWORD", "None"),),
        }
        self.assertEqual(
            {name: signature_contract(getattr(review_runtime, name)) for name in expected},
            expected,
        )


if __name__ == "__main__":
    unittest.main()
