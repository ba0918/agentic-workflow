---
name: ba0918-using-workflow
description: "Entry decider beside the ba0918 workflow: given a new request, name the skill it starts from — direct editing, iterate, brainstorm, plan then cycle, or investigate — and how much of the workflow runs, without starting the work; questions and chat are answered directly, never routed. Use when asked where to start, which skill to use, how much review a change needs, or to decide the entry point. 日本語キーワード: どこから始めるか 入口を決めて どの skill から 入口 使い分け ルーティング レビューは要るか 工程を減らす"
---

# Using the workflow

You are resident and read every turn; apply this to each new request before any other move.
Decide the entry and how much of the workflow runs. Do not start the work itself.

## What gets routed

Routed: building or changing something, a defect whose cause is unknown, and a question that
cannot be answered without reading or searching files. A question answerable from the
conversation, and chat, are answered directly — opening such an answer with a proposal to start
ba0918-brainstorm is a counter-example. Committing, releasing and the like follow the
environment's own rules. The boundary is the need to read.

## Add nothing by default

Each station — brainstorm, plan, plan review, delegated implementation, the small-task
judgment, review, the loop — costs a separate-context agent that re-reads the repository. None
is added by default; adding one needs a reason. State the line below, then act. The person
overrides it; never wait for approval.

```
outside reach · interdependent change sites · what would notice a mistake → stations added
```

| Station | Added when |
|---|---|
| brainstorm | the request reads two ways and one or two exchanges cannot settle it |
| plan | more than an implementer holds at once, or a person takes over midway |
| delegated implementation | enough volume to pollute this session's context |
| review | several interdependent change sites, so the implementation can contradict itself |
| the loop | a fix can spread beyond where it was made |

Reviewers are one per perspective: one, or two when a specification must be matched and no
machine check sees that match. A single site, independent changes, and mistakes a machine check
catches all take zero.

Three things are never traded away, and machine checks or the existing stop rules carry all
three, so none adds a station: secrets and credentials, and publishing, distribution or version,
go through the project's checks; irreversible, privileged and dangerous targets stop and ask.
Review itself is never mandatory. With no machine check, add one when that costs less than the
change; otherwise write "nothing would notice" in the line and go on — reviewers never
substitute for a missing check.

A review left out can be asked for afterwards: the line is also how the person notices none ran,
and ba0918-review called directly, or another ba0918-iterate run on the same branch, adds it then.

Outside reach shows in four signs: a publishing, distribution or version declaration;
credentials or secrets; reaching outside (network, deploy, migration); a deletion whose users
cannot be enumerated. A fifth needs a real incident behind it.

## The entry table

| Request | Entry |
|---|---|
| The line added no station | this session edits directly |
| A small task | ba0918-iterate |
| A medium-or-larger change with no specification, no grounds to judge by, or one that reads two ways | ba0918-brainstorm |
| A medium-or-larger change with a specification | ba0918-plan, then ba0918-cycle |
| A defect whose cause is unknown, or a question needing reading or searching | ba0918-investigate |

Rows below the first fire only for what the line named. A small task is ba0918-iterate's own
definition; an unreadable impact or a specification decision makes a change medium or larger. A
request to change a specification goes to ba0918-brainstorm with its path, not the plan row.

## Exceptions

Work with an approved plan or in-progress records is not rewound; it enters from where it left
off, and its skill's resume rules own the records. "Implement it" with an approved plan is
ba0918-cycle — implementing by hand there is a counter-example. A skill outside the table fires
on its own description.
