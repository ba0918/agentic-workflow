"""Discover, summarize, resume, and logically retire implementation runs."""
from pathlib import Path
import subprocess
import sys

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
import implementation_evidence

from runtime.context import append_event, load_events
from runtime.repository import load_run
from runtime.secret_detect import contains_secret
from runtime.storage import read_json
from runtime.types import Run, RuntimeResult, failure, ok

def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)

def _worktree_registration(root: Path, branch: str, worktree: str) -> bool:
    listed = _git(root, "worktree", "list", "--porcelain")
    if listed.returncode != 0:
        return False
    expected_branch = f"branch refs/heads/{branch}"
    return any(
        f"worktree {worktree}" in block.splitlines() and expected_branch in block.splitlines()
        for block in listed.stdout.strip().split("\n\n")
    )

def _uncommitted_paths(worktree: Path) -> list[str]:
    status = _git(worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return []
    return sorted({line[3:] for line in status.stdout.splitlines() if len(line) >= 4})

def _git_facts(root: Path, binding: dict, events: list[dict]) -> RuntimeResult:
    branch = binding.get("branch")
    worktree_value = binding.get("worktree")
    if not branch or not worktree_value:
        return ok({
            "branch": {"name": branch, "exists": False, "tip": None, "unexplained_commits": []},
            "worktree": {"path": worktree_value, "registered": False, "uncommitted_paths": []},
        })
    tip = _git(root, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    exists = tip.returncode == 0
    unexplained: list[dict[str, str]] = []
    if exists:
        history = _git(root, "rev-list", "--reverse", f"{binding['approval_commit']}..{tip.stdout.strip()}")
        if history.returncode != 0:
            return failure("resume_git_state_invalid", "implementation branch history is unavailable")
        explained = {event.get("commit") for event in events if event.get("event_type") == "commit"}
        explained |= {
            event.get("approval_commit") or event.get("current_commit") for event in events
            if event.get("event_type") in {"rebound", "recovering"}
        }
        for commit in filter(None, history.stdout.splitlines()):
            if commit in explained:
                continue
            subject = _git(root, "show", "-s", "--format=%s", commit).stdout.strip()
            if contains_secret(subject.encode()):
                subject = "[redacted secret-shaped subject]"
            unexplained.append({"sha": commit, "subject": subject})
    worktree = Path(worktree_value)
    registered = worktree.is_dir() and _worktree_registration(root, branch, str(worktree.resolve()))
    return ok({
        "branch": {
            "name": branch, "exists": exists, "tip": tip.stdout.strip() if exists else None,
            "unexplained_commits": unexplained,
        },
        "worktree": {
            "path": str(worktree.resolve()), "registered": registered,
            "uncommitted_paths": _uncommitted_paths(worktree) if registered else [],
        },
    })

def _summary(run: Run) -> RuntimeResult:
    binding = read_json(run.binding_path)
    events = load_events(run)
    if not binding.ok or not events.ok:
        return binding if not binding.ok else events
    derived = implementation_evidence.derive_implementation(binding.value, events.value)
    if not derived.ok:
        return failure(derived.error.code, derived.error.message)
    facts = _git_facts(run.root, binding.value, events.value)
    if not facts.ok:
        return facts
    last = events.value[-1] if events.value else {}
    remaining = [
        step["id"] for step in derived.value["steps"]
        if step["id"] not in derived.value["completed_steps"]
    ]
    return ok({
        "plan": {"key": run.plan_key, "path": binding.value.get("plan_path")},
        "run_id": run.run_id, "started_at": binding.value.get("started_at"),
        "started_at_status": "recorded" if binding.value.get("started_at") else "unavailable",
        "last_event": {"event_type": last.get("event_type"), "reason": last.get("reason") or last.get("summary")},
        "completed_steps": derived.value["completed_steps"], "remaining_steps": remaining,
        **facts.value,
    })

def discover_unfinished(root: Path, plan_key: str) -> RuntimeResult:
    store = root.resolve() / ".agents/evidence" / plan_key
    if not store.is_dir():
        return ok([])
    summaries: list[dict] = []
    for directory in sorted(store.iterdir()):
        loaded = load_run(root, plan_key, directory.name)
        if not loaded.ok:
            return loaded
        summary = _summary(loaded.value)
        if not summary.ok:
            return summary
        binding = read_json(loaded.value.binding_path)
        events = load_events(loaded.value)
        derived = implementation_evidence.derive_implementation(binding.value, events.value)
        if not derived.ok:
            return failure(derived.error.code, derived.error.message)
        complete = any(event.get("event_type") == "implementation_green" for event in events.value)
        if not complete and not derived.value["resume_candidate_retired"]:
            summaries.append(summary.value)
    return ok(summaries)

def resume_run(root: Path, *, plan_key: str, run_id: str) -> RuntimeResult:
    loaded = load_run(root, plan_key, run_id)
    if not loaded.ok:
        return loaded
    summary = _summary(loaded.value)
    if not summary.ok:
        return summary
    branch = summary.value["branch"]
    if not branch["exists"] or not summary.value["worktree"]["registered"]:
        return failure("resume_git_state_invalid", "bound branch and worktree must exist before resuming")
    binding = read_json(loaded.value.binding_path)
    events = load_events(loaded.value)
    derived = implementation_evidence.derive_implementation(binding.value, events.value)
    if not derived.ok:
        return failure(derived.error.code, derived.error.message)
    resumed = append_event(loaded.value, "resumed", {
        "branch_head": branch["tip"],
        "unexplained_commits": [item["sha"] for item in branch["unexplained_commits"]],
        "uncommitted_paths": summary.value["worktree"]["uncommitted_paths"],
    }, actor="implement")
    if not resumed.ok:
        return resumed
    return ok({"run": loaded.value, "resume_step": derived.value["resume_step"], "event": resumed.value})

def retire_run(root: Path, *, plan_key: str, run_id: str, reason: str) -> RuntimeResult:
    if not reason.strip():
        return failure("retirement_reason_missing", "logical run retirement needs a reason")
    loaded = load_run(root, plan_key, run_id)
    if not loaded.ok:
        return loaded
    return append_event(loaded.value, "resume-candidate-retired", {"reason": reason}, actor="implement")
