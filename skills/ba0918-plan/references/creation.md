# Plan creation

Require one implementation and review unit; named committed specification paths and sections;
observable success, a counterexample, and verification; declared human boundaries; and decided or
inapplicable distribution, runtime, persistence, external I/O, permissions, and new dependencies.
Return any missing consequential meaning to brainstorm before writing.

The verification mapping, Step headings, check commands, and Scope have a fixed machine-readable
form:

````markdown
**Verification coverage:**

- `docs/spec/example.md` / `Behavior` -> `1:test`
- `docs/spec/example.md` / `Failure handling` -> `2:check`

## Scope

```text
src/
  example.py
tests/
  example_test.py
```

## Step 1: Implement behavior

Use a failing behavioral test before production code.

## Step 2: Check generated output

**Checks:**

- `python3 scripts/check_output.py`
````

Each coverage row is exactly ``- `path` / `heading` -> `N:completion` ``. Paths are Markdown files
under `docs/spec/`; headings resolve exactly once at the approval commit; Step numbers are unique,
contiguous from 1, and mutually cover the rows. Every row for one Step uses the same completion
kind. Do not emit legacy `Target specifications`, a `## Steps` wrapper, or a body-level
`Completion` field. Scope is an expected file tree used to notice and explain omissions, not an
authorization list.

For every addressed requirement, design the smallest portfolio that would fail for a meaningful
counterexample and succeed for the required behavior. Choose behavioral unit tests, integration,
property-based tests, E2E, static checks, or an appropriate combination according to the service;
do not substitute an easy unit test for the contract being claimed. Distinguish the direct proof
from supporting checks such as lint or type checking.

Each `## Step N: title` explains purpose, prerequisites, expected files, concrete verification,
implementation choices explicitly delegated by the specification, and stop conditions. Its single
completion kind is declared by coverage: `test`, `check`, `artifact`, or `external`. A `check` Step
alone contains a `**Checks:**` list of exact commands in execution order. Use `artifact` or
`external` only when an executable check is inapplicable or disproportionate, and state the bounded
evidence an independent reviewer will judge. Skill wording does not require live LLM E2E unless a
scenario, model, and token budget are explicitly supplied. Human gates are limited to irreversible
operations, human-only permission, and dangerous targets. Missing consequential meaning returns to
brainstorm before the plan is written.

Write the canonical file under `docs/plans/`, run the plan reader, then perform independent review.
Stage the converged file for human approval and commit only after explicit acceptance.

Before review, run the read-only candidate command from the skill directory. It reads the working
plan bytes, but resolves every referenced specification from the named commit:

```sh
repo_root="$(git rev-parse --show-toplevel)"
python3 scripts/plan_artifact.py validate-candidate \
  --repo "$repo_root" \
  --plan docs/plans/20260829000000_example.md \
  --approval-commit "$(git -C "$repo_root" rev-parse HEAD)"
```

Replace only the example plan filename with the canonical candidate path. A successful command
writes its coverage, Steps, Checks, and Scope as JSON. A missing or changed committed
specification, an unsafe plan path, or malformed plan content exits unsuccessfully.
