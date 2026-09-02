---
name: ba0918-implement
description: "Workflow station of the ba0918 workflow: execute an approved plan step by step, test-first for code, committing one concern at a time, and hand back instead of guessing when a design decision is missing. Invoked by ba0918-cycle with a plan path, a branch, and a worktree path. Use when cycle delegates implementation of a ba0918 plan. 日本語キーワード: 実装 手順書を実行 TDD 実装計画"
---

# Implement

Carry out the plan you were given, in the order written. Code is built test-first; documents
and small scripts may be written directly. The person sees the result at the end of the cycle,
not per step.

## Inputs and outputs

In: the worktree path, the plan path, and the branch; work only inside that worktree. Out:
commits on that branch. A plan step names the
specification sections it rests on; read those sections and whatever else in the repository the
step needs. Nothing else is handed to you — the repository is the context.

## Stop only for these

Hand back (stop, state the reason, do not guess) when:

- a consequential design decision is not in the plan or the specification, or the approved
  content must change → back to brainstorm;
- the plan step asks for confirmation before an irreversible operation, a privileged operation,
  or a dangerous target (production data, configuration, external effects) → ask, then continue;
- continuing would spread damage (secret exposure, unintended publication, data loss) → stop;
- after diagnosing and changing approach once there is still no progress → stop;
- no test command can be determined (see below) → back to plan before writing product code.

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
- **External**: real devices or measurements; hand back before running anything unsafe,
  privileged, or irreversible. Keep the command and a decision-relevant summary, not full logs.

The test command comes from, in order: the plan, the project's own instructions, the standard
tool for the ecosystem. If none decides it, hand back to plan.

## Committing

- One concern per commit. A test and the minimal code that makes it pass are one concern.
- Stage with `git add <path>`; never `git add .` or `-A`. Never disable or bypass hooks.
- Message: follow the repository's commit conventions; a body only when the *why* needs it.
  Never name a workflow station (brainstorm / plan / cycle / implement / review), a finding ID,
  or session chronology.
- Fixes outside the plan that do not change its thrust: commit them with the reason recorded,
  and list them in the final report. Anything that changes the thrust is a hand-back.
- Do not invent verification of verification: tests of checks or helpers, or tests pinning
  workflow prose, are created only when the plan, finding, or specification requires them.
- For a deletion finding, no failing test is needed. Completion evidence is all existing checks
  passing after deletion.
- Keeping secrets out of commits is your responsibility; nothing scans for you.

## Resuming

There is no progress file. To resume, read the plan, `git log`, the working diff, and
`git status`, and infer where you are. Steps that leave no trace in git (check-only steps,
external checks) and approved-but-unexecuted human decisions are redone or re-asked.

## Report at the end

Commits made, verification evidence per step (test names run, check commands, artifact paths,
external summaries), out-of-plan changes with reasons, anything handed back and why.
