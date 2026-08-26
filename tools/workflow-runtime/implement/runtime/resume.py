"""Discovery and continuation of unfinished implementation runs."""
from pathlib import Path
import sys

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
import implementation_evidence

from runtime.context import append_event, load_events
from runtime.storage import read_json
from runtime.types import Run, RuntimeResult, failure, ok

def select_unfinished(runs: list[dict]) -> RuntimeResult:
    unfinished = [run for run in runs if run.get("state") not in {"completed", "abandoned"}]
    if not unfinished:
        return ok(None)
    if len(unfinished) > 1:
        return failure("run_candidate_ambiguous", "several unfinished runs exist")
    return ok(unfinished[0])

def discover_unfinished(root: Path, plan_key: str) -> RuntimeResult:
    store = root.resolve() / ".agents/evidence" / plan_key
    if not store.is_dir():
        return ok([])
    runs: list[Run] = []
    for directory in sorted(store.iterdir()):
        binding_path = directory / "binding.json"
        binding = read_json(binding_path)
        if not binding.ok or not isinstance(binding.value, dict):
            return binding if not binding.ok else failure("evidence_invalid", "implementation binding is invalid")
        run = Run(directory.name, plan_key, root.resolve(), directory, binding_path)
        events = load_events(run)
        if not events.ok:
            return events
        derived = implementation_evidence.derive_implementation(binding.value, events.value)
        if not derived.ok:
            return failure(derived.error.code, derived.error.message)
        if not any(event.get("event_type") == "implementation_green" for event in events.value):
            runs.append(run)
    return ok(runs)

def _resume_step(run: Run) -> RuntimeResult:
    binding = read_json(run.binding_path)
    events = load_events(run)
    if not binding.ok or not events.ok:
        return binding if not binding.ok else events
    derived = implementation_evidence.derive_implementation(binding.value, events.value)
    if not derived.ok:
        return failure(derived.error.code, derived.error.message)
    return ok(derived.value["resume_step"])

def resume_unique(
    root: Path,
    *,
    plan_key: str,
    branch_head: str,
    unexplained_commits: list[str],
    uncommitted_paths: list[str],
    consequential_change: bool,
) -> RuntimeResult:
    discovered = discover_unfinished(root, plan_key)
    if not discovered.ok:
        return discovered
    if len(discovered.value) != 1:
        return failure("run_candidate_ambiguous", "exactly one unfinished run is required")
    if consequential_change:
        return failure("rebound_or_new_run_required", "consequential document meaning changed")
    run = discovered.value[0]
    point = _resume_step(run)
    if not point.ok:
        return point
    resumed = append_event(run, "resumed", {
        "branch_head": branch_head,
        "unexplained_commits": list(unexplained_commits),
        "uncommitted_paths": sorted(uncommitted_paths),
    }, actor="implement")
    if not resumed.ok:
        return resumed
    return ok({"run": run, "resume_step": point.value, "event": resumed.value})
