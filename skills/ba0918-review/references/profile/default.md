# Default profile

The review profile for general code. The runtime selects it for every changed file that no
other profile covers; `--profile` overrides the selection.

## Covered files

Production code, tests, configuration, and documents no other profile covers. This profile
declares no `Covers:` line: it is the fallback.

## Viewpoints

- **Correctness**: the change does what its plan step promises; edge cases and error paths
  return the decided results; no behavior outside the approved scope changed.
- **Safety**: inputs are validated at the boundary; paths stay inside the repository or the
  bound worktree; secrets never reach code, evidence, logs, or command lines; nothing widens
  permissions or reaches the network without the plan saying so.
- **Performance and memory**: no unbounded reads, loops, or accumulation over inputs the plan
  says can grow; expensive work is not repeated inside loops without a reason.
- **Design**: responsibilities stay separated as the surrounding module does it; no logic in
  glue code; dependencies point one way; no duplication of an existing helper.
- **Coverage**: every behavior the plan step names has a test that fails without the change;
  tests assert behavior, not mocks or internals.
- **Conformance to the specification**: observable behavior matches the sections the plan
  cites; nothing implements meaning the specification does not decide.
- **Usability**: when the change has a human-facing surface, messages state what happened and
  what to do next, in the reader's language.

## Severity criteria

- `security`: a secret, injection, traversal, or permission problem someone could exploit.
- `critical`: the promised behavior is wrong, data is lost, or evidence becomes untrustworthy.
- `warn`: works, but a defect in design, coverage, or robustness that will cost later.
- `info`: an observation worth recording; never acted on automatically.

## Allowed oracle kinds

`test` (a test module the runtime runs as `python3 -m unittest <module>`) and `command` (a
command that exits 0 when the finding is fixed). On a project whose tests use another runner,
write the runner invocation as a `command` oracle instead of a `test` one. Both run inside the
worktree; absolute paths, parent-directory references, and credential-shaped values are
refused, in bare arguments and inside inline payloads (such as a `python3 -c` string) alike.
This vetting is a surface scan, not a sandbox: it stops accidents, not deliberate
obfuscation. Review examines the user's own implementation with a reviewer the human chose,
every oracle command stays visible in the frozen record, and the human who freezes the set
is the last guard.

## Items that run even at light level

- The **Safety** viewpoint over the whole diff: secret-shaped values, injection, traversal,
  permission or network widening. Report its completion as the `security_check` input of
  `register`; without it the findings set is not fixed.
- `security` and `critical` candidates anywhere in the diff. `warn` and `info` are not
  collected at light level.
