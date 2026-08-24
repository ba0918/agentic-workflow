"""Commit boundary: write-scope, credential judgment, staging, commit records."""
import re
from pathlib import PurePosixPath

from runtime.deps import execution_model
from runtime.types import RuntimeResult, Attempt, ok, failure
from runtime.gitio import run_git
from runtime.planning import step_completion_kinds
from runtime.context import load_events, validate_context, append_event
from runtime.tdd import validate_step_test_targets
from runtime.gates import check_human_gates


_CREDENTIAL_QUOTED = re.compile(
    rb"(?i)(api[_-]?key|secret|token|password|credential)\s*[=:]\s*[\"'][^\"'\n]{4,}[\"']"
)

_CREDENTIAL_BARE = re.compile(
    rb"(?i)(api[_-]?key|secret|token|password|credential)\s*[=:]\s*(?P<value>[^\s\"',;\\\\]+)"
)

_CODE_REFERENCE = re.compile(rb"[A-Za-z_][A-Za-z_.]*")

def _resembles_credential(data: bytes) -> bool:
    """True when a credential-named value looks like a secret: quoted, or bare mixing digits.

    A value that is code — a call, a subscript, an identifier or attribute path — is not a
    secret. Judging by name alone made every commit that stages this repository's own
    scanner or validator code impossible."""
    if _CREDENTIAL_QUOTED.search(data):
        return True
    for match in _CREDENTIAL_BARE.finditer(data):
        value = match.group("value")
        # A value in angle brackets is a placeholder, not a secret; the pre-judgment
        # scan excluded leading "<" the same way.
        if value.startswith(b"<"):
            continue
        if b"(" in value or b"[" in value:
            continue
        if _CODE_REFERENCE.fullmatch(value):
            continue
        return True
    return False

def stage_paths(attempt: Attempt, paths: list[str], *, step_id: str) -> RuntimeResult:
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return context
    scopes = context.value["write_scope"]
    for path in paths:
        validation = execution_model.validate_write_path(path, scopes)
        if not validation.ok:
            return failure(validation.error.code, validation.error.message, path)
    for path in paths:
        candidate = attempt.worktree.joinpath(*PurePosixPath(path).parts)
        try:
            content = candidate.read_bytes() if candidate.is_file() else b""
        except OSError as error:
            return failure("stage_failed", "approved path could not be inspected", str(error))
        if _resembles_credential(content):
            return failure("secret_detected", "candidate content resembles a credential assignment")
    kinds = step_completion_kinds(attempt)
    if not kinds.ok:
        return kinds
    if kinds.value.get(step_id) == "test":
        targets = validate_step_test_targets(attempt, step_id)
        if not targets.ok:
            return targets
    else:
        events = load_events(attempt)
        if not events.ok:
            return events
        if not execution_model.deliverable_is_approved(events.value, step_id):
            return failure("approval_missing", f"the latest deliverable of {step_id} has no approved verdict")
    gates = check_human_gates(attempt, step_id=step_id, timing="before_commit")
    if not gates.ok:
        return gates
    for path in paths:
        staged = run_git(attempt.worktree, "add", "--", path)
        if staged.returncode != 0:
            return failure("stage_failed", "Git could not stage an approved path", staged.stderr.strip())
    observed = run_git(attempt.worktree, "diff", "--cached", "--name-only", "--diff-filter=AM")
    if observed.returncode != 0:
        return failure("stage_failed", "staged paths could not be observed", observed.stderr.strip())
    staged_paths = tuple(line for line in observed.stdout.splitlines() if line)
    if set(staged_paths) != set(paths):
        return failure("stage_scope_mismatch", "staging contains missing or additional paths")
    for path in staged_paths:
        validation = execution_model.validate_write_path(path, scopes)
        if not validation.ok:
            return failure(validation.error.code, validation.error.message, path)
    staged_diff = run_git(attempt.worktree, "diff", "--cached", "--")
    if _resembles_credential(staged_diff.stdout.encode("utf-8")):
        return failure("secret_detected", "staged content resembles a credential assignment")
    return ok(staged_paths)

def record_commit(attempt: Attempt, step_id: str, previous_head: str) -> RuntimeResult:
    current = run_git(attempt.worktree, "rev-parse", "HEAD")
    current_head = current.stdout.strip()
    if (
        current.returncode != 0
        or not execution_model.COMMIT_SHA.fullmatch(previous_head)
        or current_head == previous_head
    ):
        return failure("commit_missing", "commit did not advance HEAD")
    commit_range = run_git(
        attempt.worktree,
        "rev-list",
        "--reverse",
        "--parents",
        f"{previous_head}..{current_head}",
    )
    rows = [line.split() for line in commit_range.stdout.splitlines() if line]
    if (
        commit_range.returncode != 0
        or len(rows) != 1
        or len(rows[0]) != 2
        or rows[0][0] != current_head
        or rows[0][1] != previous_head
    ):
        return failure(
            "commit_range_invalid",
            "recorded operation must produce exactly one non-merge commit from previous HEAD",
        )
    status = run_git(attempt.worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return failure("git_status_failed", "post-commit status could not be observed")
    if status.stdout.strip():
        return failure("post_commit_dirty", "worktree changed during or after commit")
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return context
    kinds = step_completion_kinds(attempt)
    if not kinds.ok:
        return kinds
    if kinds.value.get(step_id) == "test":
        targets = validate_step_test_targets(attempt, step_id)
        if not targets.ok:
            return targets
    changed = run_git(
        attempt.worktree,
        "diff",
        "--name-only",
        previous_head,
        current_head,
    )
    if changed.returncode != 0:
        return failure("commit_invalid", "committed paths could not be observed")
    for path in changed.stdout.splitlines():
        validation = execution_model.validate_write_path(path, context.value["write_scope"])
        if not validation.ok:
            return failure(validation.error.code, validation.error.message, path)
    return append_event(
        attempt,
        "commit",
        {
            "step_id": step_id,
            "commit_sha": current_head,
            "outcome": "committed",
        },
    )
