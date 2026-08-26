# Plan creation

Require one implementation and review unit; named committed specification paths and sections;
observable success, a counterexample, and verification; declared human boundaries; and decided or
inapplicable distribution, runtime, persistence, external I/O, permissions, and new dependencies.
Return any missing consequential meaning to brainstorm before writing.

Only two sections have a fixed machine-readable form:

````markdown
**Target specifications:**

- `docs/spec/example.md`
  - sections: `Behavior`, `Failure handling`

## Scope

```text
src/
  example.py
tests/
  example_test.py
```
````

Target paths and headings trace the approved source at the plan's approval commit. Scope is an
expected file tree used to notice and explain omissions, not an authorization list.

Each ordered step explains purpose, prerequisites, expected files, one completion kind
(`test`, `check`, `artifact`, or `external`), concrete verification, implementation choices
explicitly delegated by the specification, and stop conditions. A `check` step lists its exact
commands. Human gates are limited to irreversible operations, human-only permission, and dangerous
targets. Artifact and external acceptance belongs to cycle's terminal boundary.

Write the canonical file under `docs/plans/`, run the plan reader, then perform independent review.
Stage the converged file for human approval and commit only after explicit acceptance.
