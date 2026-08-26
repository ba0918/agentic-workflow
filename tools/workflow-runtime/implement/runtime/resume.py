"""Selection of unfinished implementation runs."""
from runtime.types import RuntimeResult, failure, ok

def select_unfinished(runs: list[dict]) -> RuntimeResult:
    unfinished = [run for run in runs if run.get("state") not in {"completed", "abandoned"}]
    if not unfinished:
        return ok(None)
    if len(unfinished) > 1:
        return failure("run_candidate_ambiguous", "several unfinished runs exist")
    return ok(unfinished[0])
