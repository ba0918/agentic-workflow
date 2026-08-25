"""Entry point of the implement runtime; the implementation lives in runtime/."""
# ruff: noqa: E402, F401
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# The runtime package is not installed anywhere; both homes (the canonical tree and
# the vendored copy inside the skill) resolve it from this directory. Loading both
# homes in one process would reuse the first home's cached `runtime` modules.
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime.deps import execution_model, plan_artifact
from runtime import cli, context, deliverables, gates, gitio, planning, repository, resume, staging, storage, tdd
from runtime.types import (
    Attempt,
    RepositoryInfo,
    ResolvedPlan,
    RuntimeFailure,
    RuntimeResult,
    failure as _failure,
    ok as _ok,
)
from runtime.gitio import discover_repository, run_git as _git
from runtime.storage import read_json as _read_json, write_once
from runtime.planning import resolve_plan
from runtime.repository import bootstrap_attempt, execution_branch
from runtime.context import (
    append_event,
    derive_attempt_result,
    load_events as _load_events,
    validate_context,
)
from runtime.resume import load_current_attempt, residual_executions, resume_execution
from runtime.tdd import (
    accept_red,
    bounded_observation as _bounded_observation,
    classify_process_failure as _classify_process_failure,
    execute_oracle as _execute_oracle,
    run_frozen_oracle,
    test_summary as _test_summary,
)
from runtime.gates import check_human_gates, record_human_gate
from runtime.deliverables import record_approval, record_artifact, record_check, record_external
from runtime.staging import record_commit, record_commit_late, stage_paths
from runtime.cli import generate_attempt_id, main, mark_implementation_green

if __name__ == "__main__":
    sys.exit(main())
