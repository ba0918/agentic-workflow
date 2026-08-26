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
- how its completion is shown (one of the four completion kinds below) and what exactly is
  checked;
- choices delegated to implementation, if any;
- stop conditions.

## The two machine-read parts

Only two parts of a plan are read in a fixed form, by `scripts/plan_artifact.py`. The helper
refuses to save or publish a plan in which either is unreadable, so a malformed one never
reaches the human for approval.

| Part | Form | Read for |
|---|---|---|
| Target specifications | `**Target specifications:**` followed by one list item per specification (form below) | verifying the specification has not changed |
| Change scope | `## Scope` containing one `text` code block holding a file tree | refusing edits outside the scope |

These two are fixed because **both are compared against something outside the document**: the
identity against the file now in the repository, the scope against the paths a commit touches.
A machine that cannot read them cannot do its job.

Everything else is prose. The steps, how each is shown complete, the decisions reserved for a
human, and the plan's own id and revision are written for a person; the agent that later runs
the plan reads them and declares what it found. Nothing refuses a plan over their wording — when
a wording cannot be read, the agent that reads it is the one who can fix it, and stopping helps
no one. A correction that changes meaning goes back to this skill instead.

Write these parts anyway, in the forms below. They are what makes a plan legible, and the shapes
are what the implement skill's declarations expect. They are conventions for the writer, not
gates the helper enforces.

The markers (headings and bold labels) are fixed English words regardless of the human's
language; the prose around them, and the section names they cite, are written in the human's
language. Explanatory text may follow a marker on the next lines.

### Plan id and revision

At the top, on their own lines:

```markdown
**Plan ID:** `20260826170000`
**Plan revision:** `1`
```

The id is 14 digits and never changes across revisions; the revision counts up from 1. A person
reads them here, and so does the agent that binds an execution — it passes them to the implement
skill as its own declaration. No machine matches them against anything, so they are worth
getting right: nothing else will notice if they are wrong.

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
let the reader trace which part of the specification the plan rests on, and they are the names a
human gate cites. Add a sentence after the list saying what each specification obliges the plan
to do — a path alone is not an explanation.

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
or box-drawing characters. A block that departs from this stops the helper when the draft is
saved.

### Steps

`## Steps` holds the steps, written as `### 1.`, `### 2.` and so on. Nothing counts them, so
the numbering is for the reader; keep it in order and without gaps so a person can follow it and
so a later revision can be matched against this one step by step.

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
the step's prose does not run. Declaring commands and declaring `check` go together: an execution
bound with commands on a step of another kind, or with a `check` step that names none, is refused
when it is bound — not when the plan is saved.

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
appear under `**Target specifications:**` — the bare name, without the backquotes. Check that
correspondence while writing: nothing checks it for you, and a name that matches no heading
leaves the reader unable to find what the decision rests on. A `files` target contains a
non-empty set of safe repository-relative paths. An `event` target uses `content_identity` with
an immutable `sha256:` identity instead of `paths`. `timing` is exactly `before_edit`, `before_commit`, or
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

Before confirmation, do not create or modify a canonical plan, a status file, or a session
history. The only file the draft may touch is its own temporary copy below.

Save the draft bytes, unchanged and without any header or front matter marking them as a draft,
with:

```text
python3 skills/ba0918-plan/scripts/plan_artifact.py draft \
  --repo <repo> --plan-id <plan-id> --revision <n> --slug <lowercase-slug> < draft.md
```

The helper first checks the two machine-read parts and every target specification identity. When
a check fails it writes nothing, prints which part is unreadable or which specification differs
to standard error, and exits non-zero; fix the draft and save again before showing it to the
human. When the checks pass it writes `.agents/tmp/plans/<plan-id>_<slug>_r<n>_draft.md` atomically and
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

1. Run `python3 skills/ba0918-plan/scripts/plan_artifact.py publish` with `--source` set to the
   draft path and `--approved-identity` set to the presented identity. The helper moves the draft
   to the canonical path only when the file still has the presented identity and still passes the
   same checks as at save time (so a specification revised after the draft stops publication),
   then reads the canonical file back and keeps it only when that read-back matches. A draft the
   human edited after presentation fails the identity check and stays in place for the dialogue
   to continue.
2. Read the canonical file back and confirm that its identity is the approved identity and that
   the draft path no longer exists.
3. Stage that one file and commit it. Approving a plan and committing it are one operation: the
   commit is where the approval is recorded, and nothing else records it. Skipping the commit
   leaves a plan nothing can show was approved.

If publication or verification fails, report the exact stage and leave no success claim.

## Completion display

State the plan's purpose in plain language, its stable path, its content identity, and the commit
that carries it. State explicitly that implementation has not started.
