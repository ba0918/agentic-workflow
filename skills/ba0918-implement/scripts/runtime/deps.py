"""Loads the two shared modules the runtime builds on, wherever this copy lives."""
import importlib.util
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


execution_model = load_module("ba0918_implement_execution_model", HOME / "execution_model.py")

# The runtime lives in two homes: the canonical tree (tools/workflow-runtime/implement/,
# where plan_artifact.py sits in the sibling plan/) and the vendored copy
# (skills/ba0918-implement/scripts/, where it sits in the plan skill's scripts/).
_PLAN_ARTIFACT_HOMES = (
    HOME.parent / "plan/plan_artifact.py",
    HOME.parents[1] / "ba0918-plan/scripts/plan_artifact.py",
)
plan_artifact = load_module(
    "ba0918_plan_artifact_consumer",
    next(path for path in _PLAN_ARTIFACT_HOMES if path.is_file()),
)
