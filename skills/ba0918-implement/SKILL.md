---
name: ba0918-implement
description: "Workflow station of the ba0918 workflow that builds the requirements of an approved specification on a branch, following a plan when one exists, invoked by ba0918-cycle with specification paths, a scope, a branch, and a worktree path. Use when cycle delegates implementation of a ba0918 specification or plan. 日本語キーワード: 実装 仕様書を実装 手順書を実行 TDD 実装計画"
---

# Implement

Build the requirements you were given. Code is built test-first; documents and small scripts may
be written directly. The person sees the result at the end of the cycle, not per requirement.

## Inputs and outputs

In: the worktree path, the specification paths, the scope (the requirements to build), the
branch, and the plan path when there is one; work only inside that worktree. Build only the
scope's requirements. With a plan, carry out its steps in the order written; a step names the
specification sections it rests on. Without one, read the scope's requirements and choose the
order yourself. Read whatever else in the repository the work needs. Nothing else is handed to
you — the repository is the context.
Out: commits on that branch and the verification result of each success condition in the scope.

The criteria in your request are all there is: add no check, approval, or review of your own.
Decide reversible choices without asking; those that are judgments of meaning or design are
reported as provisional answers.

## Stop only for these

Stop and ask the person only in these three cases, then continue with the answer:

- just before an irreversible operation, a privileged operation, or a dangerous target (production
  data, configuration, external effects);
- continuing would spread damage (secret exposure, unintended publication, data loss);
- a probe that is itself irreversible, privileged, or touches a dangerous target (reaching the
  network, installing something) — ask before it runs.

Hand back, ending this run, only in these two cases:

- a change contradicting the approved specification is needed → back to brainstorm; approved
  content is the person's to change;
- a change contradicting the plan is needed → back to cycle with the reason; cycle has the plan
  rewritten, so this never reaches the person.

A requirement with no means to verify it (the specification names none, and no qualifying test
exists) is not a reason to stop: build it, and return its success condition as unverified.

A product, design, persistence, or technology judgment the plan and the specification do not
settle is not a reason to stop. Take the answer with the strongest grounds as a provisional answer,
go on, and report it with its overturn condition (what the person would say to overturn it).
Before choosing one, ask whether running something in the worktree would answer the question (what
a library returns, whether a check passes, how long a command takes). That is a fact, not a
judgment: run the smallest throwaway probe, leave nothing of it in the worktree or the commits, act
on what it showed, and report the command with a decision-relevant summary. A provisional answer is
only for what no run can settle — what the specification should mean, or a tool nothing chooses.
Settling a question a run could answer with a provisional answer is a counter-example.

When the work still makes no progress after diagnosing and changing approach once, do not hand
back yet. Write the assumptions your attempts shared as an assumption stack, in the form given by
steps 1 and 2 of the ba0918-cycle skill's `references/assumption-check.md` (your last attempt in
place of the last fix), swap the top assumption, and try once. If that still makes no progress,
hand back with the stack; cycle ends on no progress. If working on the swapped assumption would
contradict the approved specification, do not try it: hand back to brainstorm as above. This
applies to implementing plan steps or specification requirements only, never to a fixer.

Everything else you recover from yourself: an unplanned but safe file to add, a flaky helper
tool, a hook failure, an ordinary command failure, a missing bit of record you can reconstruct.
Never ask for acceptance of the result piece by piece; that happens once, at the end of the cycle.

## Completing a requirement or step

Each requirement or step is shown complete in one of four kinds; details in
`references/completion.md`:

- **Test**: RED → GREEN → REFACTOR, one small failing test per behavior, run in a shell at every
  transition.
- **Check**: run the check commands in order; done only when all succeed. A command the plan or the
  project's instructions name is never substituted on the spot.
- **Artifact**: a document such as a README or skill text; pass any format check that exists and
  leave it in a state an independent review can judge.
- **External**: real devices or measurements; stop and ask the person before running anything
  unsafe, privileged, or irreversible. Keep the command and a decision-relevant summary, not full logs.

Test and check commands come from, in order: the plan when there is one, the project's own
instructions, the ecosystem's standard tool. If none settles it, choose one by reading the
repository, run it to show it works, and report it as a provisional answer with its overturn
condition; whether a command works is a fact a run settles, so never hand back for it. A standard
tool that must be installed first is asked about before installing.

## Committing

- One concern per commit. A test and the minimal code that makes it pass are one concern.
- Stage with `git add <path>`; never `git add .` or `-A`. Never disable or bypass hooks.
- Message: follow the repository's commit conventions; a body only when the *why* needs it.
  Never name a workflow station (brainstorm / plan / cycle / implement / review), a finding ID,
  or session chronology.
- Changes outside the plan that the work needs (import tidying, tests following) and that do not
  change its thrust: commit them with the reason recorded, and list them in the final report. One
  that changes the plan's thrust contradicts the plan: hand back to cycle.
- A problem found outside the scope is not fixed and not asked about: list it in the final report.
- Do not invent verification of verification: tests whose subject is a check or test helper itself,
  and tests pinning workflow prose, are created only when the plan, finding, or specification
  requires them. This does not bar unit tests of product helpers for behavior they support.
- For a deletion finding, no failing test is needed. Completion evidence is all existing checks
  passing after deletion.
- Keeping secrets out of commits is your responsibility; nothing scans for you.

## Resuming

There is no progress file. To resume, read the plan (or, without one, the specification), `git
log`, the working diff, and `git status`, and infer where you are. Work that leaves no trace in git
(check-only steps, external checks) and approved-but-unexecuted human decisions are redone or
re-asked.

## Report at the end

Commits made; the verification result of each success condition in the scope (confirmed with its
evidence — test names run, check commands, artifact paths, external summaries — or unverified with
why); probes run (command and summary); unplanned changes with reasons; out-of-scope problems
found; provisional answers — the plan's as well as your own — each with what was chosen, why,
where the evidence is (a commit, a file and line, or a command with a summary of its output), its
overturn condition, and where the rule it added lives; anything handed back and why, with the
assumption stack when the swapped assumption did not help.
