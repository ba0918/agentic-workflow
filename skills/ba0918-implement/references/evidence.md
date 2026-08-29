# Evidence

Store binding and numbered append-only JSON events under
`.agents/evidence/<plan-key>/<run-id>/`. Binding names the plan path and approval Git commit.
It also records the complete Step contracts derived from the approved plan; never accept a caller's
replacement list.
Event ordering comes from the six-digit filename sequence; do not add event, plan, specification,
profile, or deliverable hash chains.

In a direct implement run, implement is the single writer of this evidence. When cycle delegates
implementation, cycle records `delegated` and `returned`; implement writes only between those
boundaries and remains the sole writer of implementation steps, commands, and results until
control returns.

Use the runtime commands for stage evidence, commit records, stop, declared Human gates, rebound,
and completion. The runtime validates event fields and order, derives safety from the actual Git
staging area and commit objects, and derives `implementation_green`; never append it directly.
Branch/worktree binding belongs to whoever creates the run: implement in a direct run, cycle
before delegating. The same append operation atomically refreshes
`current-status` with the plan Git version, committed steps, last event/reason, and bound
branch/worktree.

Record a declared Human gate only through the dedicated command after the human answers:

```sh
python3 scripts/implement_runtime.py human-gate \
  --repo <repository> --plan-key <plan-key> --run-id <run-id> \
  --step <step> --gate-id <gate-id> --result <approved-or-rejected>
```

The runtime obtains the target, timing, and allowed results from the active binding. Do not accept
caller replacements for those declaration fields or append a generic approval in their place.
A `before_commit` gate applies only when Git-observed changed paths require the completed Step to
produce a commit. When a check or external Step has no observed changed paths, do not request or
record that gate; complete the Step without a commit.

Bindings and events use version 2. Reject legacy version 1 rather than guessing its completion
state. Binding stays append-only: `recovering` records harmless document following, while
`rebound` records the effective approval commit, Step contracts and Scope re-derived from that
committed plan, and a caller-supplied validated one-to-one mapping.

Keep only bounded facts required for verification and hand-off: steps, commands and exit codes,
safe summaries, commit SHAs, delegation boundaries, document-meaning decisions, recovery, stops,
and unplanned paths with reasons. A RED event stores the frozen test/fixture bytes and command;
GREEN and REFACTOR recompute and compare that exact snapshot before they may be recorded or read
as complete. A later genuine RED is the only event that replaces the accepted snapshot. `check`
needs at least one successful command; `artifact` may have no format checker, but still needs its
artifact path, commit, and independently reviewable result. External evidence records what was
checked, a bounded result summary, and whether the condition was met.

Discovery validates the version 2 binding and complete event stream before choosing a run. Derive
the resume point and a safe Git-backed summary before appending the single `resumed` event; a unique
candidate is still shown to the human without automatic mutation. In a delegated run, cycle performs
discovery and appends `resumed`; the delegated implement continues from the recorded boundary. Binding records `started_at` at
creation; an older version 2 binding without it reports the value as unavailable and never guesses
from file timestamps. A legacy or malformed run must return an error without changing its events or
`current-status`. `resume-candidate-retired` is an append-only logical exclusion from default
discovery, not deletion; explicit run-id inspection and resumption remain available.

Safety reads path names from Git itself and never the changed content. Report the offending path
and its category when a path is rejected. Keeping credentials out of what you commit and record is
your responsibility, not the runtime's. A commit event is valid only for a unique commit after the
approval commit and on the bound branch. At completion the branch's approval-to-HEAD commit set
and the recorded commit set must match in both directions.

Never store secrets, environment values, personal data, internal hosts, raw output, caches, logs,
or generated scratch. A stopped event may always be appended even while documents differ.
