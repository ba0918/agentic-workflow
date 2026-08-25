# Plan lifecycle

## Revisions

Never edit a published plan revision in place. Progress does not change plan bytes.

When a requested change alters product meaning, a prohibition, an allowed difference, or an
unapproved architectural choice, stop and return to brainstorm. When it only corrects execution
steps within the approved meaning (for example a machine-read part the helper could not read),
create a new plan revision at a new stable path, present the full revision, and require the
normal human gate. Later consumers treat evidence bound to the old identity as stale.

When a target specification is revised, every plan citing its old identity is stale: the helper
refuses to publish such a plan, and a new revision must cite the new identity.

## Open-plan locator

The locator is a rebuildable internal index, not completion state. It contains only:

- plan ID;
- stable path;
- revision and content identity;
- `current` or `held`.

It never contains workflow phase, completion, evidence, findings, or a copied summary. Do not
create or update `status.md` or `session-history.md`.

## Changing the current plan

Ordinary execution has at most one current plan, while any number of unfinished plans may be
held. If another current plan exists, show both plans' purposes and explain that the old plan will
remain unfinished as held. Require explicit human confirmation; never infer abandonment or
completion, including in headless execution.

A switch rewrites only the locator; it never touches the worktree. Uncommitted changes in the
worktree are therefore neither a reason to switch nor a reason to refuse one. How they are treated
belongs to the implement and recovery workflows, which stop on uncommitted changes inside a plan's
write scope and show the human the rest.

If the locator is malformed, points at different bytes, or contains inconsistent current entries,
fail closed. Do not repair meaning by choosing a plan automatically.
