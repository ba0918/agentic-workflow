# Review evidence

Execution review records live under
`.agents/evidence/<plan-key>/<run-id>/review/`. Standalone review records live under
`.agents/evidence/reviews/<review-id>/`.

Use one numbered append-only JSON file per event. Bind the input commits, specification paths and
Git version, selected profile, reviewer and model, and for execution input the implementation's
last event sequence. Do not add document or event hash chains.

Record stage starts, safety-checked finding sets, related finding additions, trailer-linked closes,
lexicographic progress decisions, and final completion as separate later events. Unrelated
`warn`/`info` observations remain terminal observations. `findings_stale` is a pause that may be
followed by rebound; it is not completion. Never duplicate raw logs or sensitive content.
