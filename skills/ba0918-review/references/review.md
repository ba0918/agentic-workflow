# Review procedure

Bind one input and its specification Git commit before reading the change. The initial reviewer
reads the complete diff, selected profiles, relevant specification sections, and direct callers
needed to judge security or critical candidates. Record one initial findings event.

After fixes, read only open findings, trailer-linked fix commits, their affected evidence, and new
risk introduced by those fixes. Run each oracle yourself. Compare open counts
`(security, critical, warn)` lexicographically. On no decrease, diagnose the finding,
implementation, specification, and tooling, change the method once, and return to the human only
if it still does not decrease.

When all findings close, start a fresh-context reviewer for exactly one final full review. Add its
findings to the same set and close them through targeted review. Do not run another full pass.

Repeat a full review before the final pass only when structure, assumptions, order, dependencies,
completion conditions, review scope topology, or governing specifications changed.
