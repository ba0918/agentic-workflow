# Review procedure

Bind one Git-resolved input and its specification Git commit before reading the change. A branch
and both ends of a commit range must exist. An implementation run must have contiguous evidence,
a valid final `implementation_green`, and matching branch/worktree/commit facts. The initial reviewer
reads the complete diff, selected profiles, relevant specification sections, and direct callers
needed to judge security or critical candidates. Record `initial-full-review-started`, then one
initial findings event; these are separate transitions.

Every admitted finding carries specification path/section and Git version, evidence, root cause,
profile, severity, action, and state. A fixable finding also records `oracle_status: failing` after
the reviewer ran its oracle and observed failure. An unavailable mechanical oracle needs a bounded
reason for human judgment.

After fixes, read only open findings, trailer-linked fix commits, their affected evidence, and new
risk introduced by those fixes. Run each oracle yourself. Compare open counts
`(security, critical, warn)` lexicographically. On no decrease, diagnose the finding,
implementation, specification, and tooling, change the method once, and return to the human only
if it still does not decrease.

When all findings close, start a fresh-context reviewer for exactly one final full review. Record
`final-full-review-started` separately from its safety check and findings result. Add its findings
to the same set and close them through targeted review. Only after those results exist and all
admitted findings close may the runtime append `review-completed`; do not synthesize completion
from an empty in-memory list or run another full pass.

Repeat a full review before the final pass only when structure, assumptions, order, dependencies,
completion conditions, review scope topology, or governing specifications changed.
