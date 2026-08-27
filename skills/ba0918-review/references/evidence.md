# Review evidence

Execution review records live under
`.agents/evidence/<plan-key>/<run-id>/review/`. Standalone review records live under
`.agents/evidence/reviews/<review-id>/`.

Use one numbered append-only JSON file per event. Bind the input commits, specification paths and
Git version, selected profile, reviewer and model, and for execution input the implementation's
last event sequence. Do not add document or event hash chains.

Record stage starts, safety-checked finding sets, related finding additions, and one targeted
result that binds each finding's trailer-linked fix commits, the reviewer-selected safe local
operation, its worktree-relative execution context, exit code, and bounded result summary. Keep the
finding's oracle proposal unchanged as data; never record it as though it were the executed action. Derive the before
and after tuples from those events rather than accepting caller-supplied counts. Completion is a
derived state after final results and all admitted findings are closed; do not append a separate
completion event. Unrelated
`warn`/`info` observations remain terminal observations. `findings_stale` is a pause that may be
followed by rebound; it is not completion. Never duplicate raw logs or sensitive content.

Each initial/final findings event includes the same reviewer's explicit bounded safety result.
Binding and review events also preserve level, selected profiles, selection sources, requested
models, explicitly supplied actual models, and the one optional second-review result or unavailable
warning. Initial and final results are incomplete when their actual model is missing; never copy the
requested model into that field.

Validate review IDs before constructing paths, keep resolved stores below `.agents/evidence`, and
reject symlinks in every parent. On every read, reduce the complete version 2 event stream through
the same schema and stage-order rules used for writing. A final result cannot exist before a valid
initial start/result and convergence.

Before writing or reading a finding, scan every nested string without returning matched values.
Repository paths must be relative, specification paths and Git versions must match the active
binding, and the profile must be one selected by that review. Apply the same safe bounded-text rule
to added findings, terminal observations, reviewer contexts, decisions, and summaries.
