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

When a requirement does not change observable product behavior (release automation, licensing,
CI), ask whether it belongs here, in a separate specification, or is not built. Never add it silently.

Whoever notices an ambiguous term or a boundary that disagrees with the code asks it there, records
what becomes clear, and hands it back here. Change the glossary and specification after the decision.

## Records

Six kinds, kept in the progress file and defined in `references/records.md`: agreement, prohibition,
undecided (with who decides), delegated (with reason), rejected (with reason), revision (what replaced
what). Never merge undecided with delegated. Overwrite only when meaning changes; resume from it.

## Writing the specification

Before writing, check for drafts, contradictions, vague words, missing scope boundaries,
related undecided items, and anything decided silently; any of these sends you back to the
dialogue. Specification silence never means "implementer decides".

Each heading-addressable requirement has an observable success condition and a counter-example.
Test its verification against **Evidence conditions**. On failure, express a non-code requirement
as human or platform inspection; drop a code behavior into an already reachable generic error path,
recording it as rejected with its missing conditions. Put agreements in the body, prohibitions in
what is not built, and rejected / undecided / delegated items in their own sections. Require
expensive model-running verification only when the person asks.

### Evidence conditions

An oracle — a test, a check, or a fixture — counts as evidence only when the condition it
produces has a named operational producer in a supported environment (untrusted input arriving
at a boundary is one), its subject is the product or a check rather than the oracle itself, the
rule it enforces is stated by the specification, and every wording, file layout, or internal
name it pins is declared there as a contract. An oracle that fails any of these is a cost: do
not add it, keep it in a change under review, or demand it.

A requirement whose only oracle would fail these conditions is not mechanically verifiable:
when it is not code, verify it by a human-run check or by the platform's own checker; when it
is code, drop the requirement and let the failure join a generic error path a reachable
failure already proves — never resolve it by having the implementer build the fixture.

Source: `ba0918-verification`, agentic-rules v0.8.0.

## Finishing

1. Adversarial review by separate-context agents, at least two: the specification's own quality,
   and conformance to the brainstorm record plus the repository's principles document when it
   keeps one (`docs/principles.md` by convention). New findings become branches; keep asking.
2. Check the conditions for handing to plan: one deliverable (one branch); result in one sentence;
   built and unbuilt scope; state and lifetime decided or absent; dependencies decided; human decision points and what they see; headings to requirements.
3. Stage the specification and the glossary change, give the path, the diff command, and the
   judgment points — never the full text, and never a summary as the thing approved. The person
   commits or says to. Then delete the progress file.
