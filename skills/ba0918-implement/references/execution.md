# Execution boundary

Read this reference before plan resolution, the unfinished-execution check, bootstrap,
fresh-session entry, context validation, or a blocking stop.

## Resolve the plan

Use candidates in this order:

1. a path explicitly supplied in the current invocation;
2. the path and content identity from the immediately preceding plan publication receipt;
3. the single `current` entry in a valid `open-plans.json`.

Conversation context may identify a candidate, but it is never execution evidence. Run the
helper's `resolve` command before any write. It reads the plan through the plan skill's reader
and verifies the registered path, plan bytes, plan id, revision, target specification bytes,
base-HEAD spec bytes, scope tree, steps, and human gates.

Ask the human only when no candidate is available, evidence is ambiguous, or candidate evidence
conflicts. Never select by modification time, filename order, or directory scanning. A plan that
is not registered is `plan_registration_missing`; do not repair its locator or accept a legacy
path. A plan the reader cannot parse is `plan_format_invalid`; report which part and stop.

```text
python3 <implement-runtime> resolve --repo <main-checkout> [--plan-path <repo-relative-plan>]
```

When using a publication receipt, provide both `--receipt-path` and `--receipt-identity`.

## Check for unfinished executions

Before creating anything, ask the helper whether this plan already has executions that did not
reach `implementation_green`:

```text
python3 <implement-runtime> residual --repo <main-checkout> --plan-id <plan-id>
```

It reads only the evidence directories under `.agents/artifacts/executions/<plan-id>/` — never
the branch list, so a branch someone created by hand is not mistaken for an execution — and
returns, per unfinished execution: when it started, how many steps were committed, the last
event and its reason, whether the branch exists and which commits (SHA and subject) it holds
beyond the last recorded commit, and whether the worktree exists, is registered, and which files
it has changed without a commit. `resumable.ok` is false only when the bound plan or
specification identities no longer match the repository; that execution cannot be continued and
only "start over" remains. An execution whose `binding.json` is missing or unreadable is listed
with its id and `resumable.ok: false` alone.

When the list is empty, bootstrap a new execution. Otherwise present the facts to the human in
plain language and let them choose between continuing one execution and starting over. The
human may first ask for an investigation: read the extra commits, the uncommitted diff, and the
stop reason, and advise with reasons — without changing the branch, the worktree, or the
evidence. The choice is theirs; do not infer it from silence or from the facts alone.

- Start over: bootstrap a new execution. Leave the old branch, worktree, and evidence in place;
  removing them is the human's manual task.
- Continue: run `resume` (below) and carry on from the step it names.

## Bootstrap

Before bootstrap, ensure the approved spec identities are committed at the selected base HEAD.
Do not copy dirty main-checkout files into the execution.

Choose a dedicated worktree path and run, passing the same plan selection you gave `resolve`
(`--plan-path`, or `--receipt-path` with `--receipt-identity`; without them the `current` plan is
taken):

```text
python3 <implement-runtime> bootstrap \
  --repo <main-checkout> \
  [--plan-path <repo-relative-plan> | --receipt-path <path> --receipt-identity <identity>] \
  --worktree <dedicated-path> \
  --executor <safe-executor-name> \
  [--backend <safe-backend-name>] \
  [--session-id <safe-session-or-unavailable>]
```

The helper performs a real write preflight, generates a path-safe execution id (a timestamp
plus random hex, which is also how the start time of an execution is read back later), writes immutable
`binding.json` (including the worktree path), creates the branch `implement/<execution-id>` and
the linked worktree from base HEAD, verifies Git identity, and writes `worktree-bound`. Test
editing is forbidden until this succeeds.

Never use an in-place fallback, delete a partial worktree, or reuse an execution id.

The helper derives the main checkout, the Git common directory, and the linked-worktree identity
from Git metadata only. A submodule, a bare repository, or a checkout whose identity does not
match is never accepted as the linked worktree. Every path the helper writes or stages must stay
inside the repository or the linked worktree: an absolute path, a `..` traversal, or a symlink
that resolves outside the boundary is rejected.

## Continue an unfinished execution

Only after the human chose to continue:

```text
python3 <implement-runtime> resume \
  --repo <main-checkout> --plan-id <plan-id> --execution-id <execution-id>
```

The helper reloads the execution from its evidence, refuses when the plan or spec identities
differ, and otherwise appends a `resumed` event recording the branch head, any commits beyond the
evidence, and whether uncommitted changes exist — so nothing is inherited silently. It returns the
step to continue from: the one after the last committed step. When that step already has RED,
GREEN, or REFACTOR evidence but no commit, it is marked `redo`: start it again from RED, and the
new RED replaces the earlier frozen oracle. Uncommitted changes are left untouched; the staging
helper still admits only paths inside the approved scope.

## Enter from a fresh session

Conversation history is optional. Reconstruct the execution from its evidence:

```text
python3 <implement-runtime> load --repo <main-checkout> \
  [--plan-id <plan-id> --execution-id <execution-id>]
```

Without ids the helper accepts only the single unfinished execution of the current plan (or its
single execution when none is unfinished); with several candidates it stops with
`execution_ambiguous` and lists them. It reads nothing but the evidence directory and
`binding.json`, then checks that the bound plan and spec identities still match, and that the
branch and the linked worktree exist. Every later command accepts the same two ids.

Then revalidate the current plan step before reading or editing implementation files. Step ids
are `step-<n>`, taken from the `### <n>.` headings under the plan's `## Steps` section:

```text
python3 <implement-runtime> context --repo <main-checkout> --step step-<n>
```

The context check compares the immutable binding with the current locator, plan, specs, Git
common directory, linked worktree, branch, base ancestry, current step, and every changed path.
Run it again at every RED, GREEN, REFACTOR, and commit boundary.

Each step's `**Completion:**` line decides how it is executed: `test` follows [tdd.md](tdd.md);
`artifact` and `external` follow [artifacts.md](artifacts.md). Evidence of the wrong kind for a
step is `completion_kind_mismatch` and a blocking stop.

## Planned human gates

Only decisions declared in the bound plan are valid. Record a decision without free-form text;
the helper computes the current target identity itself:

```text
python3 <implement-runtime> human-gate \
  --repo <main-checkout> --step step-<n> \
  --gate <declared-gate-id> --result <approved-or-rejected>
```

Before editing a step, explicitly check its `before_edit` boundary:

```text
python3 <implement-runtime> check-gates \
  --repo <main-checkout> --step step-<n> --timing before_edit
```

The staging helper enforces `before_commit`; the terminal helper enforces
`before_implementation_green`. A missing, rejected, malformed, undeclared, or stale decision is a
blocking stop. Do not substitute permission approval for a plan-declared human gate.

Compaction is not itself a stop condition. Stop without additional edits when the canonical
artifacts cannot reconstruct the current meaning or any identity differs.

## Blocking stop

On a blocking failure, freeze edits and commits first. Record the reason when durable evidence
is writable:

```text
python3 <implement-runtime> stop \
  --repo <main-checkout> \
  --step step-<n> \
  --reason <stable-failure-code>
```

A decision the plan does not make — a new input class, an error case, a product choice — is a
blocking stop of this kind: do not fill the gap; report it so the human can return it to
brainstorm. Do not analyze later steps for independence. Preserve already committed steps,
evidence, branch, and worktree. Never write progress or completion into the plan text, `open-plans.json`,
`status.md`, `session-history.md`, or `plans/progress`; the durable events are the only
record. Return the derived result, including the execution id, stop reason, step, last
sequence, branch, worktree, commits, and evidence path. The next invocation for the same plan
finds this execution through the unfinished-execution check and lets the human decide.

If evidence itself is unavailable, report an unverified stop from the observable runtime and Git
state. Never use that exception to assert progress or success.
