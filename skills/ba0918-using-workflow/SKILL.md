---
name: ba0918-using-workflow
description: "Entry decider beside the ba0918 workflow: given a new request, name the skill it starts from — iterate, brainstorm, plan then cycle, or investigate — without starting the work; questions and chat are answered directly, never routed. Use when asked where to start, which skill to use, or to decide the entry point. 日本語キーワード: どこから始めるか 入口を決めて どの skill から 入口 使い分け ルーティング"
---

# Using the workflow

You are resident and read every turn; apply this to each new request before any other move.
Decide only the routing — which skill the request enters from — and do not start the work
itself.

## What gets routed

Three kinds of request are routed: building or changing something, a reported defect whose
cause is unknown, and a question that cannot be answered without reading or searching files.
Everything else is out of scope. A question answerable from the conversation, and chat, are
answered directly — never sent to a skill; opening the answer to a question with a proposal
to start ba0918-brainstorm is a counter-example. Operations that are not building or
changing (committing, releasing, preparing a PR, and the like) are also out of scope and
follow the environment's own means and rules.

The boundary is the need to read: answerable in conversation means out of scope; answerable
only by reading or searching files means it is an investigation request.

## The entry table

| Request | Entry |
|---|---|
| A small task | ba0918-iterate |
| A medium-or-larger change with no specification, no grounds to judge by, or a request that reads two ways | ba0918-brainstorm |
| A medium-or-larger change with a specification | ba0918-plan, then ba0918-cycle |
| A reported defect whose cause is unknown, or a question needing reading or searching | ba0918-investigate |

The definition of a small task, and the words that start one, are ba0918-iterate's own. A
bare "fix it" leaves the person the path of having the main session fix it directly. A
change whose impact cannot be read, or that needs a specification decision, is medium or
larger. "Make the error message clearer" with no wording given reads more than one way — it
goes to ba0918-brainstorm, not to a small task. A request to change a specification itself
goes to ba0918-brainstorm carrying the existing specification's path, never through the
plan row. A defect sent to ba0918-investigate continues from its report's recommended next
action, which names the next entry; a defect whose fix location and content are clear from
the start and that meets the small-task definition goes to ba0918-iterate.

## Exceptions

Work that already has an approved plan, or in-progress records, is not rewound to
brainstorm; it enters from where it left off. "Implement it" with an approved plan is
ba0918-cycle — the main session implementing by hand there is a counter-example. Work whose
in-progress brainstorm, cycle, or iterate records remain follows the resume rules of the
skill that owns those records. A skill outside the table fires on its own description and
never falls into the table.
