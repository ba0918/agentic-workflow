# Direct TDD execution

Read this reference only after bootstrap has produced `worktree-bound` (or `resume` has named
the step to continue from), and only for steps whose `**Completion:**` is `test`. Work inside the
linked worktree. The current agent performs every action directly.

## Resolve an executable oracle

The plan owns the semantic oracle: the specification sections it rests on, observable behavior, expected missing-behavior
reason, verification method, evidence, and human gates. Convert it to one executable command in
this order:

1. an explicit command in the approved Plan;
2. applicable project instructions or an existing project script;
3. one uniquely detected standard tool.

Ask before production editing if no command is available or several candidates remain. Stop,
without supplying the missing permission or meaning yourself, when the step needs an unapproved
network access, a new dependency, an external service operation, or a product decision the Plan
does not make.

### Candidate oracle contract

The helper validates the candidate byte-exactly. Write it as a JSON object with exactly these
ten fields and nothing else; an unknown field is rejected as `oracle_fields_invalid`.

| Field | Value |
|---|---|
| `version` | `1` |
| `step_id` | `step-<n>`, where `<n>` is the number of the `### <n>.` heading under the plan's `## Steps` section |
| `sections` | non-empty list of the specification section names this step implements, as listed under the plan's `**Target specifications:**` |
| `test_targets` | non-empty list of unique, repository-relative path strings: the test, fixture, and inspection-config files the RED depends on. Strings only; the helper reads their bytes and adds each content identity when it freezes the oracle |
| `command` | the test command as a string array, e.g. `["python3", "-m", "unittest", "tests/greeting_test.py"]` |
| `cwd` | `"."` for the linked worktree root, or a repository-relative subdirectory inside it |
| `environment_names` | list of environment variable names the command reads; names only, never values |
| `timeout_seconds` | a positive integer from project configuration or measured fixture behavior |
| `expected_failure_kind` | the literal `behavior_failure`. The helper classifies the observed failure as `import_failure`, `permission_failure`, `fixture_failure`, `network_failure`, or `behavior_failure`, and only the last one is an approved missing behavior |
| `failure_signature` | a short literal fragment of the diagnostic line the failing test will print |

Do not supply target identities or `observed_failure_kind`. Never store environment values or put
a secret in the command.

The helper accepts RED only when `failure_signature` is a substring of its bounded observation:
the last output line that mentions an assertion, import, permission, fixture, collection,
network, or connection problem, stripped and cut to 512 characters. Therefore write the signature exactly as the
runner will print it — for a `unittest` assertion such as `AssertionError: None != 'hello'`, the
signature `None != 'hello'` is right and a sentence describing the missing behavior is wrong. A
generic runner summary such as `FAILED (errors=1)` or a bare exit code is rejected, because it
cannot distinguish the approved missing behavior from an import, collection, fixture, or
infrastructure failure.

Timeout must come from project configuration or measured fixture behavior. A timeout, missing
command, dependency, import, collection, fixture, permission, network, or unrelated existing
failure is not an expected RED.

## RED

1. Run `context` for the current step.
2. Write one small test for one approved behavior before production code.
3. Save the candidate oracle as a JSON file under the execution's temporary tree.
4. Run, passing the file path (not inline JSON):

```text
python3 <implement-runtime> accept-red --repo <main-checkout> --oracle <path-to-oracle.json>
```

The helper runs the command inside the linked worktree, revalidates identities after the command,
classifies the failure, freezes the oracle, and writes the RED event. A candidate that fails
validation, or a RED that fails for another reason, writes a durable `stopped` event naming the
reason; read that reason before touching anything. Do not proceed unless the failure is the
approved missing behavior. A RED command that changes a spec is identity drift,
not a valid RED. Later GREEN, REFACTOR, staging, and commit checks recompute every
`test_targets` identity and stop if any target changed; the terminal check verifies each
step's targets as of that step's commit, so a later step may evolve the same test file.

## GREEN

Write only the production code needed for the accepted RED. Do not change the frozen test,
fixture, command, cwd, environment names, timeout, or expected signature.

```text
python3 <implement-runtime> run-oracle \
  --repo <main-checkout> --step step-<n> --phase green
```

The original oracle must pass. Wider project verification may be added, but never replaces or
weakens the frozen oracle. New behavior requires a new RED before more production code.

## REFACTOR

With the oracle GREEN, inspect duplication, naming, and responsibility boundaries. Refactor only
when that inspection identifies a real improvement; do not rearrange code to manufacture a
REFACTOR record. When nothing warrants a change, state what was inspected and why it needs none
in the hand-off instead of editing.

Run the same frozen oracle afterwards, including when no code change was needed:

```text
python3 <implement-runtime> run-oracle \
  --repo <main-checkout> --step step-<n> --phase refactor
```

## Commit

Apply the project's commit rules first and the installed global rules only as fallback. Keep one
concern per commit and never cross Plan steps. A step may contain several commits when it contains
several concerns; a test and the minimal implementation that satisfies it are one concern and may
share a commit.

1. Record `git rev-parse HEAD` as `previous_head`.
2. Ask the helper to validate and stage every intended file, naming all of them in one
   invocation; it compares the whole staged set against the paths given, so a second call
   for a further file is reported as `stage_scope_mismatch`:

```text
python3 <implement-runtime> stage \
  --repo <main-checkout> --step step-<n> \
  --path <first-file> [--path <next-file>]
```

3. Inspect staged names and diff. Exclude scope-external files, secrets, runtime files, logs,
   caches, and build output.
4. Commit directly with hooks enabled. Never use `git add .`, `git add -A`, `--no-verify`, or a
   commit subagent.
5. Record the resulting commit:

```text
python3 <implement-runtime> record-commit \
  --repo <main-checkout> --step step-<n> --previous-head <sha>
```

Stop on a hook or commit failure, or when a file the commit touched is dirty again right after
the commit (a hook rewrote what was staged). Other uncommitted files — an earlier step's
leftovers, the next step's deliverable — do not block the record; they are the next commit's
business. Do not auto-fix, restage, or retry. A sandbox permission denial is the sole
exception: freeze edits, request only the required scope, and retry the exact same staged
identity once permission is available.

When the commit succeeded but its record did not — the helper refused, the session died
between the two — the branch holds a commit the evidence does not explain. Do not rewrite the
branch. Record the commit late, under the same checks a fresh record passes (scope, frozen
test targets as of that commit, an approved deliverable, declared gates):

```text
python3 <implement-runtime> record-commit \
  --repo <main-checkout> --step step-<n> --commit <sha>
```

The event carries `recorded_late: true`. The terminal check asks only that every commit
between the base and HEAD has exactly one commit event, whatever order the events were
written in.

## Terminal hand-off

After every plan step carries the evidence its completion kind demands (for `test` steps:
current RED, GREEN, REFACTOR, and commit; see [artifacts.md](artifacts.md) for the other kinds),
run any wider project verification the plan requires (it never replaces the frozen oracle), then:

```text
python3 <implement-runtime> implementation-green --repo <main-checkout>
python3 <implement-runtime> result --repo <main-checkout>
```

Return `implementation_green` as a review hand-off. Do not call it completed, merge it, update the
Plan or locator, start review, or clean the worktree.
