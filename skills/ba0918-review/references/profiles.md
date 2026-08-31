# Review profiles

When cycle is the caller and no profile was given, choose from changed paths: `skills/` → Skill;
`docs/` and top-level explanatory documents → Document; other source and configuration → Code.
A direct call uses the person's choice. Several kinds → every profile that applies; each finding
records which one it came from.

## Code review profile

Apply to product code, tests, configuration, and scripts. Review correctness, security and secret
handling, performance and memory, architecture and dependency direction, completeness, governing
specification conformance, and user experience when a visible interface changed.

Security and critical findings may inspect direct callers and governing specification sections.
Warn and info findings use the evaluation target as given. A mechanical test or check is the preferred oracle. Light
review still covers security, data loss, authorization, and behavior that can invalidate the
specified result.

## Document review profile

Target: specifications, plans, README files, guides, migration notes, and other explanatory
documents, including requirements, examples, commands, named files and interfaces, completion
evidence, and the hand-off to the next workflow station.

Dimensions: meaning, internal consistency, completeness, readability, interface accuracy,
verifiability, and hand-off consistency. Compare claims with changed code and current interfaces.
Look for removed commands or files still documented, changed defaults not reflected, new choices
omitted, and requirements whose verification is missing.

Severity: `security` publishes secrets or unsafe operational guidance, removes a required safety
boundary, or enables an equivalent exploitable failure. `critical` can cause the wrong system to
be built, omits a consequential decision, contradicts the governing specification, or hands an
unusable contract to the next station. `warn` is materially stale, incomplete, or ambiguous
guidance whose core intent remains recoverable. `info` is a wording, organization, or
readability improvement that changes how the text is read, with no incorrect behavior; a
meaning-preserving rewording is not a finding.

Allowed oracles: documented check commands, executable examples or tests, static link/interface
checks, and traceable cross-reference checks against specifications, implementation, and produced
artifacts. A human-judgment oracle only when meaning or readability cannot be decided
mechanically; record why.

Light review still checks contradictions capable of producing the wrong system, safety
boundaries, stale public commands or interfaces, missing verification, and a broken or
meaning-changing hand-off.

## Skill review profile

Target: `SKILL.md`, its references, and bundled helpers, including their declared inputs,
outputs, side effects, completion conditions, and hand-off to the preceding and following
workflow stations.

Dimensions: behavioral effectiveness, trigger and responsibility boundaries, context economy,
instruction clarity, and hand-off consistency. Verify that each station consumes and produces the
artifacts its contract promises and that the skill, references, and user-facing explanation retain
the same meaning.

Severity: `security` permits credential exposure, authority escalation, unsafe external effects,
or an equivalent exploitable trust-boundary failure. `critical` can select or build the wrong
system, bypass a consequential human decision, make completion unverifiable, or break the
workflow hand-off. `warn` materially weakens behavior but leaves the core workflow recoverable.
`info` is a clarity or maintainability improvement with no current behavioral failure; a
meaning-preserving rewording is not a finding.

Allowed oracles: executable tests, static validation or lint commands, and traceable
cross-reference checks between the skill contract and its produced/consumed artifacts. A
human-judgment oracle only when no mechanical oracle can decide the behavior; record why.

Light review still checks unsafe side effects, role confusion, bypasses of consequential human
decisions, and broken or meaning-changing workflow hand-offs.
