---
name: ba0918-review
description: Use when an implementation execution has handed over implementation_green evidence and needs an independent review. Runs one full review that freezes a findings set, then re-reviews only unresolved findings against trailer-marked fix commits. Records which model reviewed. Does not fix code, drive the fix loop, judge final acceptance, or merge.
---

# Review

Examine one finished implementation execution with independent eyes. Review has exactly two
jobs, and the promise between them is what makes the loop finite:

1. **First review**: read the implementation once, produce a set of findings, and freeze that
   set as one durable event.
2. **Diff re-review**: after fixes, look only at the unresolved findings and the commits that
   name them; never add new findings, except risks the fix itself introduced.

A finding's id is derived from its oracle — the mechanical way to tell whether it is fixed —
so the same problem keeps the same id while line numbers move. Severity (`security`,
`critical`, `warn`, `info`) and action (`auto_fix`, `fix_and_verify`, `human_judgment`,
`record_only`) are independent: neither is derived from the other, and an `info` finding is
only ever recorded. A finding without a workable oracle must say why none can be written and
becomes a human judgment, closed only by a recorded decision. Findings sharing a root cause
are presented together as one fix unit; grouping changes the presentation only — every
finding keeps its own id and oracle.

## Load routing

- For the whole procedure — verifying the hand-off, choosing the model, the first review,
  freezing the set, and the re-review loop — read [review.md](references/review.md).
- For where records live and what each event means, read
  [evidence.md](references/evidence.md).
- Read only the profile the runtime selects for the diff (under `references/profile/`); do
  not preload every profile.

## Boundary

- Own the findings set: its creation, its freezing, the verdicts that open and close findings,
  and the records of who reviewed with which model at which strength.
- The helper `scripts/review_runtime.py` owns input verification, finding validation, id
  derivation, oracle execution, and every durable record. Do not re-implement its checks in
  prose or shell.
- Do not fix code, drive the fix loop, or call a fixing role.
- Do not judge final acceptance, merge into the main branch, publish, or clean the worktree.
- Do not update plan text, plan indexes, status files, or session histories.
- Do not fix `info` findings automatically.
- Do not run a second reviewer nobody asked for.
- Do not delegate the first review to a built-in review command or an official review
  plugin: they are not present for every AI, their quality varies, and they carry neither
  finding ids nor a bounded re-review.

## Completion

Review is complete for a round when every finding in the frozen set is `closed`, `stale`, or
`deferred`, or when it stops on a condition the human must resolve (a revised specification,
an unfinishable security check, a finding that will not close). When something review needs
is missing — the human, the evidence, the worktree, or an environment that can run the
oracles — it never claims success: it stops incomplete and resumable instead.
