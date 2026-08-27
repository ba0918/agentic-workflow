# Review procedure

Bind one Git-resolved input and its specification Git commit before reading the change. A branch
and both ends of a commit range must exist. An implementation run must have contiguous evidence,
a valid final `implementation_green`, and matching branch/worktree/revision-segment facts. A
wording-only `recovering` commit or approved `rebound` commit may be the branch tip after the last
implementation commit; validate each segment against its effective approval boundary instead of
requiring the last implementation commit itself to equal the tip. The initial reviewer
reads the complete diff, selected profiles, relevant specification sections, and direct callers
needed to judge security or critical candidates. Record `initial-full-review-started`, then one
initial findings event; these are separate transitions.

For specification conformance, build the chain `specification heading -> Verification coverage ->
Step portfolio -> evidence -> diff`. Confirm every relevant heading is covered, each direct proof
observes the promised behavior at the right boundary, and at least one meaningful counterexample
would make it fail. Treat lint, type checking, snapshots without semantic assertions, and mocked
interactions as supporting evidence unless they directly establish the requirement. A missing
safe test or check is a fixable verification gap. Missing product meaning, a new dependency,
external access, or permission is a human boundary rather than an invented oracle.

Before recording either findings set, the same reviewer supplies a small safety result containing
`completed`, a bounded `summary`, and `unresolved`. Continue only when completed is true and
unresolved is empty. The runtime stores that result; it never substitutes a hard-coded pass.

The binding records level, profiles and their selection source, requested model and its selection
source, and optional second-reviewer settings. The skill owns second-reviewer execution: send only
the plan and diff after a secret scan, omit the first reviewer's findings and conclusion, invoke
the explicitly requested replaceable runner once, then record its actual model and bounded result.
If unavailable, record a warning and continue with the first reviewer.

Every admitted finding carries specification path/section and Git version, evidence, root cause,
profile, severity, action, and state. A fixable finding also records `oracle_status: failing` after
the reviewer ran its oracle and observed failure. An unavailable mechanical oracle needs a bounded
reason for human judgment.

After fixes, read only open findings, trailer-linked fix commits, their affected evidence, and new
risk introduced by those fixes. An open finding can close only after its corresponding
`targeted-review-started`; record its fix commits and oracle result together in one
`targeted-review-result`. For a two-commit input, select a fix head that descends from the original
head and derive the exact trailer-linked set from that range; reject side/non-descendant commits.
Run each oracle yourself. Derive and compare open counts
`(security, critical, warn)` lexicographically. On no decrease, diagnose the finding,
implementation, specification, and tooling, change the method once, and return to the human only
if it still does not decrease.

An oracle stored in a finding is a proposed decision method, not a shell command. Read its intent,
then choose a safe local operation rooted at the reviewed worktree. Do not accept absolute paths,
outside writes, irreversible commands, external publication, or credential-dependent operations.
Record the operation actually chosen, its exit code, and a bounded result summary independently of
the proposal. A safe equivalent may close the finding; the absence of one becomes a human-judgment
reason and never a fabricated passing result.

When all findings close, start a fresh-context reviewer for exactly one final full review. Record
`final-full-review-started` separately from its safety check and findings result. Add its findings
to the same set and close them through targeted review. Only after those results exist and all
admitted findings close may the runtime report derived completion. It never appends a caller-
asserted completion event; do not synthesize completion from an empty in-memory list or run another
full pass.

Repeat a full review before the final pass only when structure, assumptions, order, dependencies,
completion conditions, review scope topology, or governing specifications changed.
