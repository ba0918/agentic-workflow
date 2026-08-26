# Check, artifact and external steps

Read this reference for steps you declared as `check`, `artifact`, or `external`. None
of them can be shown by a test written first. A `check` step is decided by the commands the plan
names; the other two produce something only a person can judge — prose an AI will read, a
configuration file, a check on a running system — so their completion rests on recorded evidence
plus the human's verdict.

## Check steps (`check`)

The plan names the commands, and their exit codes decide the step. Do not ask for approval here:
there is nothing for a person to read that the commands do not already answer, and an approval
with nothing to read teaches the human to answer without looking.

1. Run `context` for the step, then do the work the step describes — run the generator, fix the
   files — inside the plan's scope.
2. Record the step:

   ```text
   python3 <implement-runtime> record-check \
     --repo <main-checkout> --step step-<n>
   ```

   The helper reads the commands from the step's `**Checks:**` declaration and runs them in the
   order the plan writes them, inside the worktree. It appends a `check` event holding each
   command with its exit code, and every in-scope file that changed with its content identity.
   It passes no command of its own and takes none at call time: what was declared is what
   runs.
3. A command that does not succeed records nothing and does not stop the execution
   (`check_failed` names the command). Fix what the command reports and run `record-check` again.
4. Stage, commit, and record the commit as in [tdd.md](tdd.md) — but only when the check covered
   a change. A step that changed no file is complete on its `check` event alone: a check confirms,
   it does not produce.

## Artifact steps (`artifact`)

1. Run `context` for the step, then create or edit the files the plan names, inside the plan's
   scope.
2. Run the format checks the plan names (a skill structure check, a broken-link check, …). Do not
   choose checks the plan does not mention; a step without named checks records none.
3. Record the deliverable:

   ```text
   python3 <implement-runtime> record-artifact \
     --repo <main-checkout> --step step-<n> \
     --path <repo-relative-file> [--path ...] \
     [--check "<format check command>" ...]
   ```

   The helper refuses a path outside the scope or a file that does not exist, runs each check
   inside the worktree, and appends an `artifact` event holding every file's content identity and
   every check's command and exit code. A failing check is recorded, not hidden — but passing the
   checks is part of the completion itself, so a deliverable with a failed check cannot be
   approved (`format_check_failed`): fix it and record it again.
4. Ask the human to read the files. Present the paths and identities; do not paste the content
   into chat as the thing to approve. When they answer, record the verdict:

   ```text
   python3 <implement-runtime> approve \
     --repo <main-checkout> --step step-<n> --result <approved-or-rejected>
   ```

   The `approval` event binds the verdict to the identity of the step's latest `artifact` event.
   This verdict is required even when the plan declares no `**Human gates:**` for the step; it is
   distinct from a declared gate (`human_gate`), which the plan must name explicitly.
5. Stage, commit, and record the commit as in [tdd.md](tdd.md). The staging helper refuses an
   `artifact` step whose latest deliverable has no approved verdict — so editing a file after
   approval means recording it again and asking again.

## External steps (`external`)

1. Run `context` for the step, then perform the check the plan describes. Run what the agent can
   run; ask the human to perform what it cannot, and take their report as the result.
2. Record it:

   ```text
   python3 <implement-runtime> record-external \
     --repo <main-checkout> --step step-<n> \
     --checked "<what was checked, as the plan describes it>" \
     --summary "<short result>"
   ```

   Both texts are bounded (500 characters) and may not carry secret-shaped values. Full output
   and external service logs are never stored.
3. Ask the human to look at the result and record their verdict with `approve` as above.
4. Commit only when the step leaves something to commit; an `external` step is complete after the
   approval alone, and a commit, when present, is verified like any other.

## Rejection

`approve --result rejected` records the verdict and a `stopped` event, and the execution halts.
Fix the deliverable in a later invocation: the unfinished-execution check finds this execution,
the human chooses to continue, `resume` names the step again, and the step is recorded and
approved afresh.

## Terminal hand-off

`implementation-green` checks every step against its completion kind: `test` needs RED, GREEN,
REFACTOR, and commit; `check` needs a `check` event whose commands all succeeded, followed by a
commit when that check recorded a changed file; `artifact` needs an approved `artifact` event
followed by a commit; `external` needs an approved `external` event, with or without a commit.
Evidence of another completion kind on a step — test evidence on an `artifact`, `external`, or
`check` step, or a `check` inside a `test` step — is a mismatch and never completes the step.
