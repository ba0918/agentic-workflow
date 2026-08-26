# Wrap and plan readiness

Before writing, review the complete semantic state for contradictions, placeholders, ambiguous
boundaries, silently inferred decisions, and incomplete verification. Explicitly cover persistence
and lifetime, ownership and concurrency, permissions, external systems, new dependencies, failure
and recovery, migration, operations, and release when the requirement makes them relevant.

Write strategy to `ROADMAP.md`, implementation behavior to `docs/spec/`, and rejected or
unresolved decision history to `docs/agreements/`. Use `scripts/draft.py` only as the safe
atomic writer to these canonical paths; it is not a draft or publish workflow.

Run the mandatory independent architecture review described by the skill. After it converges,
stage the canonical files and ask for approval of the staged diff. On approval, commit those bytes
and remove temporary state.

A result is ready for plan only when it is one implementation and review unit, states observable
value and exclusions, has decided or ruled out distribution, runtime, persistence, external I/O,
permissions, and new dependencies, names human boundaries and verification, lists affected skills
or code, and leaves no foundational design decision unresolved.
