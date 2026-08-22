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

### Planned human gates

When a step requires a human judgment already defined by the approved specification, place the
following exact marker and versioned JSON object inside that step:

````markdown
**Human gates:**

```json
{
  "version": 1,
  "gates": [
    {
      "gate_id": "unique-gate-id",
      "clauses": ["SPEC-001"],
      "criterion": "one approved yes-or-no judgment",
      "target": {
        "kind": "files",
        "paths": ["repo/relative/path"]
      },
      "timing": "before_edit",
      "allowed_results": ["approved", "rejected"]
    }
  ]
}
```
````

Each `gate_id` is unique within the Plan. `clauses` are a non-empty subset of that step's
applicable specification clauses. A `files` target contains a non-empty set of safe
repository-relative paths. An `event` target uses `content_identity` with an immutable
`sha256:` identity instead of `paths`. `timing` is exactly `before_edit`, `before_commit`, or
`before_implementation_green`; `allowed_results` is exactly `["approved", "rejected"]`.

Omit the declaration when no human gate is required. A choice that changes product meaning is
not a human gate: return it to brainstorm instead of encoding alternatives in the Plan.

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
