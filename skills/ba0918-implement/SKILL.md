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
  key and its approval commit fixes the source specification versions.
- Treat Scope as expected paths. A safe ordinary omission is recorded with its reason and included;
  it is not a human gate.
- Apply secret, dangerous-path, temporary, log, generated-output, and sensitive-target checks to
  every commit, expected or not.
- During a cycle delegation, implement is the only evidence writer. Cycle records the delegation
  boundaries.
- New or changed external dependencies and missing product, persistence, architecture, permission,
  or dangerous-operation meaning return to the human. Dependencies already approved by the plan
  may be used.
- Recover helper failures, missing reconstructible records, hook failures, and a replaced RED
  inside the run. Diagnose a stalled method and change it once before returning to the human.

## Completion

Complete when every plan step has its required evidence and commit, all safety checks pass, and an
all-steps-complete event is recorded. Hand the branch, commits, plan approval commit, evidence path,
unplanned changes and reasons, and verification results to cycle. Do not ask the human to approve
artifact or external steps during implementation; their acceptance is the terminal cycle boundary.
