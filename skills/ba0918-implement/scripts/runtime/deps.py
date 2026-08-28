"""Load the plan reader shipped with this runtime."""
import importlib.util
from pathlib import Path
import sys

for candidate in (
    Path(__file__).resolve().parents[2] / "shared",
    Path(__file__).resolve().parents[1],
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
import git_status
import implementation_evidence

HOME = Path(__file__).resolve().parents[1]
PLAN_READER_PATH = HOME / "plan_artifact.py"
if not PLAN_READER_PATH.is_file():
    PLAN_READER_PATH = HOME.parent / "plan/plan_artifact.py"

specification = importlib.util.spec_from_file_location("workflow_plan_reader", PLAN_READER_PATH)
if specification is None or specification.loader is None:
    raise RuntimeError(f"cannot load plan reader: {PLAN_READER_PATH}")
plan_artifact = importlib.util.module_from_spec(specification)
specification.loader.exec_module(plan_artifact)

__all__ = ["git_status", "implementation_evidence", "plan_artifact"]
