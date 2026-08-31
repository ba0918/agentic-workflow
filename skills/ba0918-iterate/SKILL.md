---
name: ba0918-iterate
description: "Entry point beside the ba0918 workflow for a task too small to need a specification or a plan: a separate-context judge reads the repository and proposes a verdict on whether the request is a small task, this skill decides, then the cycle loop runs implementation, review, and fixing on it; anything bigger is turned away with the next skill to call. Use when asked to iterate, for one more fix, to fix this bit, to add this too, or to polish it a little more. 日本語キーワード: iterate ちょっと直して これも足して もう少し磨いて 小さいタスク"
---

# Iterate

Run cycle's loop on a **request** instead of a plan, once a read-only judgment says the task is
small. Delegate everything: never implement, review, fix, or judge here. A person starts this
skill from the conversation; cycle never calls it and hands nothing over — what the main session
learned there goes into the request; a findings file on the branch is inherited state (see the
loop). Required inputs: the request, and the branch with its worktree path; missing either, stop:
the main session prepares them beforehand — never create a branch or a worktree here. The branch
name is a short name for the request (no fixed prefix). Optional: cycle's four optional inputs plus
the specification path to match against; defaults are cycle's. A **request** is the person's words
completed by what the main session knows — named files, settled direction, a preceding run's
terminal report — into a self-contained text an implementer with no context can build from. "Fix
that thing from before" arrives expanded into the file and the change; if one or two exchanges
cannot expand it, this skill does not run. Out: commits on the branch and a terminal report.
Stopped at the judgment: no commit, guidance only. Stopped by a hand-back during implementation:
the commits so far stay (never deleted or rewound), and the terminal report carries artifacts,
commits, and diff view plus the guidance.

## Small task and its judgment

A **small task** meets all four; file count is irrelevant.

1. One reading: the implementer writes the diff without choosing one.
2. No specification decision: no new input kind, acceptance boundary, or error handling is
   decided for the first time by this task.
3. If a specification exists, no contradiction with it.
4. The impact is readable: the judge enumerates every file to change (files to be created included)
   in a closed list — no "there may be others"; never a count — and says what changes in each without
   judgment (attached per entry; closure is judged per file). Not readable means large.

Undecidable on 1 or 4 means not small. Thirty files in one spelling unification: small. A rename
whose callers all enumerate and change mechanically: small; four callers enumerated but one needing
a choice on its return value: not readable. "Make the error message clearer": one reading only with
the wording given.

Before implementation, delegate a read-only judgment to a separate-context **judge** (not an
investigation, which starts from a symptom) with a self-contained prompt: the request; the worktree
path; the specification path if given, else the duty to search the specification home the project's
instructions name and report one covering the files to change; the four conditions verbatim; the
return shape (the files and their changes, plus a verdict with grounds per condition); and, in full,
these restrictions: no editing, creating, overwriting, deleting, moving, or renaming any file,
notebooks included; allowed — and the only commands run — are reading files, listing paths,
searching, read-only commands, and following references; forbidden, as examples (refuse anything
else that changes state the same way): `rm` `rmdir` `mv` `cp` `chmod` `chown` `touch` `mkdir` `tee`,
output redirection, in-place rewriting, state-changing git; secrets reported as existing, never by
value; the judge writes no file and never delegates further. Take `git status` yourself before and
after the judgment; a difference is a spreading accident: stop, show it to the person, and ask;
never revert it. A found specification counts as given — for condition 3, review, and the guidance
table's "if a specification exists"; none found, go on without; passing condition 3 unsearched is a
counter-example. The verdict is a proposal; the decision is here, as with reviewers in cycle. No
verdict: re-delegate once, then report none was possible and stop.

Not small: stop with guidance (the failed condition with grounds, the destination, a ready-to-use
invocation); never start brainstorm or plan yourself. Several failed: list all, destination from
the highest row, since a clarified request may change verdicts 2 to 4. Guiding to plan with no
specification (it cannot run without one) or offering "continue here anyway" is a counter-example.

| Failed | Also handed back for | Destination | Ready-to-use form |
|---|---|---|---|
| 1 (ambiguous) | the request read two ways (implementer) | the person, via the main session | where the readings diverge, and the question to ask |
| 2 (specification decision), 3 (contradiction) | a missing design decision (2), a contradiction with the specification (3) — implementer or fixer | brainstorm | `/ba0918-brainstorm <topic>`, with the existing specification path if any |
| 4 (impact unreadable) | a file outside the enumeration (implementer only) | plan if a specification exists, else brainstorm | `/ba0918-plan <specification path>` or `/ba0918-brainstorm <topic>` |

## The loop

Read the ba0918-cycle skill body and run all of it as written, its Inputs included (the review skill
read before the first review); "cycle" there means this run. Only these substitutions apply:

| In cycle's body | Read here as |
|---|---|
| the required plan path | the request |
| the branch name contains the plan name | a short name for the request |
| the specification path read from the plan | the given path, or the specification the judge found |
| inferring done steps from the plan and `git log`, then delegating the rest to implement | no inference: the request goes to the implementer in one delegation, after the judgment |
| the implement delegation (plan path, branch, worktree path) | the implementer delegation (request, the judge's enumeration, the specification path if any, branch, worktree path) |
| the plan path in the fixer delegation | the request, and the specification path if any |
| the fixer contract's "the plan's commands in order, unedited" | check commands come from the project's instructions, then the ecosystem's standard tool |
| "run more" re-entering at step 1 when steps remain | always the diff loop |
| the specification path in review delegations | the specification path and the request, both |
| ending 4 (a hand-back to brainstorm or plan) and its "run more or accept the rest" choice | the destination is one of the guidance table's three; the choice is not offered — the report (as in Out above) adds the hand-back reason and the guidance, and the person restarts with a new request holding their answer |
| any other plan word meaning the plan (one plan at once, out-of-plan changes) | the request (out-of-request changes); plan as a skill name, a destination, stays; sentences about plan steps (do not interpret its steps, if steps remain) do not apply — there is no plan |

The **implementer** is cycle's fixer contract pasted in full, the request replacing the visible
findings; the implement skill is not used. It returns commits, evidence per completion kind,
out-of-request changes with reasons — or a hand-back and why. The enumeration goes along as reading
material, marked as not an order — handing it as steps is a counter-example — yet the cap on files:
one outside it (edit, create, delete, rename; tests included) means the impact was not readable:
hand back; never touch it or report it as out-of-request. Inside a listed file, changes the request
did not name (import tidying, tests following) go on as out-of-request; an entry whose change came
out different is review's to catch. The cap binds only the implementer; the fixer follows findings
into any file, reporting those outside as out-of-request. With no specification, reviewers match
the request — two, quality and conformance, so someone checks it was met.

Same branch right after a cycle or a run of this skill: reuse it, never re-cut; findings JSON still
there is cycle's resume — keep the findings (deleting or ignoring the file is a counter-example) and
continue rounds from the inherited max (the first review is max+1). Unless the person gave a
comparison base, it is the branch tip at start (that diff was already checked); inherited open
findings are evaluated in the diff review even outside the base. Ending 3's streaks (`still_present`
two rounds running; three full reviews each with new findings) reset at a start of this skill
(inherited evaluations uncounted), not at "run more" after ending 2 or 3; a closed cause returning
counts across the boundary. No default round-trip limit; one the person set counts this run's
reviews, not the round numbers, and cycle's ending 2 applies. No counter of consecutive runs.

Cycle's terminal report and "never" list apply, verification results taken from the implementer's
evidence, plus, here only, the guidance when the task was judged not small or handed back. "Look
into this" belongs to the investigate skill, "check that it works" and "verify this" to review's
diagnosis; implementing from such words is a boundary breach. "Fix it" or "add it" alone never
starts this skill; ask for a reviewed loop.
