# Plan creation

## Input gate

Require all of the following before drafting:

- one implementation and verification unit;
- the explicitly named approved specification paths, revisions or content identities, and
  applicable clauses;
- an observable success condition, counterexample or known failure, verification method, and
  any human gate for every applicable clause;
- decided distribution, execution, persistence, lifetime, external I/O, and source-audit
  boundaries;
- no blocking undecided item or unknown dependency.

If any item is missing, do not write a draft file. Explain the missing meaning and its impact in
the human's language, then return it to brainstorm.

## Draft

Write one canonical draft in the human's language. Follow [readability.md](readability.md).
Every implementation step identifies:

- applicable specification clauses and verification contracts;
- prerequisites and judgment dependencies;
- expected artifacts and allowed write scope;
- required evidence and delegated implementation choices;
- stop conditions.

Delegated choices may vary implementation mechanics only when every allowed choice preserves the
same approved observable behavior. Do not introduce a new input class, acceptance boundary,
error case, tolerance, or verification example that the approved specification and verification
contract do not decide. Return such a choice to brainstorm instead of placing it in the plan.

Keep the draft only in the conversation until the human confirms it. Before confirmation, do
not create or modify any file for the draft—not a canonical plan, scratch file, hidden file,
index, status, or session history. A non-canonical filename does not make a pre-confirmation
write acceptable.

Present the complete draft in chat. A summary is not the approval target. Compute and present a
SHA-256 content identity over the exact UTF-8 draft bytes without writing a canonical plan or
open-plan entry. Send the bytes directly from the conversation-held draft to
`python3 skills/ba0918-plan/scripts/plan_artifact.py identity` on standard input; do not stage
them in a file first.

## Human gate and publication

Ask whether the displayed draft and destination may become canonical. Silence and a request to
continue discussing are not confirmation.

After explicit confirmation:

1. Only now, write the exact confirmed bytes to a temporary file under `.agents/tmp/`.
2. Determine whether an open plan is already current and whether the worktree is dirty.
3. If another plan is current, load [lifecycle.md](lifecycle.md) and obtain the required switch
   decision before publication.
4. Run `python3 skills/ba0918-plan/scripts/plan_artifact.py publish` with the approved identity
   and the observed switch inputs.
5. Read the canonical file and locator back, and confirm that the canonical identity is the
   approved identity.
6. Remove the temporary file only after successful verification.

If publication or verification fails, report the exact stage and leave no success claim.

## Completion display

State the plan's purpose in plain language, its stable path, content identity, and whether it is
current or held. State explicitly that implementation has not started.
