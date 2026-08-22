# Direct TDD execution

Read this reference only after bootstrap has produced `worktree-bound`. Work inside the linked
worktree. The current agent performs every action directly.

## Resolve an executable oracle

The Plan owns the semantic oracle: clauses, observable behavior, expected missing-behavior
reason, verification method, evidence, and human gates. Convert it to one executable command in
this order:

1. an explicit command in the approved Plan;
2. applicable project instructions or an existing project script;
3. one uniquely detected standard tool.

Ask before production editing if no command is available or several candidates remain. Do not
invent a command or add a dependency.

Create a candidate oracle JSON value with `version: 1`, `step_id`, `clauses`, `test_targets` as a
non-empty list of repository-relative test, fixture, and inspection-config paths, `command` as a
string array, repository-relative `cwd`, `environment_names`, bounded `timeout_seconds`,
`expected_failure_kind`, and a bounded `failure_signature`. Do not supply target identities or
`observed_failure_kind`; the helper reads the target bytes and adds their identities and its
failure classification only after execution. Never store environment values or put a secret in
the command.

The failure signature must identify the approved missing behavior. A generic runner summary such
as `FAILED (errors=1)` or a bare exit code is not a behavior signature and must not be used to
turn an import, collection, fixture, or infrastructure failure into RED evidence.

Timeout must come from project configuration or measured fixture behavior. A timeout, missing
command, dependency, import, collection, fixture, permission, network, or unrelated existing
failure is not an expected RED.

## RED

1. Run `context` for the current step.
2. Write one small test for one approved behavior before production code.
3. Save the candidate oracle under the attempt's temporary tree.
4. Run:

```text
python3 <cycle-runtime> accept-red --repo <main-checkout> --oracle <oracle-json>
```

The helper runs the command inside the linked worktree, revalidates identities after the command,
classifies the failure, freezes the oracle, and writes the RED event. Do not proceed unless the
failure is the approved missing behavior. A RED command that changes a spec is identity drift,
not a valid RED. Later GREEN, REFACTOR, staging, commit, and terminal checks recompute every
`test_targets` identity and stop if any target changed.

## GREEN

Write only the production code needed for the accepted RED. Do not change the frozen test,
fixture, command, cwd, environment names, timeout, or expected signature.

```text
python3 <cycle-runtime> run-oracle \
  --repo <main-checkout> --step step-<n> --phase green
```

The original oracle must pass. Wider project verification may be added, but never replaces or
weakens the frozen oracle. New behavior requires a new RED before more production code.

## REFACTOR

With the oracle GREEN, inspect duplication, naming, and responsibility boundaries. Refactor only
when that inspection identifies a real improvement; do not rearrange code to manufacture a
REFACTOR record.

Run the same frozen oracle afterwards, including when no code change was needed:

```text
python3 <cycle-runtime> run-oracle \
  --repo <main-checkout> --step step-<n> --phase refactor
```

## Commit

Apply the project's commit rules first and the installed global rules only as fallback. Keep one
concern per commit and never cross Plan steps. A step may contain several commits when it contains
several concerns.

1. Record `git rev-parse HEAD` as `previous_head`.
2. Ask the helper to validate and stage every intended file individually:

```text
python3 <cycle-runtime> stage \
  --repo <main-checkout> --step step-<n> \
  --path <first-file> [--path <next-file>]
```

3. Inspect staged names and diff. Exclude scope-external files, secrets, runtime files, logs,
   caches, and build output.
4. Commit directly with hooks enabled. Never use `git add .`, `git add -A`, `--no-verify`, or a
   commit subagent.
5. Record the resulting commit:

```text
python3 <cycle-runtime> record-commit \
  --repo <main-checkout> --step step-<n> --previous-head <sha>
```

Stop on a hook or commit failure, hook-produced change, or post-commit dirty state. Do not
auto-fix, restage, or retry. A sandbox permission denial is the sole exception: freeze edits,
request only the required scope, and retry the exact same staged identity once permission is
available.

## Phase 3 terminal

After every Plan step has current RED, GREEN, REFACTOR, and commit evidence, run the complete
project verification required by the Plan, then:

```text
python3 <cycle-runtime> implementation-green --repo <main-checkout>
python3 <cycle-runtime> result --repo <main-checkout>
```

Return `implementation_green` as a review hand-off. Do not call it completed, merge it, update the
Plan or locator, start review, or clean the worktree.
