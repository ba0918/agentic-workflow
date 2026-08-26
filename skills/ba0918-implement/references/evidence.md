# Evidence and persistence

Read this reference before creating or retrying durable execution evidence, or when a write is
denied or fails.

## Store ownership

The main checkout owns both roots. Do not create a second store inside the linked worktree, and
do not create anything under `.agents/runtime/`: there is no repository-wide marker.

```text
.agents/artifacts/executions/<plan-id>/<execution-id>/  durable binding, oracle, events, status
.agents/tmp/executions/<execution-id>/                      disposable execution scratch
```

`binding.json` is immutable. It binds the execution, the plan and whether the commit it starts
from carried that plan, the spec identities,
repository, base HEAD, branch, worktree path, write scope, the steps and human decisions the
agent declared out of the plan, and safe executor provenance before the worktree exists. It is the only thing a fresh session needs, together with the event files,
to reconstruct the execution. When the human rebinds the execution to a revised plan, the
`binding.json` bytes stay as they are: the *effective binding* is `binding.json` with the plan,
specs, write scope, human gates, and steps of the last `rebound` event laid over it, and every
check uses the effective binding.

Events are one atomic file per sequence, named `<sequence>-<type>.json`. Their order is the
sequence and nothing else. Event types are `worktree-bound`, `red`, `green`, `refactor`, `check`,
`artifact`, `external`, `approval`, `commit`, `human_gate`, `delegated`, `returned`, `resumed`,
`rebound`, `history_approved`, `permission_required`, `recovering`, `stopped`, and
`implementation_green`. Existing files are never overwritten: the write itself refuses a target
that exists, so nothing has to compare one record against another to keep the record append-only.

**An event carries a fingerprint only to compare against something a human approved.** The
plan's, the specifications', the frozen test's, and the deliverable a human signed off. It
carries none of itself, none of the event before it, and none of the repository or worktree: a
64-character hex string with no purpose costs the reader as much as the writer.

`current-status` sits beside the events and is rewritten by the same operation that appends one.
It holds four things: the plan's path and revision, the steps that reached a commit, the last
event with its reason, and the branch and worktree. It never says what to do next, and it is
never deleted — a finished execution keeps its last status, which is how the unfinished ones are
told apart.

`delegated` records which executor and model the implementation was handed to; `returned` records
how far the delegated conversation got. Handing it over is cycle's work; this skill only writes
it down.

`recovering` records something the agent put right itself, with the reason. Three of them in a
row on one step, with nothing else in between, end in a `stopped` whose reason is
`recovery_exhausted`.

A `rebound` event moves the execution onto a revised plan: it holds the revised plan (id, path,
revision, identity), the spec identities, write scope, human gates and declared steps of that
revision, the step map (for each revised step, the previous step it matches and `carry` /
`continue` / `new`), the superseded previous steps, the branch head, the extra commits, and
whether uncommitted changes existed. Reading the chain through the last rebound renumbers the
evidence of carried steps and drops the evidence of superseded ones; the files themselves are
untouched.

A `history_approved` event holds the listing the human approved at the terminal — commits no
event explains, history paths outside the write scope, uncommitted changes outside it — and an
optional bounded reason. It is valid only while that listing is unchanged.

`check` holds the commands declared for the step with their exit codes — all of them successful, or the
event is not written — and every in-scope file that changed, with its content identity. It carries
no verdict: a check step has none. `artifact` holds the files a step produced (path and content
identity) and the format checks it ran (command and exit code); `external` holds what was checked
and a short result. `approval` is
the human's verdict on the newest of those, bound to the fingerprint of what they read. It is not a
`human_gate`: a `human_gate` records a decision the plan declared under `**Human gates:**`, while
an `approval` is required for every `artifact` and `external` step whether or not the plan
declares anything. `stopped` ends the chain except for one `resumed` event (the human chose to
continue) or one `rebound` event (the human chose to rebind); after it the chain goes on as
usual. Only `implementation_green` is final.

The event count is an observation for later plan-granularity analysis. It is never a hard limit,
scope verdict, or stop oracle.

## Minimal evidence

Store only what determines acceptance or a safe hand-off: bounded failure signature, command,
exit code, outcome, frozen target and oracle identities, test summary, commit SHA, stable stop
reason, and safe executor/backend/session identifiers.

Every RED, GREEN, and REFACTOR event carries a `test_summary` the helper computed from the
runner output. Never supply or edit it. It is `complete` with `passed`, `failed`, and
`skipped` counts only when the output holds exactly one `Ran N tests` line and one matching `OK`
or `FAILED (...)` line, as Python `unittest` prints; any other output yields `unavailable` with a
bounded reason. Do not report counts the helper did not record, and never infer them from an exit
code, a command count, or an ambiguous runner summary.

Never copy full stdout, stderr, provider logs, credentials, environment values, caches, or build
output into durable evidence. When safe provenance is unavailable, record `unavailable` and a
reason; that alone does not block GREEN. Root-cause investigation may follow a safe session or run
identifier to the provider's original log instead of duplicating it.

## Permission required

The first sandbox denial is `permission_required`, not persistence failure.

1. Freeze further edits and commits.
2. Keep the exact bytes you were about to record.
3. Request read or write permission for only the rejected path or operation.
4. Record again once it is granted.

Do not broaden permission to an entire home or configuration tree when one read-only file or
directory is sufficient.

## Persistence unavailable

Only a denied permission that cannot be granted, headless permission failure, continued read-only
storage, quota exhaustion, capacity failure, or I/O failure is `persistence_unavailable`.

Do not silently fall back to another store. Preserve the worktree, branch, commits, and all
events already made durable. If the stop event itself cannot be written, return an explicitly
unverified stop from runtime and Git observations. Code or tests passing without durable evidence
can never produce `implementation_green`.

## Derived result

There is no `result.json`. The helper derives:

- `not_started` before a durable execution;
- `stopped` after an execution without a valid terminal success;
- `implementation_green` only from the terminal event.

Result output includes only fields that exist. A stop identifies the reason, step, and last
durable sequence. A successful hand-off identifies the plan, execution, branch, worktree, commits,
and evidence path while leaving the plan open.
