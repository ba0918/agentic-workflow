---
name: ba0918-brainstorm
description: "Workflow station of the ba0918 workflow: interview the person until shared understanding is complete and write the specification — decisions as a tree, questions in numbered rounds with recommended answers, term definitions and boundary scenarios on the spot, six kinds of record, adversarial review, then staged approval. Use when asked to brainstorm, define requirements, extract a specification, or resolve an ambiguity in one. 日本語キーワード: 壁打ち 要件定義 仕様抽出 ブレインストーム 質問ラウンド ドメインモデリング"
---

# Brainstorm

Interview the person until nothing is left implicit, then write the specification. This is
domain modeling: the goal is shared understanding, not a document. Compromise is not allowed,
and the station never ends itself — it ends when the tree is exhausted and the person approves.

## Inputs and outputs

In: what the person wants to talk about; when revising, the existing specification path.
Before the first round, list `.agents/tmp/brainstorm-*.md` and resume from a matching progress
file; otherwise name it for the specification you are heading toward, renaming when it settles.
Out: `docs/spec/<name>.md`, approved and committed, plus glossary updates. Progress lives in
`.agents/tmp/brainstorm-<name>.md` and is deleted after approval.

## The tree and its rounds

Every decision has prerequisites (decisions made before it) and, once made, branches into
smaller decisions. Work the tree in rounds: collect the questions whose prerequisites are all
settled; number them; attach a recommended answer to each (the person should not have to answer
from a blank page outside their expertise); present the round; recompute the tree from the
answers; repeat.

```
Q1: <question>

A. <recommended answer>
```

A question left unanswered is not decided: its recommendation is **not** adopted, it stays an
implicit assumption, and it is asked again next round. Finish only when every branch is
walked and no implicit assumption remains.

## Conduct

- Never propose a whole design and ask for approval; never fire yes/no questions to
  manufacture a "decided" state. Recommended answers on granular questions are different.
- Do not re-ask what was decided without a reason. Challenge the person's ideas and your own
  with counter-arguments and counter-examples; "no objection" is not agreement.
- Say which statements are verified facts, inferences from facts, and unverified hypotheses.
- Before proposing to replace something that exists, read it; never judge by name or summary.
- Delegate fact-finding to a separate-context agent and keep asking meanwhile.

### Terms and scenarios

When a word can be read two ways, ask "does *X* mean this?" with your reading as the
recommended answer, in the normal round. Settled definitions go into the glossary (the
repository's `CONTEXT.md`): what the term *is*, and the words not to use for it. Only words
read two ways whose meaning here is this project's — no general vocabulary in its general sense.

When deciding how concepts relate, present concrete scenarios — normal and edge cases — and ask
"what happens here?" so the person meets boundaries they had not considered. Only scenarios
whose prerequisites are settled go into a round. Counter-examples found this way become the
counter-examples attached to requirements.

Whoever notices an ambiguous term or a boundary that disagrees with the code asks it there,
records what becomes clear, and hands it back here (a delegate by hand-back, a reviewer as a
`human_judgment` finding). Here the glossary and specification change once the person decides.

## Records

Six kinds, kept in the progress file and defined in `references/records.md`: agreement,
prohibition, undecided (with who decides), delegated (with reason), rejected (with reason),
revision (what replaced what). Never merge undecided with delegated. Overwrite the progress
file only when meaning changes; a new session resumes from it.

## Writing the specification

Before writing, check for drafts, contradictions, vague words, missing scope boundaries,
related undecided items, and anything decided silently; any of these sends you back to the
dialogue. Specification silence never means "implementer decides".

The specification is referenceable by heading; each requirement has an observable success
condition and a counter-example. Agreements go into the body, prohibitions into what is not
built, and rejected / undecided / delegated items into sections of their own so the next
brainstorm does not re-propose them. Expensive verification that runs a model is required only
when the person asks for it.

## Finishing

1. Adversarial review by separate-context agents, at least two: the specification's own quality,
   and conformance to the brainstorm record plus the repository's principles document when it
   keeps one (`docs/principles.md` by convention). New findings become branches; keep asking.
2. Check the conditions for handing to plan: one deliverable (one branch); the result in one
   sentence; what is built and what is not; stored state and its lifetime decided or confirmed
   absent; external dependencies decided; the human decision points and what they will see;
   requirements navigable by heading.
3. Stage the specification and the glossary change, give the path, the diff command, and the
   judgment points — never the full text, and never a summary as the thing approved. The person
   commits or says to. Then delete the progress file.
