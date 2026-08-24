---
name: ba0918-brainstorm
description: Use when a broad change request or unsettled idea needs human-approved phases, requirements, a specification set or roadmap, and a plan-readiness decision. Does not create plans or implement changes.
metadata:
  contracts:
    - brainstorm-runtime
---

# Brainstorm

Use this as the entry point for build-or-change requests. Settle product meaning through dialogue; never turn a broad request directly into one monolithic plan.

## Load routing

- For session opening, sparring, and scope decomposition, read only [session.md](references/session.md).
- Read [state.md](references/state.md) only when saving, restoring, resolving conflicts, handling compaction, or finalizing a wrap that has progress state.
- Read [wrap-readiness.md](references/wrap-readiness.md) only for wrap or plan-readiness work.
- Do not preload all references. Do not reread unchanged material.

## Boundary

- Own dialogue, semantic state, scope decomposition, the applicable specification set, approval, and plan readiness.
- Do not create or update plans, implement product changes, manage idea lists/archive/drop, or start a cycle.
- During ordinary dialogue, reply in chat and create or edit no files. Only save session progress after the human agrees to a semantic change; during wrap, save the draft as a temporary file the human reads, and write canonical documents only after approval bound to its content identity.
- Promote strategic brainstorms to ROADMAP and implementation brainstorms to the project-specific specification set.
- Write normative ROADMAP, specification, and plan content in the current user's language. Stable machine identifiers may remain English.
- Start a second reviewer at most once, and only when explicitly authorized for the current run by a flag or the user. Never carry or retry that authority.

## Completion

Complete only after the human approves each draft by path and content identity, the canonical write succeeds with matching read-back and no draft left behind, and plan readiness is evaluated. If readiness is incomplete, return the missing items and continue brainstorming; do not hand off to planning as a success. If the canonical write fails, preserve progress, report the failure, and remain incomplete.
