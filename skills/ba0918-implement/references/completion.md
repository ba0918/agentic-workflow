# Completion kinds

## Test: RED → GREEN → REFACTOR

No production code without a failing test first. Every transition is proven by running the
tests in a shell and reading the output; a claimed transition without a run is a violation.

**RED** — write one small test for one behavior. Name it for the behavior, not the
implementation. Run it and confirm it fails *because the behavior is not implemented*. These
are not the expected failure and do not count: typos, import or load errors, missing
dependencies, permission or network errors, unrelated pre-existing failures. If the new test
passes, it tests existing behavior — fix the test.

**GREEN** — write only the code that makes that test pass. Do not change the test. No
speculative abstraction, no "while I am here" improvements. Run the suite: the new test passes
and nothing that passed before fails now.

**REFACTOR** — only after GREEN. Remove duplication, improve names, extract helpers; add no
behavior. Run the suite again. If there is nothing to tidy, record what you looked at and why
no change was needed, then move on — do not rearrange structure just to have refactored.

Red flags: production code edited before the test file; GREEN declared without a run; one test
covering several behaviors; refactoring before the tests pass; a mock setup larger than the test
logic; "tests later".

## Check

Run each listed command in the order the plan gives. Completion is all of them succeeding in
one pass. A failing command is fixed in the product, not by editing or replacing the command; a command
that cannot succeed as written (a name that does not exist, a rejected flag) is a plan defect —
hand back to plan.

## Artifact

Produce the document or file the step names. Run any format check the project has (a linter, a
schema validator). The artifact is complete when an
independent review could judge its meaning — not when it looks finished to you.

## External

Real hardware, a live service, a measurement. Before running anything, decide whether it is
safe, within your authority, and reversible; if any answer is no, hand back with the exact
command you would run. Afterwards keep only: the command, the decision-relevant numbers or
lines, and the pass/fail judgment. Full output and logs are not kept.
