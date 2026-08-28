"""Public entry point for the implementation runtime."""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime.planning import locate_plan, plan_candidates, resolve_plan
from runtime.repository import bind_run
from runtime.context import append_event, load_events
from runtime.tdd import freeze_test, frozen_test_matches
from runtime.types import Run, RuntimeFailure, RuntimeResult
from runtime.cli import main

__all__ = [
    "Run",
    "RuntimeFailure",
    "RuntimeResult",
    "append_event",
    "bind_run",
    "freeze_test",
    "frozen_test_matches",
    "load_events",
    "locate_plan",
    "main",
    "plan_candidates",
    "resolve_plan",
]

if __name__ == "__main__":
    raise SystemExit(main())
