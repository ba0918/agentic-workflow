# Evidence

Store binding and numbered append-only JSON events under
`.agents/evidence/<plan-key>/<run-id>/`. Binding names the plan path and approval Git commit.
Event ordering comes from the six-digit filename sequence; do not add event, plan, specification,
profile, or deliverable hash chains.

In a direct implement run, implement is the single writer of this evidence. When cycle delegates
implementation, cycle records only the delegation boundary; implement remains the sole writer of
implementation steps, commands, and results until control returns.

Keep only bounded facts required for verification and hand-off: steps, commands and exit codes,
safe summaries, commit SHAs, delegation boundaries, document-meaning decisions, recovery, stops,
and unplanned paths with reasons. Keep the frozen RED test hash separately.

Never store secrets, environment values, personal data, internal hosts, raw output, caches, logs,
or generated scratch. A stopped event may always be appended even while documents differ.
