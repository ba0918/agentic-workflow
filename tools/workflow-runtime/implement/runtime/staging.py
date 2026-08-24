"""Commit boundary: write-scope, credential judgment, staging, commit records."""
import re
from pathlib import PurePosixPath

from runtime.deps import execution_model
from runtime.types import RuntimeResult, Attempt, ok, failure
from runtime.gitio import run_git
from runtime.planning import step_completion_kinds
from runtime.context import load_events, validate_context, append_event
from runtime.storage import read_json
from runtime.tdd import validate_step_test_targets, validate_step_test_targets_at
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

def _committed_paths(attempt: Attempt, previous: str, commit_sha: str) -> RuntimeResult:
    changed = run_git(attempt.worktree, "diff", "--name-only", previous, commit_sha)
    if changed.returncode != 0:
        return failure("commit_invalid", "committed paths could not be observed")
    return ok([line for line in changed.stdout.splitlines() if line])


def _dirty_paths(attempt: Attempt) -> RuntimeResult:
    status = run_git(attempt.worktree, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode != 0:
        return failure("git_status_failed", "post-commit status could not be observed")
    return ok([line[3:] for line in status.stdout.splitlines() if line])


def _verify_commit_for_step(attempt: Attempt, step_id: str, committed: list[str], commit_sha: str) -> RuntimeResult:
    """The checks a commit must pass to become evidence of a step, however it is recorded."""
    context = validate_context(attempt, step_id=step_id)
    if not context.ok:
        return context
    kinds = step_completion_kinds(attempt)
    if not kinds.ok:
        return kinds
    if kinds.value.get(step_id) == "test":
        targets = validate_step_test_targets_at(attempt, step_id, commit_sha)
        if not targets.ok:
            return targets
    else:
        events = load_events(attempt)
        if not events.ok:
            return events
        if not execution_model.deliverable_is_approved(events.value, step_id):
            return failure("approval_missing", f"the latest deliverable of {step_id} has no approved verdict")
    for path in committed:
        validation = execution_model.validate_write_path(path, context.value["write_scope"])
        if not validation.ok:
            return failure(validation.error.code, validation.error.message, path)
    return ok(context.value)


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
    committed = _committed_paths(attempt, previous_head, current_head)
    if not committed.ok:
        return committed
    dirty = _dirty_paths(attempt)
    if not dirty.ok:
        return dirty
    # Only the commit's own files must be clean afterwards: that is how a hook rewriting what
    # was staged shows up. Other uncommitted files may predate the commit (a resumed
    # execution keeps them) and are the next commit's business, not this one's.
    if set(dirty.value) & set(committed.value):
        return failure("post_commit_dirty", "a committed file changed during or after the commit")
    verified = _verify_commit_for_step(attempt, step_id, committed.value, current_head)
    if not verified.ok:
        return verified
    return append_event(
        attempt,
        "commit",
        {
            "step_id": step_id,
            "commit_sha": current_head,
            "outcome": "committed",
        },
    )


def record_commit_late(attempt: Attempt, step_id: str, commit_sha: str) -> RuntimeResult:
    """Record a commit the branch already holds but the evidence never saw.

    A record-commit that was refused after the commit succeeded, or a session that died between
    the two, leaves a commit the history explains and the record does not; the human may continue
    such an execution, so the commit must be recordable under the same checks as a fresh one."""
    if not execution_model.COMMIT_SHA.fullmatch(commit_sha):
        return failure("commit_sha_invalid", "commit SHA is invalid")
    binding = read_json(attempt.binding_path)
    if not binding.ok:
        return binding
    history = run_git(attempt.worktree, "rev-list", "--parents", f"{binding.value['base_head']}..HEAD")
    rows = {line.split()[0]: line.split()[1:] for line in history.stdout.splitlines() if line}
    if history.returncode != 0 or commit_sha not in rows:
        return failure("commit_not_in_history", "the commit is not between the base and the branch head", commit_sha)
    if len(rows[commit_sha]) != 1:
        return failure("commit_range_invalid", "a merge commit cannot be recorded as a step's commit", commit_sha)
    events = load_events(attempt)
    if not events.ok:
        return events
    if any(event.get("event_type") == "commit" and event.get("commit_sha") == commit_sha for event in events.value):
        return failure("commit_already_recorded", "the commit already has a commit event", commit_sha)
    committed = _committed_paths(attempt, rows[commit_sha][0], commit_sha)
    if not committed.ok:
        return committed
    verified = _verify_commit_for_step(attempt, step_id, committed.value, commit_sha)
    if not verified.ok:
        return verified
    gates = check_human_gates(attempt, step_id=step_id, timing="before_commit")
    if not gates.ok:
        return gates
    return append_event(
        attempt,
        "commit",
        {
            "step_id": step_id,
            "commit_sha": commit_sha,
            "outcome": "committed",
            "recorded_late": True,
        },
    )
