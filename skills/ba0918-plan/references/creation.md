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

Before confirmation, do not create or modify a canonical plan, the open-plan index, a status
file, or a session history. The only file the draft may touch is its own temporary copy below.

Save the draft bytes, unchanged and without any header or front matter marking them as a draft,
with:

```text
python3 skills/ba0918-plan/scripts/plan_artifact.py draft \
  --repo <repo> --plan-id <plan-id> --revision <n> --slug <lowercase-slug> < draft.md
```

It writes `.agents/tmp/plans/<plan-id>_<slug>_r<n>_draft.md` atomically and prints the path and
the SHA-256 content identity of exactly those bytes. When a draft with that name already exists
(for example after a resumed session), pass `--replace-identity <identity-of-the-existing-file>`;
the helper refuses to overwrite a draft whose identity was not named.

Present in chat only: the draft path, its content identity, the canonical destination, and the
points the human should judge. Do not copy the draft text into chat, and do not offer a summary
as the approval target; the human reads the file with their own viewer.

## Human gate and publication

Ask whether the draft at that path, with that identity, may become canonical at the stated
destination. Silence and a request to continue discussing are not confirmation. When the human
wants a change, revise the draft in dialogue and save a new draft; never ask them to edit the
file.

After explicit confirmation:

1. Determine whether an open plan is already current and whether the worktree is dirty.
2. If another plan is current, load [lifecycle.md](lifecycle.md) and obtain the required switch
   decision before publication.
3. Run `python3 skills/ba0918-plan/scripts/plan_artifact.py publish` with `--source` set to the
   draft path, `--approved-identity` set to the presented identity, and the observed switch
   inputs. The helper moves the draft to the canonical path only when the file still has the
   presented identity, reads the canonical file back, and registers it only when that read-back
   matches. A draft the human edited after presentation fails the identity check and stays in
   place for the dialogue to continue.
4. Read the canonical file and locator back, and confirm that the canonical identity is the
   approved identity and that the draft path no longer exists.

If publication or verification fails, report the exact stage and leave no success claim.

## Completion display

State the plan's purpose in plain language, its stable path, content identity, and whether it is
current or held. State explicitly that implementation has not started.
