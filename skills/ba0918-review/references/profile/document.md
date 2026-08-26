# Document review profile

## Target

Apply this profile to specifications, plans, README files, guides, migration notes, and other
explanatory documents. Include requirements, examples, commands, named files and interfaces,
completion evidence, and the hand-off to the next workflow station.

## Dimensions

Review meaning, internal consistency, completeness, readability, interface accuracy,
verifiability, and hand-off consistency. Compare claims with changed code and current interfaces.
Look for removed commands or files still documented, changed defaults not reflected, new choices
omitted, and requirements whose verification is missing.

## Severity

- `security`: publishes secrets or unsafe operational guidance, removes a required safety
  boundary, or enables an equivalent exploitable failure.
- `critical`: can cause the wrong system to be built, omits a consequential decision, contradicts
  the governing specification, or hands an unusable contract to the next station.
- `warn`: materially stale, incomplete, or ambiguous guidance whose core intent remains
  recoverable.
- `info`: optional wording, organization, or readability improvement with no incorrect behavior.

## Allowed oracles

Use documented check commands, executable examples or tests, static link/interface checks, and
traceable cross-reference checks against specifications, implementation, and produced artifacts.
A human-judgment oracle is allowed only when meaning or readability cannot be decided
mechanically; record why no mechanical oracle is sufficient.

## Light review

Even a light review must check contradictions capable of producing the wrong system, safety
boundaries, stale public commands or interfaces, missing verification, and a broken or
meaning-changing hand-off to the next station. It collects `security` and `critical` candidates
only, but still requires the safety check and an oracle for every admitted fixable finding; it
does not collect `warn` or `info`.
