---
name: ba0918-iterate
description: "Entry point beside the ba0918 workflow for a task too small to need a specification or a plan: a separate-context judge reads the repository and decides whether the request is a small task, then the cycle loop runs implementation, review, and fixing on it; anything bigger is turned away with the next skill to call. Use when asked to iterate, for one more fix, to fix this bit, to add this too, or to polish it a little more. 日本語キーワード: iterate ちょっと直して これも足して もう少し磨いて 小さいタスク"
---

# Iterate

Run cycle's loop on a **request** instead of a plan, once a read-only judgment says the task is
small. Delegate everything: never implement, review, fix, or judge here. A person starts this
skill from the conversation; cycle never calls it and hands nothing over — what the main session
learned there goes into the request; a findings file on the branch is inherited state (see the loop).

Required inputs: the request, and the branch with its worktree path, created by the main session
beforehand; missing either, stop: the main session must prepare them first — never create a branch
or a worktree here. The branch name is a short name for the request (no fixed prefix); right after a
cycle on the same branch, it is reused, not re-cut. Optional: cycle's four (round-trip limit, review
strength, comparison base, profiles) plus the specification path to match against; defaults are
cycle's. A **request** is the person's words completed by what the main session knows — named files,
settled direction, a preceding cycle's terminal report — into a self-contained text an implementer
with no context can build from. "Fix that thing from before" arrives expanded into the file and the
change; if one or two exchanges cannot expand it, this skill does not run.

Out: commits on the branch and a terminal report. Stopped at the judgment: no commit, guidance
only. Stopped by a hand-back during implementation: the commits so far stay (never deleted or
rewound), and the terminal report carries artifacts, commits, and diff view plus the guidance.

## Small task and its judgment

A **small task** meets all four; file count is irrelevant.

1. One reading: the implementer writes the diff without choosing one.
2. No specification decision: no new input kind, acceptance boundary, or error handling is
   decided for the first time by this task.
3. If a specification exists, no contradiction with it.
4. The impact is readable: the judge can enumerate every place to change and the list is closed
   — no "there may be others"; never a count. For an interface change, every caller enumerated
   and what changes at each one stated without judgment. Not readable means large.

Undecidable on 1 or 4 means not small; passing a doubtful request as small is a counter-example.
Thirty files in one spelling unification: small. A rename whose callers all enumerate and change
mechanically: small; four callers enumerated but one needing a choice on how it uses the return
value: not readable. "Make the error message clearer": one reading only with the wording given.

Before delegating implementation, delegate a read-only judgment to a separate-context **judge**
(judgment starts from a request; an investigation, from a symptom) with a self-contained prompt: the
request; the worktree path; the specification path if given — given none, the duty to search the
specification home the project's instruction files name for one covering the places to change (a
found one counts as a given one: condition 3, review conformance, the guidance; none found, go on
without, but passing condition 3 unsearched is a counter-example); the four conditions verbatim; the
return shape — the enumeration of places to change (file and change) plus a verdict with grounds per
condition; and these restrictions in full: do not edit, create, overwrite, delete, move, or rename
any file, notebooks included; allowed are reading files, listing paths, searching, running commands
known to be read-only, and following references; run only commands known to be read-only; forbidden,
as examples — refuse anything else that could change state the same way — are `rm` `rmdir` `mv` `cp`
`chmod` `chown` `touch` `mkdir` `tee`, output redirection, in-place rewriting, and state-changing
git; secrets are reported as existing, never by value; the judge writes no file and never delegates
further. Outside that prompt, take `git status` yourself before and after the judgment; a difference
is a spreading accident: stop, show it to the person, and ask; never revert it yourself.

The verdict is a proposal; the decision is here, as with reviewers in cycle. No verdict:
re-delegate once, then report that none was possible and stop. A place outside the enumeration met
during implementation means the impact was not readable: the implementer hands back (its prompt
says so) and this ends with the condition 4 guidance; a hand-back for a missing design decision
ends with the condition 2 guidance.

Not small: stop with guidance (the failed condition with grounds, the destination, a ready-to-use
invocation); never start brainstorm or plan yourself. Several failed: list all, destination from
the highest row, since a clarified request may change verdicts 2 to 4. Guiding to plan with no
specification (it cannot run without one) or offering "continue here anyway" is a counter-example.

| Failed | Destination | Ready-to-use form |
|---|---|---|
| 1 (ambiguous) | the person, via the main session | where the readings diverge, and the question to ask |
| 2 (specification decision), 3 (contradiction) | brainstorm | `/ba0918-brainstorm <topic>`, with the existing specification path if any |
| 4 (impact unreadable) | plan if a specification exists, else brainstorm | `/ba0918-plan <specification path>` or `/ba0918-brainstorm <topic>` |

## The loop

Read the ba0918-cycle skill body and run its loop, judgment, findings file, stopping rules, and
endings as written, with only these substitutions:

| In cycle's body | Read here as |
|---|---|
| the required plan path | the request |
| the branch name contains the plan name | a short name for the request |
| the specification path read from the plan | the given path, or the specification the judge found |
| inferring done steps from the plan and `git log`, then delegating the rest to implement | no inference: the request goes to the implementer in one delegation, after the judgment |
| the implement delegation (plan path, branch, worktree path) | the implementer delegation (request, the judge's enumeration, branch, worktree path) |
| the plan path in the fixer delegation | the request |
| the fixer contract's "the plan's commands in order, unedited" | check commands come from the project's instructions, then the ecosystem's standard tool |
| "run more" re-entering at step 1 when steps remain | always the diff loop; ending 4 (a hand-back) offers no "run more" — it ends with the guidance alone |
| the specification path in review delegations | the specification path and the request, both |

The **implementer** is cycle's fixer contract, pasted in full, given the request in place of the
visible findings; the implement skill is not used. It returns commits, evidence per completion
kind (test, check, artifact, external), and out-of-request changes with reasons — or a hand-back
with its reason. The enumeration goes along as reading material, marked as not an order; handing
it over as steps is a counter-example. Review receives the specification path if any and the
request; with none, the request is what reviewers match against, and there are two reviewers,
quality and conformance, so that someone checks the request was met.

Same branch right after a cycle, findings JSON still there: cycle's resume. Keep the findings;
visible ones are fixed by the loop; `human_judgment` and `record_only` stay open into the
terminal report; deleting or ignoring the file is a counter-example. Unless the person gave a
comparison base, it becomes the branch tip at start (the person already checked cycle's diff);
inherited open findings are still evaluated in the diff review, even outside the base. No default
round-trip limit; on one the person set, cycle's ending 2 applies. No counter of consecutive runs.

Cycle's terminal report and "never" list apply, "two plans at once" read as "two requests at
once", verification results taken from the implementer's evidence, plus, here only, the guidance
when the task was judged not small. "Look into this" belongs to the investigate skill, "check
that it works" and "verify this" to review's diagnosis; implementing from such words is a
boundary breach. "Fix it" or "add it" alone never starts this skill; ask for a reviewed loop.
