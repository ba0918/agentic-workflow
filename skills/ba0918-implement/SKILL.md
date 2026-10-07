---
name: ba0918-implement
description: "Workflow station of the ba0918 workflow that carries out the steps of an approved plan on a branch, invoked by ba0918-cycle with a plan path, a branch, and a worktree path. Use when cycle delegates implementation of a ba0918 plan. 日本語キーワード: 実装 手順書を実行 TDD 実装計画"
---

# Implement

Carry out the plan you were given, in the order written. Code is built test-first; documents
and small scripts may be written directly. The person sees the result at the end of the cycle,
not per step.

## Inputs and outputs

In: the worktree path, the plan path, and the branch; work only inside that worktree. Out:
commits on that branch. A plan step names the specification sections it rests on; read those
sections and whatever else in the repository the step needs. Nothing else is handed to you — the
repository is the context.

## Stop only for these

Stop and ask the person only in these three cases, then continue with the answer:

- the plan step asks for confirmation before an irreversible operation, a privileged operation,
  or a dangerous target (production data, configuration, external effects);
- continuing would spread damage (secret exposure, unintended publication, data loss);
- a probe that is itself irreversible, privileged, or touches a dangerous target (reaching the
  network, installing something) — ask before it runs.

Hand back upstream, ending this run, only in these two cases:

- a change contradicting the approved specification or plan is needed → back to brainstorm
  (specification) or plan (plan); approved content is the person's to change;
- no test command can be determined (see below) → back to plan before writing product code.

A product, design, persistence, or technology judgment the plan and the specification do not
settle is not a reason to stop. Take the answer with the strongest grounds as a provisional answer,
go on, and report it with its overturn condition (what the person would say to overturn it).
Before choosing one, ask whether running something in the worktree would answer the question (what
a library returns, whether a check passes, how long a command takes). That is a fact, not a
judgment: run the smallest throwaway probe, leave nothing of it in the worktree or the commits, act
on what it showed, and report the command with a decision-relevant summary. A provisional answer is
only for what no run can settle — what the specification should mean, or a tool the plan does not
choose. Settling a question a run could answer with a provisional answer is a counter-example.

When a plan step still makes no progress after diagnosing and changing approach once, do not hand
back yet. Write the assumptions your attempts shared as an assumption stack: one sentence per
level, the most specific one (what the last attempt touched) at the bottom and what the others rest
on above it, each marked as living in the implementation or in the plan or specification. Swap the
top assumption and try once. If that still makes no progress, hand back with the stack; cycle ends
on no progress. If working on the swapped assumption would contradict the approved specification
or plan, do not try it: hand back upstream as above. This applies to implementing plan steps only.

Everything else you recover from yourself: an unplanned but safe file to add, a flaky helper
tool, a hook failure, an ordinary command failure, a missing bit of record you can reconstruct.
Never ask for acceptance of the result step by step; that happens once, at the end of the cycle.

## Completing a step

Each plan step says how its completion is shown. Four kinds; details in
`references/completion.md`:

- **Test**: RED → GREEN → REFACTOR, one small failing test per behavior, run in a shell at every
  transition.
- **Check**: run the check commands the plan lists, in order; done only when all succeed. Never
  substitute a different command on the spot.
- **Artifact**: a document such as a README or skill text; pass any format check that exists and
  leave it in a state an independent review can judge.
- **External**: real devices or measurements; stop and ask the person before running anything
  unsafe, privileged, or irreversible. Keep the command and a decision-relevant summary, not full logs.

The test command comes from, in order: the plan, the project's own instructions, the ecosystem's
standard tool when it runs without installing anything — a provisional answer, reported with the
command and its overturn condition. A standard tool that must be installed first is asked about
before installing. If none applies, hand back to plan before writing product code.

## Committing

- One concern per commit. A test and the minimal code that makes it pass are one concern.
- Stage with `git add <path>`; never `git add .` or `-A`. Never disable or bypass hooks.
- Message: follow the repository's commit conventions; a body only when the *why* needs it.
  Never name a workflow station (brainstorm / plan / cycle / implement / review), a finding ID,
  or session chronology.
- Fixes outside the plan that do not change its thrust: commit them with the reason recorded,
  and list them in the final report. One that changes the thrust contradicts the approved plan:
  hand back to plan.
- Do not invent verification of verification: tests whose subject is a check or test helper itself,
  and tests pinning workflow prose, are created only when the plan, finding, or specification
  requires them. This does not bar unit tests of product helpers for behavior they support.
- For a deletion finding, no failing test is needed. Completion evidence is all existing checks
  passing after deletion.
- Keeping secrets out of commits is your responsibility; nothing scans for you.

## Resuming

There is no progress file. To resume, read the plan, `git log`, the working diff, and
`git status`, and infer where you are. Steps that leave no trace in git (check-only steps,
external checks) and approved-but-unexecuted human decisions are redone or re-asked.

## Report at the end

Commits made, verification evidence per step (test names run, check commands, artifact paths,
external summaries), probes run (command and summary), out-of-plan changes with reasons,
provisional answers with their overturn conditions, anything handed back and why — with the
assumption stack when the swapped assumption did not help.
