---
name: ba0918-plan
description: Use when an approved specification is ready to be converted into one human-readable implementation plan that the implement skill can execute as written. Rejects missing meaning and does not implement, track progress, or resume work.
metadata:
  contracts:
    - plan-runtime
---

# Plan

Convert one approved, plan-ready change into the exact implementation plan that both the human
and the later implement skill will use. The plan is one Markdown file: written for a human
reader throughout, with a small number of machine-read parts in a fixed form.

## Load routing

- For input checks, draft creation, the plan format, approval, and publication, read
  [creation.md](references/creation.md).
- Read [readability.md](references/readability.md) while composing or checking the draft.
- Read [lifecycle.md](references/lifecycle.md) only when creating a revision, registering an
  open plan, or changing the current plan.
- Do not preload every reference.

## Boundary

- Own plan-readiness rechecking, draft composition, the temporary draft file the human reads,
  human confirmation bound to its content identity, canonical publication, plan revisions that
  do not change product meaning, and open-plan registration.
- Own the plan format. `scripts/plan_artifact.py` is the single reader of the machine-read
  parts (plan id and revision, target specifications, change scope tree, steps with their
  completion kind, human gates). The implement skill reads plans through it and keeps no
  parser of its own.
- Do not infer a specification by scanning content. The caller or human names the approved
  specification set.
- Do not decide missing product meaning or architecture. Return those gaps to brainstorm.
- Do not own status updates, session history, checkboxes, implementation, TDD, evidence
  generation, completion, review, resume, checkpoints, branches, worktrees, commits, or
  parallel execution.
- Never start a later workflow automatically.

## Completion

Complete only after the helper accepted the draft (format and specification identities
verified), the human confirmed the draft file by its content identity, the published bytes match
that identity, the draft file is gone, and the plan is registered without silently replacing
another current plan. Publication does not authorize implementation.
