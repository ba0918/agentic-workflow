# Plan readability

The canonical plan is a human decision surface, not an LLM-only instruction payload. The
standard is the reader's understanding, not a word count or a template.

## Reader contract

Write every normative section in the current human's language. A reader without project history
must be able to decide what will change and whether it is safe without opening another document.

Stable identifiers, schema fields, code identifiers, commands, and paths may remain in English.
Explain their meaning and effect where they matter; never substitute an identifier or path for an
explanation.

Terms that exist only inside this project (a file name used as a concept, a state name, a
coined label) get their plain meaning stated before the name appears, once per plan. Widely
understood technical terms (git, SHA-256, JSON, worktree) are used as they are; do not attach
dictionary definitions to them.

## Required content

The plan itself explains:

- its stable plan id and revision;
- the approved specification paths, their content identities, the sections relied on, and what
  each specification obliges the plan to do;
- the outcome and why it matters;
- what changes and what explicitly does not;
- external effects, major risks, and human gates;
- each step's purpose, prerequisites, scope, completion kind, and stop condition;
- the evidence that will show each step complete;
- choices delegated to implementation.

Do not split the plan into a friendly summary and a normative layer only an LLM can understand.
Do not make brevity the target: remove unexplained jargon, not necessary meaning.

## Pre-publication check

Before presenting the draft, check that:

- the plan id, revision, and target specification identities are inside the canonical draft,
  not only in surrounding chat or publication metadata;
- every project-internal term and reference has its meaning stated before the name, once;
- every specification reference is accompanied by its practical obligation;
- the non-change boundary is explicit;
- risks state consequences rather than labels alone;
- every step has a completion kind and says what will be checked;
- where the evidence for a claim is missing or uncertain, the plan says so instead of filling
  the gap with a plausible guess;
- no requirement first appears in the plan instead of the approved specification.
