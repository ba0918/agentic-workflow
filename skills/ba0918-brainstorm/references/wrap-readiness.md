# Wrap and plan readiness

Before writing, review the complete semantic state for contradictions, placeholders, ambiguous
boundaries, silently inferred decisions, and incomplete verification. Explicitly cover persistence
and lifetime, ownership and concurrency, permissions, external systems, new dependencies, failure
and recovery, migration, operations, and release when the requirement makes them relevant.

Group implementation requirements under uniquely addressable Markdown headings at a granularity
that lets a later plan map each requirement to verification. State the observable success, at least
one counterexample or failure boundary, and how a later plan can judge it. When execution cannot
decide the result, name the bounded human criterion instead of pretending that a command proves it.

Write strategy to `ROADMAP.md`, implementation behavior to `docs/spec/`, and rejected or
unresolved decision history to `docs/agreements/`. Use `scripts/draft.py` only as the safe
atomic writer to these canonical paths; it is not a draft or publish workflow.
The writer accepts only repository-root `ROADMAP.md`, `docs/spec/**/*.md`, and direct
`docs/agreements/*.md` files. It rejects source, configuration, `.git`, and every other path.

Run the mandatory independent architecture review described by the skill. After it converges,
stage the canonical files and ask for approval of the staged diff. On approval, commit those bytes
and remove temporary state.

A result is ready for plan only when it is one implementation and review unit, states observable
value, counterexamples, exclusions, and a verification or human criterion under uniquely
addressable headings of practical scope; has decided or ruled out distribution, runtime,
persistence, external I/O, permissions, and new dependencies; lists affected skills or code; and
leaves no foundational design decision unresolved.
