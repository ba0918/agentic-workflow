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
- Read [lifecycle.md](references/lifecycle.md) only when creating a revision, or when another
  unfinished plan already sits in the working tree.
- Do not preload every reference.

## Boundary

- Own plan-readiness rechecking, draft composition, the temporary draft file the human reads,
  human confirmation bound to its content identity, canonical publication, and plan revisions
  that do not change product meaning.
- Own the plan format. `scripts/plan_artifact.py` is the single reader of the two parts a
  machine reads in a fixed form: the specifications the plan stands on, and the files it may
  change. The implement skill reads plans through it and keeps no parser of its own.
- Everything else in a plan is prose: the steps, how each one is shown complete, the decisions
  reserved for a human, and the plan's own id and revision. The agent that reads the plan
  declares them when it binds an execution. Nothing checks their wording.
- Do not infer a specification by scanning content. The caller or human names the approved
  specification set.
- Do not decide missing product meaning or architecture. Return those gaps to brainstorm.
- Do not own status updates, session history, checkboxes, implementation, TDD, evidence
  generation, completion, review, resume, checkpoints, branches, worktrees, implementation
  commits, or parallel execution. The one commit this skill makes is the plan's own approval.
- Never start a later workflow automatically.

## Completion

Complete only after the helper accepted the draft (the two machine-read parts and the
specification identities verified), the human confirmed the draft file by its content identity,
the published bytes match that identity, the draft file is gone, and the plan is committed.
Approving a plan and committing it are one operation: the commit that carries it is the record
of its approval. Publication does not authorize implementation.
