---
name: ba0918-plan
description: Use when named, committed specifications contain complete product meaning and need one human-readable, independently reviewed implementation plan under docs/plans.
metadata:
  contracts:
    - plan-runtime
---

# Plan

Arrange already-approved meaning into executable order. Never use planning as a second design
phase.

## Load routing

- Read [creation.md](references/creation.md) for input checks, format, review, and approval.
- Read [readability.md](references/readability.md) while writing.
- Read [lifecycle.md](references/lifecycle.md) for revisions or overlapping unfinished plans.

## Boundary

- Accept only specification paths and sections named by the caller or human. Verify they are
  committed and complete enough for one implementation and review unit.
- Own the implementation approach, ordering, dependencies, expected file tree, completion evidence,
  explicitly delegated mechanical choices, and stop conditions within approved meaning.
- Do not choose a missing dependency, persistence model, permission boundary, external service, or
  product behavior. Return missing meaning to brainstorm.
- Write directly to one canonical Markdown file under `docs/plans/`. The path stem is the plan
  key and the approving Git commit is its version. Do not add a manual id, revision, content hash,
  draft, publication receipt, status file, or approval ledger.
- Do not implement, create worktrees, start cycle, update progress, merge, or publish.

## Independent review

Before human approval, use a separate reviewer to compare the complete plan with the named
specifications, repository structure, tests, and project rules. The first review is full. After a
local correction, re-review only unresolved findings, the correction, and affected later steps.
Repeat the full review if structure, assumptions, step order, dependencies, completion conditions,
Scope topology, or referenced specifications change.

Review cannot invent product meaning. A consequential gap returns to brainstorm.

## Approval and completion

After review converges and `scripts/plan_artifact.py` validates the two machine-shaped sections,
stage only the plan. Show its path, the staged diff command, and decisions the human must judge.
Explicit acceptance of those staged bytes authorizes committing them. The commit is the sole
approval record and does not authorize implementation.

Complete after that commit. State that implementation has not started.
