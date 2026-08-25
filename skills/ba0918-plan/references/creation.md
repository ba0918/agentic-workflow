# Plan creation

## Input gate

Require all of the following before drafting:

- one implementation and verification unit;
- the explicitly named approved specification paths, their current content identities
  (`sha256:` of the file bytes), and the sections the plan relies on;
- an observable success condition, counterexample or known failure, verification method, and
  any human gate the specification requires;
- decided distribution, execution, persistence, lifetime, and external I/O boundaries;
- no blocking undecided item or unknown dependency.

If any item is missing, do not write a draft file. Explain the missing meaning and its impact in
the human's language, then return it to brainstorm.

## Draft

Write one canonical draft in the human's language. Follow [readability.md](readability.md).
Every implementation step identifies:

- its purpose and the specification sections it rests on;
- prerequisites and judgment dependencies;
- the files it may change (a subset of the plan's change scope);
- how its completion is shown (one of the three completion kinds below) and what exactly is
  checked;
- choices delegated to implementation, if any;
- stop conditions.

## Machine-read parts

The implement skill reads the plan through `scripts/plan_artifact.py`. The helper refuses to
save or publish a plan in which any of these parts is unreadable, so a malformed plan never
reaches the human for approval. Everything outside these parts is free prose.

The markers (headings and bold labels) are fixed English words regardless of the human's
language; the prose around them, and the section names they cite, are written in the human's
language. Explanatory text may follow a marker on the next lines.

| Part | Form | Read for |
|---|---|---|
| Plan id and revision | At the top: `**Plan ID:** \`<14 digits>\`` and `**Plan revision:** \`<n>\`` on their own lines; they must equal the `--plan-id` and `--revision` given to the helper | binding evidence to a plan |
| Target specifications | `**Target specifications:**` followed by one list item per specification (form below) | verifying the specification has not changed |
| Change scope | `## Scope` containing one `text` code block holding a file tree | refusing edits outside the scope |
| Steps | `## Steps` containing `### 1.`, `### 2.` … counted from 1 without gaps | executing one step at a time |
| Completion kind | exactly one `**Completion:**` line per step naming one of the four kinds, plus a `**Checks:**` declaration when that kind is `check` | demanding the matching evidence |
| Human gates | `**Human gates:**` plus a JSON block inside the step that needs one | pausing for a human decision |

### Target specifications

```markdown
**Target specifications:**

- `docs/features/greeting.md`
  - content identity: `sha256:0123…abcd`
  - sections: `残っている作業があるとき`, `証拠の残し方`
```

The path is repository-relative. The identity is the `sha256:` content identity of the file as
it is now; the helper compares it against the file in the repository when saving and when
publishing, and stops when they differ or the file is missing. Section names are the headings
of the specification in the human's language, each in backquotes and separated by commas; they
are for the human reader and also define the names a human gate may cite. Add a
sentence after the list saying what each specification obliges the plan to do — a path alone is
not an explanation.

### Change scope

````markdown
## Scope

```text
skills/ba0918-implement/
  SKILL.md
  references/
    execution.md
```
````

Indentation expresses nesting (any consistent width), directories end with `/`, paths are
repository-relative, and the block holds nothing but path segments — no comments, annotations,
or box-drawing characters.

### Completion kind

Each step states how its completion will be shown. Choose by **who can judge it**, not by what the
step produces:

| Line | Use for | Evidence the implement skill demands |
|---|---|---|
| `**Completion:** test` | code that maps fixed inputs to fixed outputs | a failing test written first, then passing |
| `**Completion:** check` | generated copies, anything a named command can judge | every command the step declares succeeds |
| `**Completion:** artifact` | prose a person reads to decide whether it is right, configuration files | the file exists with the agreed content, passes its format check, and the human reads it and approves |
| `**Completion:** external` | checks on a running system; measurement the human explicitly asked for | the human sees the result and approves |

A named command can judge it → `test` when a failing test can be written first, otherwise `check`.
Only a person reading it can decide → `artifact` or `external`.

A `check` step declares its commands in the same step, one per line, each command in backquotes:

````markdown
**Completion:** check

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
````

The implement skill runs exactly these, in this order, and nothing else; a command written only in
the step's prose does not run. A `check` step with no declaration, and a step of another kind that
carries one, are both refused when the plan is saved.

**Never make a document a `check` step.** Specifications, skill prose, plans, and anything else a
person reads to decide whether it is right are `artifact`, even when a format check exists for
them. Naming one command to skip the reading is exactly the ritual approval this workflow exists
to remove — in the other direction. No command decides this line; the plan does, when it is
written.

Do not add a measurement step (running an LLM to observe behaviour) unless the human asked for
it by name.

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
      "sections": ["残っている作業があるとき"],
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

Each `gate_id` is unique within the plan. `sections` is a non-empty list of section names that
appear under `**Target specifications:**` — the bare name, without the backquotes; the helper rejects any
name that is not listed there. A `files` target contains a non-empty set of safe
repository-relative paths. An `event` target uses `content_identity` with an immutable
`sha256:` identity instead of `paths`. `timing` is exactly `before_edit`, `before_commit`, or
`before_implementation_green`; `allowed_results` is exactly `["approved", "rejected"]`.

Omit the declaration when no human gate is required. A choice that changes product meaning is
not a human gate: return it to brainstorm instead of encoding alternatives in the plan. The
human reading that `artifact` and `external` steps already require is part of those
completion kinds; do not declare a gate for it again.

Delegated choices may vary implementation mechanics only when every allowed choice preserves the
same approved observable behavior. Do not introduce a new input class, acceptance boundary,
error case, tolerance, or verification example that the approved specification does not decide.
Return such a choice to brainstorm instead of placing it in the plan.

## Saving the draft

Before confirmation, do not create or modify a canonical plan, the open-plan index, a status
file, or a session history. The only file the draft may touch is its own temporary copy below.

Save the draft bytes, unchanged and without any header or front matter marking them as a draft,
with:

```text
python3 skills/ba0918-plan/scripts/plan_artifact.py draft \
  --repo <repo> --plan-id <plan-id> --revision <n> --slug <lowercase-slug> < draft.md
```

The helper first checks every machine-read part and every target specification identity. When a
check fails it writes nothing, prints which part is unreadable or which specification differs to
standard error, and exits non-zero; fix the draft and save again before showing it to the human.
When the checks pass it writes `.agents/tmp/plans/<plan-id>_<slug>_r<n>_draft.md` atomically and
prints the path and the SHA-256 content identity of exactly those bytes. When a draft with that
name already exists (for example after a resumed session), pass
`--replace-identity <identity-of-the-existing-file>`; the helper refuses to overwrite a draft
whose identity was not named.

Present in chat only: the draft path, its content identity, the canonical destination, and the
points the human should judge. Do not copy the draft text into chat, and do not offer a summary
as the approval target; the human reads the file with their own viewer.

## Human gate and publication

Ask whether the draft at that path, with that identity, may become canonical at the stated
destination. Silence and a request to continue discussing are not confirmation. When the human
wants a change, revise the draft in dialogue and save a new draft; never ask them to edit the
file.

After explicit confirmation:

1. Determine whether an open plan is already current.
2. If another plan is current, load [lifecycle.md](lifecycle.md) and obtain the required switch
   decision before publication.
3. Run `python3 skills/ba0918-plan/scripts/plan_artifact.py publish` with `--source` set to the
   draft path, `--approved-identity` set to the presented identity, and `--switch-confirmed` when
   the human confirmed a switch. The helper moves the draft to the canonical path only when the file still has the
   presented identity and still passes the same checks as at save time (so a specification
   revised after the draft stops publication), reads the canonical file back, and registers it
   only when that read-back matches. A draft the human edited after presentation fails the
   identity check and stays in place for the dialogue to continue.
4. Read the canonical file and locator back, and confirm that the canonical identity is the
   approved identity and that the draft path no longer exists.

If publication or verification fails, report the exact stage and leave no success claim.

## Completion display

State the plan's purpose in plain language, its stable path, content identity, and whether it is
current or held. State explicitly that implementation has not started.
