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

## Unfinished plans

The plans sitting in the working tree are the unfinished ones. Nothing lists them elsewhere, and
nothing marks one of them as the plan being worked on.

- Approving a plan and committing it are one operation, so the commit that carries a plan is the
  record of its approval. There is no separate place where approval is written down.
- A plan whose work is finished and merged is removed from the working tree with `git rm`. What
  it said stays readable in the repository's history.
- Never write a `status.md`, a `session-history.md`, or any other file that restates where the
  work stands. How far an implementation got is answered by the evidence the implement skill
  leaves behind.

## Several plans at once

Any number of unfinished plans may sit in the working tree together. Publishing a second one is
not a switch away from the first and needs no confirmation. Which plan gets implemented is
decided when cycle or implement is started, not here.

When a new plan would cover ground an existing one already covers, show the human the existing
plan and ask whether to revise it or write a separate one. Never leave two similar plans side by
side without saying so.

Which implementations are live — the branches and working directories they run in — is answered
by `git worktree list`. This skill reads that and never writes it.
