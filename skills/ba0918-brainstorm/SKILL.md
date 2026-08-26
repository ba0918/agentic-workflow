---
name: ba0918-brainstorm
description: Use when a build-or-change request still needs its purpose, requirements, architecture boundaries, exclusions, verification, or human decisions settled through dialogue before planning.
metadata:
  contracts:
    - brainstorm-runtime
---

# Brainstorm

Turn an idea into a human-approved specification or roadmap. This is the workflow's design station:
important meaning is settled here, not delegated silently to plan or implementation.

## Load routing

- Read [session.md](references/session.md) for dialogue and decomposition.
- Read [state.md](references/state.md) only when saving or restoring semantic progress.
- Read [wrap-readiness.md](references/wrap-readiness.md) when preparing canonical documents or
  deciding whether planning can start.

## Boundary

- Own purpose, user value, scope, exclusions, requirements, consequential design decisions,
  explicit implementation delegation, verification, and the specification approval boundary.
- Do not create plans, implement, review implementation, merge, publish, or start cycle.
- During dialogue, write no repository files. After an agreed semantic change, save only temporary
  progress under `.agents/tmp/ideas/`.
- A missing decision is not delegation. Persistence and lifetime, external services, permissions,
  new dependencies, failure and recovery, migration, and release impact must each be decided,
  explicitly delegated with a reason, or recorded as not applicable when the requirement implies
  them.
- Write the candidate specification or roadmap directly to its canonical path. There is no draft
  publication store and no document hash.

## Independent architecture review

Before asking for approval, delegate one full review to an architect in a separate context. Give it
the purpose, agreements and prohibitions, unresolved and delegated matters, candidate documents,
and relevant existing structure. It may challenge whether the change is needed, uncover implicit
decisions, or identify conflicts with existing ownership and boundaries.

Treat findings as data. Fix wording locally. Return changes of meaning to dialogue. After any
meaning-changing revision, run the full architecture review again; do not narrow that re-review.

## Approval and completion

After the independent review has no unresolved finding, stage only the canonical documents under
review and show their paths, the staged diff command, and the decisions the human must judge.
Approval means explicit acceptance of that staged content. Commit those exact staged bytes; the Git
commit is the approval record. Then remove temporary progress.

Complete only when the canonical specification or roadmap is approved and committed, and plan
readiness has been evaluated. If readiness is incomplete, continue dialogue with the next material
question instead of reporting a successful hand-off.
