# Step template

Each step in the plan carries these fields, in prose or as a short list. The order below is
the order an implementer needs them.

```markdown
## Step N — <what this step produces>

Purpose: <one sentence>. Specification: <path>#<heading>, <path>#<heading>.
Prerequisites: <steps that must be complete; environment or data that must exist>.
May change: <files or directories; nothing outside this scope>.
Done when: <observable condition>.
Shown by: test | check | artifact | external — <test names / commands / artifact path / what to
observe and where>.
Left to the implementer: <choices where every option keeps approved behavior> (or "none").
Stop and hand back if: <conditions specific to this step, beyond the four general ones>.
```

Guidance per field:

- **Specification** names headings, not paraphrases. If a heading you need does not exist, the
  specification is missing something — hand back to brainstorm rather than inventing the content.
- **Done when** is a condition someone else can observe, not "the feature works".
- **Shown by** picks exactly one kind. *Test* means RED → GREEN → REFACTOR with named tests.
  *Check* lists commands in order. *Artifact* names the file and any format check. *External*
  says what to observe, on what, and what counts as pass; if it is unsafe, privileged, or
  irreversible, say that a human runs or confirms it. Name only tests that meet **Evidence
  conditions**. Do not add tests for conditions already true or match their count to the
  number of Done conditions; use one test per behavior being implemented. If no test qualifies
  and the specification does not require human or platform inspection, hand back to brainstorm.
- **Left to the implementer** holds choices delegated for this step; plan-wide ones go in the
  plan-level section. Naming, internal
  structure, and helper extraction usually qualify; input formats, limits, error behavior, and
  persistence never do.
- **Stop and hand back if** names conditions the implementer could not infer: a dependency that
  may be unavailable, a measurement that may disagree with the specification, an interface that
  may already exist under another name.

Plan-level sections that precede the steps: **Goal** (one sentence, the result the person
gets), **Specification** (the one governing path), **Approach and why**, **Scope of change**,
**Step order and prerequisites**, **Verification map** (which steps prove which specification
sections), **Left to the implementer**, **Stop conditions**, **Test command** (only when the
project does not fix one), **Out of scope**.
