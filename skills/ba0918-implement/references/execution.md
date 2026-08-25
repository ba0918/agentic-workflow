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
that no commit event explains — wherever they sit between the base and the head — and whether
the worktree exists, is registered, and which files it has changed without a commit. `resumable.ok`
is false only when the plan or specification identities the execution currently stands on (its
binding, as the last rebound left it) no longer match the repository; that execution cannot be
continued as it is. `rebindable.ok` then says whether it can be rebound instead: the current
registered plan must be a revision of the same plan, and the plan revision the execution was
bound to must still be readable. An execution whose `binding.json` is missing or unreadable is
listed with its id and `resumable.ok: false` alone.

When the list is empty, bootstrap a new execution. Otherwise present the facts to the human in
plain language and let them choose between continuing one execution, rebinding it to the revised
plan, and starting over. The human may first ask for an investigation: read the extra commits,
the uncommitted diff, and the stop reason, and advise with reasons — without changing the branch,
the worktree, or the evidence. The choice is theirs; do not infer it from silence or from the
facts alone.

- Start over: bootstrap a new execution. Leave the old branch, worktree, and evidence in place;
  removing them is the human's manual task.
- Continue: run `resume` (below) and carry on from the step it names.
- Rebind: run `rebind` (below), show the human its table, and record it only when they confirm.

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
differ (rebind instead), and otherwise appends a `resumed` event recording the branch head, the
commits the evidence does not explain, and whether uncommitted changes exist — so nothing is
inherited silently. It returns the step to continue from: the first step without a commit event.
When that step already has RED, GREEN, or REFACTOR evidence but no commit, it is marked `redo`:
start it again from RED, and the new RED replaces the earlier frozen oracle. When the step's
commit already exists on the branch — the commit succeeded and only its record failed — record
it late instead of redoing the work (`record-commit --commit <sha>`, see [tdd.md](tdd.md)).
Uncommitted changes are left untouched; the staging helper still admits only paths inside the
approved scope, and changes outside it are listed at the terminal for the human's approval.

## Rebind an execution to a revised plan

When the plan was revised (a new revision is registered as current) while an execution of it is
unfinished, the execution stands on the old revision and every forward command reports
`plan_identity_drift`. The human need not start over. First show them how the revision maps onto
the execution; this writes nothing:

```text
python3 <implement-runtime> rebind \
  --repo <main-checkout> --plan-id <plan-id> --execution-id <execution-id> \
  [--plan-path <repo-relative-revised-plan>]
```

The helper matches the steps of the bound revision and the revised plan by the identity of
their wording (heading and body, never the number), and returns a `step_map`: for each revised
step, `carry` (same wording, already committed — its evidence and commit are kept), `continue`
(same wording, not yet committed — resumed from its evidence), or `new` (no step with that
wording existed). Previous steps no revised step matches are `superseded_steps`: their evidence
no longer counts and they are done again, while their commits stay on the branch and are listed
at the terminal. It also names `next_step`, the first revised step that is not carried, and the
commits the evidence does not explain. Present the table in plain language and let the human
decide; a narrowed write scope does not block the rebind (the terminal lists what falls outside).

Only after the human confirmed:

```text
python3 <implement-runtime> rebind \
  --repo <main-checkout> --plan-id <plan-id> --execution-id <execution-id> \
  [--plan-path <repo-relative-revised-plan>] --confirm \
  --expect-plan-identity <the identity the preview printed>
```

`--expect-plan-identity` is required, and it is the `plan.content_identity` of the table the
human actually read. Another revision may be registered between reading and confirming, and
recording a rebound onto a revision nobody read would make the record and the decision two
different things; the helper refuses with `rebind_target_moved` and the preview is shown again.

This appends a `rebound` event carrying the revised plan (id, path, revision, identity), its
specification identities, write scope, human gates, the step map, the branch head, the extra
commits, and whether uncommitted changes exist. From then on every command checks against the
revised plan, and step ids are the revised numbering. The rebind target is the registered current
plan (or the registered plan at `--plan-path`) and must be the same plan id; when the bound
revision's file is no longer readable the rebind is refused and only starting over remains.

The review skill reads the binding of an execution as the last rebound left it, so a rebound
execution is handed to review like any other.

## Enter from a fresh session

Conversation history is optional. Reconstruct the execution from its evidence:

```text
python3 <implement-runtime> load --repo <main-checkout> \
  [--plan-id <plan-id> --execution-id <execution-id>]
```

Without ids the helper accepts only the single unfinished execution of the current plan (or its
single execution when none is unfinished); with several candidates it stops with
`execution_ambiguous` and lists them. It reads nothing but the evidence directory and
`binding.json`, and checks that the branch and the linked worktree exist. It does not require the
plan or spec identities to match: reading an execution and stopping it never depend on that, so a
revised plan is reported by `context`, not by `load`. Every later command accepts the same two
ids.

Then revalidate the current plan step before reading or editing implementation files. Step ids
are `step-<n>`, taken from the `### <n>.` headings under the plan's `## Steps` section:

```text
python3 <implement-runtime> context --repo <main-checkout> --step step-<n>
```

The context check compares the effective binding — the immutable `binding.json` as the last
`rebound` event left it — with the current locator, plan, specs, Git common directory, linked
worktree, branch, base ancestry, and current step. Uncommitted changes inside the write scope are
work in progress; changes outside it are returned as `out_of_scope_changes`, a fact for the
human, never a stop — the staging boundary keeps them out of commits and the terminal lists them.
Run the check again at every RED, GREEN, REFACTOR, and commit boundary.

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
is writable — this works even when the plan or specs no longer match the binding, so a revised
plan never leaves an execution unable to say that it stopped:

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

Not every unplanned fact is a blocking stop. Uncommitted changes outside the write scope, commits
no event explains, a defect in the helper itself (the helper is not part of the bound identities,
so repairing it mid-execution invalidates nothing), a frozen test that changed (accept a new RED
for the same step), a check command that failed (fix what it reports and record again), and a
record that failed to be written (record it late) are facts to show the human. A decision the plan does not make about the deliverable is
the only reason to return to brainstorm.

## Terminal hand-off and the history approval

The terminal check (`implementation-green`) compares every commit between the base and the head
with the `commit` events, the paths the history touched with the write scope, and the worktree
with the scope. In-scope uncommitted leftovers are a stop (`post_verification_dirty`: something was
not committed); a recorded commit missing from the history is a stop (`commit_identity_drift`: the
branch was rewritten). Everything else the evidence does not explain — commits without a commit
event, history paths outside the scope, uncommitted changes outside the scope — is listed and
answered with `history_approval_required`, without a stop event. Present the listing to the
human; when they approve it, record it:

```text
python3 <implement-runtime> approve-history --repo <main-checkout> [--reason <short-reason>]
```

The `history_approved` event holds the listing itself, so the approval is valid only while the
listing is unchanged; a later commit or change is listed again. Then run `implementation-green`
again. When nothing needs approval, the terminal completes without one, and `approve-history`
refuses with `history_approval_unnecessary`.
