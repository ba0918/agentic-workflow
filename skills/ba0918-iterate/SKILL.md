---
name: ba0918-iterate
description: "Entry point beside the ba0918 workflow for a small task that should still be reviewed: runs cycle's implementation, review, and fixing loop on a request judged small, and turns anything bigger away with the next skill to call. Use when asked to iterate, or to run a reviewed loop on a small fix or addition; a bare request to fix or add something is edited directly instead. 日本語キーワード: iterate レビュー付きで直して レビューを回して 小さいタスク"
---

# Iterate

Run cycle's loop on a **request** instead of a specification, once judged small. Review and
fixing always go to separate contexts; the judgment and implementation are delegated only when
their conditions below hold. A person starts this skill from the conversation; cycle never calls
it and hands nothing over — what the main session learned there goes into the request; a findings file on the branch is
inherited state (see the loop). Required: the request, and the branch with its worktree path;
missing either, stop: the main session prepares them beforehand — never create a branch or a
worktree here. The branch name is short, for the request (no fixed prefix). Optional: cycle's optional
inputs (review items among them) plus the specification paths to match against (several allowed,
never an index); defaults are cycle's. A **request** is
the person's words completed by what the main session knows — named files, settled direction, a
preceding run's terminal report — into a self-contained text an implementer with no context can
build from. "Fix that thing from before" arrives expanded into the file and the change; if one or
two exchanges cannot, this skill does not run. Out: commits on the branch and a terminal report.
Stopped at the judgment: no commit, guidance only. Stopped by a hand-back during implementation: the
commits so far stay (never deleted or rewound), and the terminal report carries artifacts, commits,
and diff view plus the guidance.

## Small task and its judgment

A **small task** meets all four; file count is irrelevant.

1. One reading: the implementer writes the diff without choosing one.
2. No specification decision: no new input kind, acceptance boundary, or error handling is
   decided for the first time by this task.
3. If a specification exists, no contradiction with it.
4. The impact is readable: the judgment enumerates every file to change (files to be created included;
   for code, the tests the implementer adds test-first are among them) in a closed list — no "there
   may be others"; never a count — and says what changes in each without judgment (attached per
   entry; closure is judged per file); for an interface change, every caller is enumerated and its
   change said without judgment the same way. Not readable means large.

Undecidable on 1 or 4: not small. Thirty files in one spelling fix: small. A rename whose callers
all enumerate and change mechanically: small; four enumerated but one needing a choice on its return
value: not readable. "Make the error message clearer": one reading only with wording given.

The four conditions are judged here by default: this session already holds the context a judge
would re-read, so it enumerates the impact itself and records the verdict in one line. Delegate a
read-only **judge** (not an investigation, which starts from a symptom) only when the enumeration
cannot be closed — condition 4 in doubt — and say so; a judge over a closed enumeration is a
counter-example. When delegated, the prompt is self-contained: the request; the worktree
path; the specification paths if given, else the duty to search the specification home the project's
instructions name and report every specification covering the files to change, indexes not counted;
the four conditions verbatim; the return
shape (the files and their changes, plus a verdict with grounds per condition); and, in full, these
restrictions: no editing, creating, overwriting, deleting, moving, or renaming any file, notebooks
included; allowed — the only commands run — are reading files, listing paths, searching, read-only
commands (a test only when known to update nothing, in the repo or outside), and following references;
forbidden, as examples (refuse anything else that changes state): `rm` `rmdir` `mv` `cp` `chmod` `chown`
`touch` `mkdir` `tee`, output redirection, in-place rewriting, state-changing git; secrets reported as
existing, never by value; the judge writes no file and never delegates further. Take `git status`
yourself before and after; a difference is a spreading accident: stop, show the person, ask; never
revert it. Judging here, search the same way. Found specifications count as given — for condition
3, review, and the guidance table's "with the existing specification path if any"; none found, go on without; passing
condition 3 unsearched is a counter-example.
The verdict is a proposal; the decision is here, as with reviewers in cycle; a test file the implementer
needs test-first but the enumeration lacks is added here — that gap alone does not fail condition 4. No
verdict: re-delegate once, then report none was possible and stop.

Not small: stop with guidance (the failed condition with grounds, the destination, a ready-to-use
invocation); never start brainstorm or cycle yourself. Several failed: list all, destination from
the highest row, since a clarified request may change verdicts 2 to 4. Guiding to cycle or
offering "continue here anyway" is a counter-example.

| Failed | Also handed back for | Destination | Ready-to-use form |
|---|---|---|---|
| 1 (ambiguous) | — | the person, via the main session | where the readings diverge, and the question to ask |
| 2 (specification decision), 3 (contradiction) | a contradiction with the specification (3) — implementer or fixer | brainstorm | `/ba0918-brainstorm <topic>`, with the existing specification path if any |
| 4 (impact unreadable) | a file outside the enumeration (implementer only) | brainstorm | `/ba0918-brainstorm <topic>`, with the existing specification path if any |

## The loop

Read the ba0918-cycle skill body and run all of it as written, its Inputs included (the review skill
read before the first review); "cycle" there means this run. Cycle's path for a reason that added
no review never applies: this skill runs only when the caller's reason adds review. Only these
substitutions apply:

| In cycle's body | Read here as |
|---|---|
| the required specification paths and approval commit, and the scope they set | the request; specification paths only when given |
| the branch name contains the specification's name | a short name for the request |
| the received specifications as review's counterpart | the given paths, or the specifications the judgment found |
| when to have a plan written | never: work that large is not small and already stopped at the judgment |
| inferring what is done from the plan or specification and `git log`, then delegating the rest to implement | no inference: the request goes to the implementer in one delegation, after the judgment |
| the implement delegation (specification paths, scope, branch, worktree path) | the implementer delegation (request, the judgment's enumeration, the specification paths if any, branch, worktree path), with the contract's hand-back reasons read as: a file outside the enumeration; a contradiction with the specification |
| the specification paths and scope in the fixer delegation | the request, and the specification paths if any; the contract's hand-back reason reads as a contradiction with the specification |
| "every success condition is confirmed" in ending 1 | the request is met; with a specification, also the success conditions the request touches |
| each success condition's state in the terminal report | one line on whether the request was met; with a specification, also the success conditions the request touches |
| "run more" re-entering at step 1 when requirements or plan steps remain | always the diff loop |
| the specification paths and scope in review delegations | the specification paths and the request, both |
| ending 4 (a hand-back to brainstorm, or the assumption check ending on a contradiction) and its "run more or accept the rest" choice | the destination is the guidance table's; the choice is not offered — the report (as in Out above) adds the hand-back reason and the guidance, and the person restarts with a new request holding their answer |
| any other word meaning the received specification or scope (building the scope, unplanned changes) | the request (out-of-request changes); sentences about the plan (do not interpret it, a contradiction with it, the commit deleting it) do not apply — there is no plan |

The **implementer** is cycle's fixer contract pasted in full with the two sentences, the request
replacing the visible findings; the implement skill is not used. Where the reason did not name delegated implementation,
this session implements under that same contract, the rest of the loop unchanged. It returns
commits; whether the request was met (with a specification, also the success conditions it
touches), with evidence per completion kind; out-of-request changes with reasons; problems found
outside the request; provisional answers with the four items (what was chosen, why, where the
evidence is, its overturn condition) — or a hand-back and why. A request that turns out to read two ways, or a
design judgment found missing, during implementation is not handed back: the implementer takes a
provisional answer and the terminal report carries it — the product's direction was taken from the
person before the loop, and a request reading two ways at the judgment already stopped at condition
1. A file outside the enumeration is no judgment but a sign the task outgrew small, so it is never a
provisional answer.
The enumeration goes along as reading material, marked as not an order — handing it as steps is a
counter-example — yet it caps the files to touch (edit, create, delete, rename; tests included): one
outside it — hand back, never touch or report it. In a listed file, changes the request did not name
(import tidying, tests following) are out-of-request; an entry whose change differs is review's to
catch. The cap binds only the implementer; the fixer follows findings into any file, reporting those
outside as out-of-request. With no specification the request is the counterpart; review's own rule
adds the conformance reviewer, never a default.

Same branch right after a cycle or a run of this skill: reuse it, never re-cut; findings JSON still
there is cycle's resume, a start of this skill being cycle's "start" — deleting or ignoring it is a
counter-example, and the first review is the inherited max + 1. Unless the person gave a
comparison base, it is the branch tip at start (already checked); inherited open findings are
evaluated in the diff review even outside it. No default round-trip limit; one the person set
counts this run's reviews from when set, not the round numbers, and cycle's ending 2 applies. No
consecutive-run counter.

Cycle's terminal report, its merging (the setting works here under the same conditions), and its
"never" list apply — two requests at once in place of two branches — verification results from
the implementer's evidence, plus the guidance when not small or handed back. "Look into this" belongs to the investigate skill,
"check that it works" and "verify this" to review's diagnosis; implementing from them is a boundary
breach. "Fix it" or "add it" alone never starts this skill; ask for a reviewed loop. A small task
enters here only when the caller's reason adds review (several interdependent change sites, or the
person asked for review); one needing no review is edited directly by the main session, implementation
delegated only for volume.
