---
name: ba0918-implement
description: Use when one approved plan must be executed step by step with TDD and append-only evidence, usually as a synchronous cycle delegate. Continues safe ordinary work autonomously and returns only consequential decisions or dangerous boundaries.
metadata:
  contracts:
    - implement-runtime
---

# Implement

Execute one approved plan in its dedicated `implement/<run-id>` branch and linked worktree.
Implement does not review, merge, publish, complete the plan, or delete execution resources.

## Load routing

- Read [execution.md](references/execution.md) when resolving, starting, resuming, rebinding, or
  judging document change.
- Read [tdd.md](references/tdd.md) for a test step.
- Read [artifacts.md](references/artifacts.md) for check, artifact, or external completion.
- Read [evidence.md](references/evidence.md) before writing durable records.

## Boundary

- Read the named committed plan through `scripts/implement_runtime.py`. Its path stem is the plan
  key. Require its working bytes to equal the last commit that changed that plan, parse those
  approved bytes, and return approved/current specification versions plus their Git diff for the
  agent's semantic decision; wording-only specification drift is not an automatic rejection.
- Treat Scope as expected paths. A safe ordinary omission is recorded with its reason and included;
  it is not a human gate.
- Derive changed paths from Git's actual staged diff and each recorded commit, then apply secret,
  dangerous-path, temporary, log, generated-output, and sensitive-target checks to every path,
  expected or not. Never accept a caller's claim that a safety check passed.
- During a cycle delegation, implement is the only evidence writer. Cycle records the delegation
  boundaries.
- New or changed external dependencies and missing product, persistence, architecture, permission,
  or dangerous-operation meaning return to the human. Dependencies already approved by the plan
  may be used.
- Recover helper failures, missing reconstructible records, hook failures, and a replaced RED
  inside the run. Diagnose a stalled method and change it once before returning to the human.

## Completion

Complete when every plan step has its required evidence and, when that completion kind requires
one, a commit; `check` and `external` need no commit when Git reports no changed paths. All Git-
derived safety checks must pass, and an
`implementation_green` event has been derived by the runtime from valid step transitions, recorded
commits, the bound branch/worktree, and a clean worktree. Every append also updates `current-status`
in the same operation. Hand the branch, commits, plan approval commit, evidence path,
unplanned changes and reasons, and verification results to cycle. Do not ask the human to approve
artifact or external steps during implementation; their acceptance is the terminal cycle boundary.
