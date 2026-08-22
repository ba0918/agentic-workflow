# Evidence and persistence

Read this reference before creating or retrying durable execution evidence, or when a write is
denied or fails.

## Store ownership

The main checkout owns all three roots. Do not create a second store inside the linked worktree.

```text
.agents/artifacts/executions/<plan-id>/<attempt-id>/  durable binding, oracle, and events
.agents/runtime/cycles/current.claim                  repository-wide normal-Cycle claim
.agents/runtime/cycles/<attempt-id>/                  host-local control
.agents/tmp/cycles/<attempt-id>/                      disposable attempt scratch
```

`binding.json` is immutable. It binds the attempt, registered Plan, spec identities, repository,
base HEAD, branch, write scope, and safe executor provenance before the worktree exists.

Events are one atomic file per sequence. Each carries the attempt, Plan and spec identities,
previous-event identity, and its own content identity. Event types are `worktree-bound`, `red`,
`green`, `refactor`, `commit`, `stopped`, and `implementation_green`. Existing files are never
overwritten.

The event count is an observation for later Plan-granularity analysis. It is never a hard limit,
scope verdict, or stop oracle.

## Minimal evidence

Store only what determines acceptance or a safe hand-off: bounded failure signature, exit code,
pass/fail/skip summary when available, oracle identity, commit SHA, stable stop reason, and safe
executor/backend/session identifiers.

Never copy full stdout, stderr, provider logs, credentials, environment values, caches, or build
output into durable evidence. When safe provenance is unavailable, record `unavailable` and a
reason; that alone does not block GREEN. Root-cause investigation may follow a safe session or run
identifier to the provider's original log instead of duplicating it.

## Permission required

The first sandbox denial is `permission_required`, not persistence failure.

1. Freeze further edits and commits.
2. Keep the exact candidate bytes and content identity.
3. Request read or write permission for only the rejected path or operation.
4. Retry the same identity.
5. Treat an existing identical event as success and a different event as collision.

Do not broaden permission to an entire home or configuration tree when one read-only file or
directory is sufficient.

## Persistence unavailable

Only a denied permission that cannot be granted, headless permission failure, continued read-only
storage, quota exhaustion, capacity failure, or I/O failure is `persistence_unavailable`.

Do not silently fall back to another store. Preserve the worktree, branch, commits, claim, and all
events already made durable. If the stop event itself cannot be written, return an explicitly
unverified stop from runtime and Git observations. Code or tests passing without durable evidence
can never produce `implementation_green`.

## Derived result

There is no `result.json`. The helper derives:

- `not_started` before a durable attempt;
- `stopped` after an attempt without a valid terminal success;
- `implementation_green` only from the terminal event.

Result output includes only fields that exist. A stop identifies the reason, step, and last
durable sequence. A successful hand-off identifies the Plan, attempt, branch, worktree, commits,
and evidence path while leaving the Plan open.
