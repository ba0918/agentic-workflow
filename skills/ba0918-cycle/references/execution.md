# Execution boundary

Read this reference before plan resolution, bootstrap, fresh-session entry, context validation,
or a blocking stop.

## Resolve the plan

Use candidates in this order:

1. a path explicitly supplied in the current invocation;
2. the path and content identity from the immediately preceding Plan publication receipt;
3. the single `current` entry in a valid `open-plans.json`.

Conversation context may identify a candidate, but it is never execution evidence. Run the
helper's `resolve` command before any write. It verifies the registered path, plan bytes, Plan ID,
revision, referenced spec bytes, base-HEAD spec bytes, and write scope.

Ask the human only when no candidate is available, evidence is ambiguous, or candidate evidence
conflicts. Never select by modification time, filename order, or directory scanning. A plan that
is not registered is `plan_registration_missing`; do not repair its locator or accept a legacy
path.

```text
python3 <cycle-runtime> resolve --repo <main-checkout> [--plan-path <repo-relative-plan>]
```

When using a publication receipt, provide both `--receipt-path` and `--receipt-identity`.

## Bootstrap

Before bootstrap, ensure the approved spec identities are committed at the selected base HEAD.
Do not copy dirty main-checkout files into the execution.

Choose a dedicated worktree path and run:

```text
python3 <cycle-runtime> bootstrap \
  --repo <main-checkout> \
  --worktree <dedicated-path> \
  --executor <safe-executor-name> \
  [--backend <safe-backend-name>] \
  [--session-id <safe-session-or-unavailable>]
```

The helper performs a real write preflight, atomically acquires the repository claim, generates a
path-safe attempt ID, writes immutable `binding.json`, creates the branch and linked worktree from
base HEAD, verifies Git identity, and writes `worktree-bound`. Test editing is forbidden until
this succeeds.

Never use an in-place fallback. Never reclaim a claim from a PID, delete a partial worktree, or
reuse an attempt ID.

The helper derives the main checkout, the Git common directory, and the linked-worktree identity
from Git metadata only. A submodule, a bare repository, or a checkout whose identity does not
match is never accepted as the linked worktree. Every path the helper writes or stages must stay
inside the repository or the linked worktree: an absolute path, a `..` traversal, or a symlink
that resolves outside the boundary is rejected.

## Enter from a fresh session

Conversation history is optional. Reconstruct the attempt from the main checkout:

```text
python3 <cycle-runtime> load --repo <main-checkout>
```

Then revalidate the current plan step before reading or editing implementation files. Step IDs
are `step-<n>`, taken from the `### <n>.` headings under the bound Plan's `## 実装手順` section;
a Plan without that structure cannot be executed:

```text
python3 <cycle-runtime> context --repo <main-checkout> --step step-<n>
```

The context check compares the immutable binding with the current locator, plan, specs, Git
common directory, linked worktree, branch, base ancestry, current step, and every changed path.
Run it again at every RED, GREEN, REFACTOR, and commit boundary.

## Planned human gates

Only decisions declared in the bound Plan are valid. Record a decision without free-form text;
the helper computes the current target identity itself:

```text
python3 <cycle-runtime> human-gate \
  --repo <main-checkout> --step step-<n> \
  --gate <declared-gate-id> --result <approved-or-rejected>
```

Before editing a step, explicitly check its `before_edit` boundary:

```text
python3 <cycle-runtime> check-gates \
  --repo <main-checkout> --step step-<n> --timing before_edit
```

The staging helper enforces `before_commit`; the terminal helper enforces
`before_implementation_green`. A missing, rejected, malformed, undeclared, or stale decision is a
blocking stop. Do not substitute permission approval for a Plan-declared human gate.

Compaction is not itself a stop condition. Stop without additional edits when the canonical
artifacts cannot reconstruct the current meaning or any identity differs.

## Blocking stop

On a blocking failure, freeze edits and commits first. Record the reason when durable evidence
is writable:

```text
python3 <cycle-runtime> stop \
  --repo <main-checkout> \
  --step step-<n> \
  --reason <stable-failure-code>
```

Do not analyze later steps for independence. Preserve already committed steps, evidence, branch,
claim, and worktree. Never write progress or completion into the Plan text, `open-plans.json`,
`status.md`, `session-history.md`, or `plans/progress`; the durable events are the only
record. Return the derived result, including the attempt, stop reason, step, last
sequence, branch, worktree, commits, and evidence path.

If evidence itself is unavailable, report an unverified stop from the observable runtime and Git
state. Never use that exception to claim progress or success.
