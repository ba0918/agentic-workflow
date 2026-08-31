---
name: ba0918-cycle
description: "Workflow station of the ba0918 workflow: a small orchestrator that takes an approved plan and a branch, delegates implementation, review, and fixing to separate-context agents, and loops full review → diff loop → full review until findings converge, then hands the result to the person once. Use when asked to run a ba0918 cycle on a plan, or to resume one. 日本語キーワード: サイクル 実装ループ 改善ループ オーケストレータ 手順書を回す"
---

# Cycle

Run implement → review → fix on one plan until the visible findings are gone. Delegate
everything; cycle itself never implements, reviews, or fixes. The person sees only the terminal
report; the loop does not stop for them except in the cases below.

## Inputs

Required: the plan path and the branch with its worktree path. The main session creates both
before cycle starts; the branch name contains the plan name.
Optional: round-trip limit (default none: loop until convergence), review strength (the
person's choice, default `standard`), comparison base (default: merge-base with the branch's
parent), profiles (default: chosen from changed paths by the review skill's path mapping).

Read the plan only to find the specification path it names; do not interpret its steps.
The findings file is `.agents/artifacts/reviews/<branch>.json` (a `/` in the branch name is a
directory). If it already exists this is a resume: keep its findings, continue round numbers from
the inherited maximum, and count ending 3's streak from this start only (a returning closed cause
counts across starts). Either way, infer from the plan and `git log` which steps are done; skip
step 1 only when every step left a git trace. Otherwise delegate step 1: implement resumes by
inference and redoes untraced steps.

Before the first review, read the ba0918-review skill (its `SKILL.md`, `references/profiles.md`,
`references/finding-schema.md`) and paste the reviewer setup, the profile text, the read
restrictions, and the output shape into every reviewer prompt.

## Loop

1. Delegate the plan path, branch, and worktree path to an implement agent, all remaining steps
   in one delegation.
2. Full review: base..head, profiles, strength, specification path, plus the **known findings** (open
   `record_only` / `human_judgment`, closed `accepted`), never visible or fixed ones; a match is not raised again.
3. Diff loop: delegate the **visible findings** to a fixer; then diff review (changes since the
   last review, the open findings with IDs, profiles, strength, specification path). Repeat until
   no visible finding remains.
4. Last full review. Visible findings → one more diff loop until none remain; then converged.

Visible findings = open findings whose final action is `auto_fix` or `fix_and_verify`. Findings with
`human_judgment` or `record_only` are never delegated; they stay open for the terminal report. The
second full review cancels the taint a diff review carries from seeing prior findings. A **round
trip** is one review invocation (any number of reviewers, full or diff, the first one included). The
limit, when the person set one, counts round trips.

## Delegations

| To | Prompt carries | Comes back |
|---|---|---|
| implement | plan path, branch, worktree path | commits, per-step verification evidence, out-of-plan changes; or a hand-back with its reason |
| review (full) | base and head, worktree path, profiles, strength, spec path, known findings, reviewer setup | findings JSON |
| review (diff) | diff since last review, worktree path, open findings with IDs, profiles, strength, spec path, reviewer setup | per-finding `still_present` / `no_longer_visible`, new findings |
| fixer | visible findings, plan path, branch, worktree path, the fixer contract below | commits and which finding each addresses; or a hand-back |

The fixer has no skill of its own. Its contract, pasted in full: for code, RED → GREEN →
REFACTOR with a test run at every transition; for a check oracle, the plan's commands in order,
unedited; for an artifact, left judgeable by an independent review; for external work, hand
back before anything unsafe, privileged, or irreversible. One concern per commit,
`git add <path>` only, hooks never disabled, no station name or finding ID in a commit message,
missing design decisions handed back, not guessed; stop and ask before an irreversible or
privileged operation, a dangerous target, or a spreading accident.
Every prompt is self-contained; never assume a delegate loaded a skill or read the conversation.

## Judgment stays here

Cycle alone writes the findings file (shape: the review skill's `finding-schema.md`, plus `base` and
`last_reviewed_head`). After every review it overwrites the file: sets `last_reviewed_head`, assigns
IDs to new findings, merges reviewers and groups same-cause findings, finalizes each proposed action
before classifying visible findings (keep the reviewer's proposal unless its stated reason is
contradicted by the evidence; never move a finding out of `human_judgment` without first putting its
question to the person), appends every verdict to `evaluations` with its round-trip number, and
updates state. After every fix it records the reported commits under their findings.
`no_longer_visible` → closed (`fixed`); accepted by the person at the end → closed (`accepted`). If
reviewers disagree, one `still_present` means still present. A full review returns no IDs: match by
evidence location and oracle — a match with an open finding reuses its ID and appends
`still_present`; a match with a closed finding is "same cause returned" below and reopens it unless
it was closed `accepted`. Reviewers only evaluate; the fixer only reports commits.

## Stopping inside the loop

- A `security` finding, whatever its action: pause the whole loop before delegating anything
  and hand its content to the person unchanged. Their answer says whether it is fixed now (it
  becomes visible) or stays open for the terminal report; nothing closes it mid-loop.
- A delegate stops on an irreversible operation, a privileged operation, a dangerous target, or a
  spreading accident: relay the question verbatim, then resume or re-delegate with the answer.
- A delegate hands back a missing design decision: ending 4.

## Endings

1. Converged: the last full review returned no visible finding, or the diff loop after it cleared them.
2. The person's round-trip limit was reached.
3. No progress: a finding is `still_present` in two consecutive rounds that evaluated it (the
   second after a changed approach); a closed finding's cause returns; or a review still cannot
   succeed after one re-delegation.
4. A delegate handed back to brainstorm or plan.

Endings 2–4 add to the terminal report the choice "run more or accept the rest and finish" and
any hand-back reason. "Run more" continues the same run (streaks kept), findings still open, at
step 1 if untraced plan steps remain, else at step 3; a new limit, if any, is the person's to set.

## Terminal report

Always: artifacts and commits, verification results from the implement report, how to view
the diff. When present: fixed findings and forwarded observations, out-of-plan changes
with reasons, open findings and why they need the person. This is the person's one check;
merging is theirs. Cycle never merges, publishes, deletes branches or worktrees, edits the
specification, manages issues, or runs two plans at once.
