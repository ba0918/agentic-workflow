# Review evidence

Execution review records live under
`.agents/evidence/<plan-key>/<run-id>/review/`. Standalone review records live under
`.agents/evidence/reviews/<review-id>/`.

Use one numbered append-only JSON file per event. Bind the input commits, specification paths and
Git version, selected profile, reviewer and model, and for execution input the implementation's
last event sequence. Do not add document or event hash chains.

Record stage starts, safety-checked finding sets, related finding additions, and one targeted
result that binds each finding's trailer-linked fix commits and oracle result. Derive the before
and after tuples from those events rather than accepting caller-supplied counts. Completion is a
derived state after final results and all admitted findings are closed; do not append a separate
completion event. Unrelated
`warn`/`info` observations remain terminal observations. `findings_stale` is a pause that may be
followed by rebound; it is not completion. Never duplicate raw logs or sensitive content.
