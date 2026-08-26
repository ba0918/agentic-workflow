# Evidence

Store binding and numbered append-only JSON events under
`.agents/evidence/<plan-key>/<run-id>/`. Binding names the plan path and approval Git commit.
Event ordering comes from the six-digit filename sequence; do not add event, plan, specification,
profile, or deliverable hash chains.

In a direct implement run, implement is the single writer of this evidence. When cycle delegates
implementation, cycle records `delegated` and `returned`; implement writes only between those
boundaries and remains the sole writer of implementation steps, commands, and results until
control returns.

Use the runtime commands for branch/worktree binding, stage evidence, commit records, stop,
rebound, and completion. It validates event fields and order, derives safety from the actual Git
staging area and commit objects, and derives
`implementation_green`; never append it directly. The same append operation atomically refreshes
`current-status` with the plan Git version, committed steps, last event/reason, and bound
branch/worktree.

Keep only bounded facts required for verification and hand-off: steps, commands and exit codes,
safe summaries, commit SHAs, delegation boundaries, document-meaning decisions, recovery, stops,
and unplanned paths with reasons. A RED event stores the frozen test/fixture bytes and command;
GREEN and REFACTOR recompute and compare that snapshot before they may be recorded.

Never store secrets, environment values, personal data, internal hosts, raw output, caches, logs,
or generated scratch. A stopped event may always be appended even while documents differ.
