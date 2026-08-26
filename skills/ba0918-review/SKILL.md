---
name: ba0918-review
description: Use for an independent review of an implementation run, branch, or two-commit range. Performs one initial full review, targeted convergence, and one final full review without fixing the work.
metadata:
  contracts:
    - review-runtime
---

# Review

Review independently. Own findings and their append-only records; never edit the reviewed work or
delegate fixes.

## Load routing

- Read [review.md](references/review.md) for input binding and the three review stages.
- Read [evidence.md](references/evidence.md) before writing findings or verdicts.
- Load only the profiles selected by changed file type from `references/profile/`.

## Boundary

- Accept an implement run id, a branch with a resolvable comparison base, or two commits. For
  standalone input use human-specified specifications or `docs/spec/`.
- Resolve branch base by explicit comparison target, pull-request target, then merge-base with the
  unique default branch. Ask before review if none is unique.
- Severity and action are independent. Every fixable finding has a failing oracle; a human-judgment
  finding explains why no oracle exists. State is only `open` or `closed`.
- Admit serious regressions introduced by fixes. Keep unrelated minor observations outside the
  current verdict for the terminal report.
- A specification change is semantically judged. Follow a new Git version when no consequential
  decision changed; append resumable `findings_stale` only when one did.

## Completion

Perform one initial full review, targeted re-reviews until admitted findings close, then one final
full review in a fresh context. Findings from that final pass close through targeted review; never
repeat the final full pass. Review is complete only when it performed the final full pass and all
admitted findings are closed.
