#!/usr/bin/env python3
"""Stable public facade for the composed review runtime."""
from __future__ import annotations

from pathlib import Path
import sys


# Shared modules live in ../shared in the development tree and flattened next to
# this file in a distributed skill copy.
for _candidate in (
    Path(__file__).resolve().parent,
    Path(__file__).resolve().parents[1] / "shared",
):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from review_support.binding import (
    bind_review,
    choose_comparison_base,
    execution_binding,
    input_kind,
    load_review_binding,
    requires_full_review,
    resolve_input,
    selected_profiles as _selected_profiles,
    standalone_binding,
)
from review_support.cli import main
from review_support.events import append_event, current_findings, load_events
from review_support.findings import (
    add_findings,
    begin_stage,
    close_finding,
    complete_review,
    mark_stale,
    rebound_findings,
    record_findings,
    record_human_decision,
    record_progress,
    record_second_review,
    record_targeted_result,
)
from review_support.repository import review_directory
from review_support.types import RuntimeFailure, RuntimeResult, failure, ok
from review_support.validation import review_execution as _review_execution


__all__ = [
    "RuntimeFailure",
    "RuntimeResult",
    "add_findings",
    "append_event",
    "begin_stage",
    "bind_review",
    "choose_comparison_base",
    "close_finding",
    "complete_review",
    "current_findings",
    "execution_binding",
    "failure",
    "input_kind",
    "load_events",
    "load_review_binding",
    "main",
    "mark_stale",
    "ok",
    "rebound_findings",
    "record_findings",
    "record_human_decision",
    "record_progress",
    "record_second_review",
    "record_targeted_result",
    "requires_full_review",
    "resolve_input",
    "review_directory",
    "standalone_binding",
]


if __name__ == "__main__":
    raise SystemExit(main())
