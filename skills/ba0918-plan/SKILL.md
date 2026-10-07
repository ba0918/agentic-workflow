---
name: ba0918-plan
description: "Workflow station of the ba0918 workflow that turns approved specifications (one or several) into one Markdown plan an implementer with no prior context can execute. Use when asked to write or revise a ba0918 plan from specifications. 日本語キーワード: 実装計画 手順書 計画を立てる 仕様から計画"
---

# Plan

Write the implementation plan for approved specifications. The reader is an LLM that knows
nothing of this conversation; it gets the plan path, the repository, and nothing else. Anything
the reader cannot recover from those must be in the plan.

## Inputs and outputs

In: the paths of committed specifications, one or several (uncommitted means unapproved — stop
and say so). Never traverse from an index. You may read the specifications they link to, one link
deep; list every one a step rests on in the plan, linked ones included.
Out: one Markdown file, `docs/plans/<name>.md`, approved by the person and committed. The
implementation branch will carry `<name>`; choose a name that reads well in a branch.

## What a plan is

Written in plain language, one file, no machine-oriented sections. It **references** the
specifications by Markdown link and section heading and never copies specification text: copies
drift, and the implementer must read the sections anyway. What the plan adds is what only this
plan knows — why this order, why these files, where to stop.

The plan-level sections and the fields every step carries are in `references/step-template.md`;
read it before writing.

## Boundaries

- A choice may be left to the implementer only if every option leaves the approved behavior
  unchanged. When a step needs a judgment the specification does not make — a new input kind, an
  acceptance boundary, error handling — write the answer with the strongest grounds into the plan
  as a provisional answer, and put it with its overturn condition (what the person would say to
  overturn it) among step 3's judgment points: the person sees them at approval anyway, so do not
  send them back to brainstorm and wait. Deciding one silently, off the judgment points, is a
  counter-example.
- A human check inside a step is written as an ordinary sentence in that step, and only for an
  irreversible operation, a privileged operation, or a dangerous target. A judgment the plan does
  not settle is the implementer's to take as a provisional answer; it hands back upstream only for
  the reasons of the ba0918-cycle skill's ending 4. Acceptance of the result belongs to the end of
  the cycle.
- When neither the project's instructions nor the ecosystem's standard tool fixes a test
  command, decide it here — the implementer must not invent one.

## Finishing

1. Self-check against `references/step-template.md`: every step has all fields; every referenced
   heading exists in its specification; every judgment the specification does not make is a
   provisional answer listed among the judgment points.
2. Adversarial review, only when the plan's own decisions can contradict each other — steps that
   depend on one another, or one specification heading driving several steps. Say that reason,
   then launch one separate-context agent on the plan's own quality, and a second against the
   specification only when the match is one no check can make. A plan whose steps stand alone
   gets none. Fix every finding, including those that need a decision; do not ask the person about
   them. Put each decision taken, with its overturn condition, among step 3's judgment points. Only
   a finding whose fix would contradict the approved specification is not fixed in the plan: hand
   it back to brainstorm.
3. Approval: stage only the plan, give the person the path, the command to view the diff, and
   the points needing their judgment, the provisional answers among them. Do not paste the plan,
   and never let a summary be what they approve. The person commits, or tells you to. A plan is
   approved only once committed.

Finished plans are deleted by the main session after the person accepts the result and
merges the branch; the plan stays readable in git history. Do not delete it yourself.
