---
name: ba0918-brainstorm
description: "Workflow station of the ba0918 workflow that interviews the person until shared understanding is complete and writes the specification. Use when asked to brainstorm, define requirements, extract a specification, or resolve an ambiguity in one. 日本語キーワード: 壁打ち 要件定義 仕様抽出 ブレインストーム 質問ラウンド ドメインモデリング"
---

# Brainstorm

Interview the person until nothing is left implicit, then write the specification. This is
domain modeling: the goal is shared understanding, not a document. Compromise is not allowed,
and the station never ends itself — it ends when the tree is exhausted and the person approves.

## Inputs and outputs

In: what the person wants to talk about; when revising, the existing specification path (the
index's path when that scope is split). Before the first round, list `.agents/tmp/brainstorm-*.md`
and resume from a matching progress file; otherwise name it for the topic — a short name for what
this session discusses, or the index's name when revising a split scope.
Out: the specifications under the project's specification home (`docs/spec/` in the usual
layout), approved and committed, plus glossary updates and the list of specification paths
changed. One session may change several specifications. Progress lives in
`.agents/tmp/brainstorm-<topic>.md` and is deleted after approval.

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

A round holds only questions of three kinds, plus whether a requirement belongs in this
specification (see Terms and scenarios), which is always asked:

- product direction, preference, or a trade-off that reading and trying cannot settle;
- a decision whose later change means rebuilding what was built or the data accumulated;
- a point where the request text, a sample, or the records give a clue the person cares about it.

Check a fact that reading or running answers before the round, and put the result in the
question's background; asking the person what the repository already says is a counter-example.
Anything else is decided without asking, with its grounds, and recorded as delegated. That is
**edge behavior** — behavior the person never touched, with no clue, and no rebuild to change
later: boundary values, where combined rules split the result, inputs that rarely occur — and a
question whose every option keeps the agreed behavior and that is cheap to change later (a name,
a small default). The person overturns these at approval. When you cannot tell whether a question
is one of the three kinds, ask. This applies wherever brainstorm raises a question: ordinary
rounds, terms and scenarios, and after the finishing review. Counter-examples: putting edge
behavior the person has no answer to in a round with recommendations; deciding without asking
where a clue says the person cares; deciding without asking and not recording it as delegated.

## Conduct

- Never propose a whole design and ask for approval; never fire yes/no questions to
  manufacture a "decided" state. Recommended answers on granular questions are different.
- Do not re-ask what was decided without a reason. Challenge the person's ideas and your own
  with counter-arguments and counter-examples; "no objection" is not agreement.
- Say which statements are verified facts, inferences from facts, and unverified hypotheses.
- Before proposing to replace something that exists, read it; never judge by name or summary.
- Delegate fact-finding to a separate-context agent and keep asking meanwhile.

### Terms and scenarios

When a word can be read two ways and its reading is one of the three kinds, ask "does *X* mean
this?" with your reading as the recommended answer, in the normal round; otherwise decide the
reading and record it as delegated. Settled definitions go into the glossary (the
repository's `CONTEXT.md`): what the term *is*, and the words not to use for it. Only words
read two ways whose meaning here is this project's — no general vocabulary in its general sense.

When deciding how concepts relate, walk concrete scenarios — normal and edge cases — so no
boundary the person would care about is missed. Only a scenario whose prerequisites are settled
and that is one of the three kinds becomes a "what happens here?" question; for the others,
decide what happens and record it as delegated. Counter-examples found this way become the
counter-examples attached to requirements.

When a requirement does not change observable product behavior (release automation, licensing,
CI), ask whether it belongs here, in a separate specification, or is not built. Never add it silently.

Before approval, whoever notices an ambiguous term or a boundary that disagrees with the code asks
it there (in brainstorm, only when it is one of the three kinds) and records what becomes clear.
A drift a station finds after approval is not asked there: that station goes on with a provisional
answer and reports it, and fixing the glossary and specification goes to the next brainstorm.
Only brainstorm changes them, after the person decides.

### External interfaces

An **external interface** is what the person's procedures or other tools and scripts depend on:
the command form, output format, exit codes, the names and places of files written. Parts of it
that are one of the three kinds are asked in ordinary rounds. When any of it was decided without
asking, the last round before approval shows one **usage example** of ordinary use and asks
whether it is right: for a command, the command itself, the first lines of output, the exit code,
and the files written; for anything else, the call and what comes back. Edge behavior the example
does not show (which exit code wins when errors combine, which inputs are errors) is not asked
and stays delegated. What the person accepts or corrects becomes an agreement; what they leave to
you stays delegated. Note in the progress file's position that the example was shown. When more
interface is decided after it, in a round or not, ask again the same way before approval. With
nothing decided without asking, do not ask. Listing an unasked command form only as a delegated
line and going to approval is a counter-example.

## Records

Six kinds, kept in the progress file: agreement, prohibition, undecided (with who decides),
delegated (with reason), rejected (with reason), revision (what replaced what). Read
`references/records.md` for what each holds and the file's layout before writing the file.

## Writing the specification

Before writing, read `references/spec-documents.md`: whether to add to an existing specification
or start a new one, where a fact already lives, links, and when to split. Check for drafts,
contradictions, vague words, missing scope boundaries, related undecided items, and anything decided
without recording it; any of these sends you back to the dialogue. Text-search the specifications
for links to every heading you change and reread each one that links there for contradictions —
every time, whether or not Finishing adds a review; left to a review, it goes unread when none is
added.
Specification silence never means "implementer decides": write every silent point out before
approval. A station after approval that meets a silent point takes a provisional answer, which is
why one left here reaches the person only in a terminal report.

Each heading-addressable requirement has an observable success condition and a counter-example.
Test its verification against the Evidence conditions in the ba0918-review skill's
`references/oracle-evidence.md`; a delegated line that fixes an external interface counts as the
specification declaring it a contract. On failure, express a non-code requirement as human or
platform inspection; drop a code behavior into an already reachable generic error path,
recording it as rejected with its missing conditions. Put agreements in the body, prohibitions in
what is not built, and rejected / undecided / delegated items in their own sections. Require
expensive model-running verification only when the person asks.

## Finishing

1. Adversarial review, only when the specification's own requirements can contradict each other —
   several interdependent requirements, or one the record and the principles could pull apart.
   Say that reason, then launch one separate-context agent on the specification's own quality,
   and a second on conformance to the brainstorm record plus the repository's principles document
   when it keeps one (`docs/principles.md` by convention) — that second one only when the record
   is long enough that reading it back here would not catch the drift. A specification of a few
   standalone requirements gets none. Give reviewers only the specifications changed and those
   one link away, linking to them or linked from them — never the whole specification home: in a
   large context, reviewers miss contradictions too. New findings become branches: ask those of
   the three kinds, decide the others and record them as delegated. Putting a split the review
   found between combined rules to the person as it stands is a counter-example. Then ask the
   usage example (External interfaces) when an interface decided without asking has not been
   shown in one, or more was decided after it was shown.
2. Check the conditions for handing to cycle: one deliverable (one branch); result in one sentence;
   built and unbuilt scope; stored state and its lifetime decided or confirmed absent; external
   dependencies accepted or rejected; human decision points and what they see; headings to
   requirements.
3. Stage the specifications and the glossary change, give the paths, the diff command, and the
   judgment points — never the full text, and never a summary as the thing approved. The person
   commits or says to. Then delete the progress file.
4. Unless the person said "specification only", the main session creates the implementation
   branch and its worktree (the branch named for the specification, or for the topic when several
   changed), states the one-line declaration in ba0918-using-workflow's form from the approval
   commit's scope, and starts ba0918-cycle with the specification paths and the approval commit,
   without waiting for "implement it"; starting cycle without it is a counter-example. With
   "specification only", return the specification paths and end.
