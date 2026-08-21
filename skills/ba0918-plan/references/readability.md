# Plan readability

The canonical plan is a human decision surface, not an LLM-only instruction payload.

## Reader contract

Write every normative section in the current human's language. A reader without project history
must be able to decide what will change and whether it is safe without opening another document.

Stable identifiers, schema fields, code identifiers, commands, and paths may remain in English.
Explain their meaning and effect where they matter; never substitute an identifier or path for an
explanation.

## Required content

The plan itself explains:

- its stable plan ID and revision;
- the approved specification paths, revisions or content identities, and applicable clauses;
- the outcome and why it matters;
- what changes and what explicitly does not;
- external effects, major risks, and human gates;
- each step's purpose, prerequisites, scope, and stop condition;
- the evidence that will prove each step complete;
- choices delegated to implementation.

Do not split the plan into a friendly summary and a normative layer only an LLM can understand.
Do not make brevity the target: remove unexplained jargon, not necessary meaning.

## Pre-publication check

Before presenting the draft, check that:

- the plan ID, revision, and approved specification identifiers are inside the canonical draft,
  not only in surrounding chat or publication metadata;
- every technical term is explained at first use;
- every specification reference is accompanied by its practical obligation;
- the non-change boundary is explicit;
- risks state consequences rather than labels alone;
- every step has observable completion evidence;
- no requirement first appears in the plan instead of the approved specification.
