---
name: ba0918-plan
description: Use when approved specifications and verification contracts are ready to be converted into one human-readable implementation plan. Rejects missing meaning and does not implement, track progress, or resume work.
---

# Plan

Convert one approved, plan-ready change into the exact implementation plan that both the human
and the later runner will use.

## Load routing

- For input checks, draft creation, approval, and publication, read
  [creation.md](references/creation.md).
- Read [readability.md](references/readability.md) while composing or checking the draft.
- Read [lifecycle.md](references/lifecycle.md) only when creating a revision, registering an
  open plan, or changing the current plan.
- Do not preload every reference.

## Boundary

- Own plan-readiness rechecking, draft composition, the temporary draft file the human reads,
  human confirmation bound to its content identity, canonical publication, plan revisions that
  do not change product meaning, and open-plan registration.
- Do not infer a specification by scanning content. The caller or human names the approved
  specification set and its revisions.
- Do not decide missing product meaning or architecture. Return those gaps to brainstorm.
- Do not own status updates, session history, checkboxes, implementation, TDD, evidence
  generation, completion, review, resume, checkpoints, branches, worktrees, commits, or
  parallel execution.
- Never start a later workflow automatically.

## Completion

Complete only after the human confirms the draft file by its content identity, the published
bytes match that identity, the draft file is gone, and the plan is registered without silently
replacing another current plan. Publication does not authorize implementation.
