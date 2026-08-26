"""Load the plan reader shipped with this runtime."""
import importlib.util
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
PLAN_READER_PATH = HOME / "plan_artifact.py"
if not PLAN_READER_PATH.is_file():
    PLAN_READER_PATH = HOME.parent / "plan/plan_artifact.py"

specification = importlib.util.spec_from_file_location("workflow_plan_reader", PLAN_READER_PATH)
if specification is None or specification.loader is None:
    raise RuntimeError(f"cannot load plan reader: {PLAN_READER_PATH}")
plan_artifact = importlib.util.module_from_spec(specification)
specification.loader.exec_module(plan_artifact)
