# Step template

Each step in the plan carries these fields, in prose or as a short list. The order below is
the order an implementer needs them.

```markdown
## Step N — <what this step produces>

Purpose: <one sentence>. Specification: [<heading>](<path>#<anchor>), [<heading>](<path>#<anchor>).
Prerequisites: <steps that must be complete; environment or data that must exist>.
May change: <files or directories; nothing outside this scope>.
Done when: <observable condition>.
Shown by: test | check | artifact | external — <test names / commands / artifact path / what to
observe and where>.
Left to the implementer: <choices where every option keeps approved behavior> (or "none").
Stop and hand back if: <conditions specific to this step, beyond the general ones> (or "none").
```

Guidance per field:

- **Specification** links headings, not paraphrases, in any of the plan's specifications. When the
  step needs a judgment no heading makes, write it as a provisional answer in the plan (see
  **Approach and why** below) and link the headings it rests on.
- **Done when** is a condition someone else can observe, not "the feature works".
- **Shown by** picks exactly one kind. *Test* means RED → GREEN → REFACTOR with named tests.
  *Check* lists commands in order. *Artifact* names the file and any format check. *External*
  says what to observe, on what, and what counts as pass; if it is unsafe, privileged, or
  irreversible, say that a human runs or confirms it. Name only tests that meet the Evidence
  conditions in the ba0918-review skill's `references/oracle-evidence.md`. Do not add tests for
  conditions already true or match their count to the number of Done conditions; use one test per
  behavior being implemented. If no test qualifies and the specification does not require human
  or platform inspection, hand back to brainstorm — never a provisional answer: an oracle counts
  only when the specification declares what it enforces, and a plan cannot declare that.
- **Left to the implementer** holds choices delegated for this step; plan-wide ones go in the
  plan-level section. Naming, internal
  structure, and helper extraction usually qualify; input formats, limits, error behavior, and
  persistence never do.
- **Stop and hand back if** names conditions the implementer could not infer. The general ones
  (SKILL.md's Boundaries) need not be repeated; a step condition is one of them made concrete — a
  dependency that may have to be installed, a measurement that may contradict the specification.

Plan-level sections that precede the steps: **Goal** (one sentence, the result the person
gets), **Specification** (each specification the steps rest on, as a link), **Approach and
why** (including the provisional answers the plan chose where the specification is silent, each
with its overturn condition), **Scope of change**, **Step order and prerequisites**, **Verification map** (which steps
prove which specification sections), **Left to the implementer**, **Stop conditions**, **Test
command** (only when the project does not fix one), **Out of scope**.
