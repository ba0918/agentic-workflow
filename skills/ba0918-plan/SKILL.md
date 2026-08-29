---
name: ba0918-plan
description: "Workflow station of the ba0918 workflow: turn an approved specification into one Markdown plan that an implementer with no prior context can execute, referencing specification sections instead of copying them, with per-step completion evidence and stop conditions. Use when asked to write or revise a ba0918 plan from a specification. 日本語キーワード: 実装計画 手順書 計画を立てる 仕様から計画"
---

# Plan

Write the implementation plan for one approved specification. The reader is an LLM that knows
nothing of this conversation; it gets the plan path, the repository, and nothing else. Anything
the reader cannot recover from those must be in the plan.

## Inputs and outputs

In: the path of a committed specification (uncommitted means unapproved — stop and say so).
Out: one Markdown file, `docs/plans/<name>.md`, approved by the person and committed. The
implementation branch will carry `<name>`; choose a name that reads well in a branch.

## What a plan is

Written in plain language, one file, no machine-oriented sections. It **references** the
specification by path and section heading and never copies specification text: copies drift,
and the implementer must read the sections anyway. What the plan adds is what only this plan
knows — why this order, why these files, where to stop.

Plan-level content: which specification sections each step verifies; approach and its
rationale; the file scope that may change; step order and prerequisites; choices left to the
implementer; stop conditions.

Per-step content (see `references/step-template.md`): purpose and the specification sections it
rests on; prerequisites; the files it may change; what "done" means and how it is shown (test /
check / artifact / external); choices left open; when to stop and hand back.

## Boundaries

- A choice may be left to the implementer only if every option leaves the approved behavior
  unchanged. New input kinds, acceptance boundaries, and error handling are specification
  decisions: if the specification is silent, do not decide here — hand back to brainstorm.
  "The specification does not say" never means "the implementer decides".
- A human check inside a step is written as an ordinary sentence in that step, and only for an
  irreversible operation, a privileged operation, or a dangerous target. Meaning-changing
  decisions go back to brainstorm; acceptance of the result belongs to the end of the cycle.
- When neither the project's instructions nor the ecosystem's standard tool fixes a test
  command, decide it here — the implementer must not invent one.

## Finishing

1. Self-check against `references/step-template.md`: every step has all fields; every referenced
   heading exists in the specification; no step decides a specification question.
2. Adversarial review by separate-context agents, at least two: one on the plan's own quality,
   one checking it against the specification. Findings that need no decision are fixed
   directly. Findings that need a decision: under the four stop conditions (missing meaning or
   departure from approved content; irreversible, privileged, or dangerous operation; spreading
   accident; no progress after a changed approach) stop and ask the person now; otherwise decide
   yourself and list the decision among step 3's judgment points.
3. Approval: stage only the plan, give the person the path, the command to view the diff, and
   the points needing their judgment. Do not paste the plan, and never let a summary be what
   they approve. The person commits, or tells you
   to. A plan is approved only once committed.

Finished plans are deleted by the main session after the person accepts the result and
merges the branch; the plan stays readable in git history. Do not delete it yourself.
