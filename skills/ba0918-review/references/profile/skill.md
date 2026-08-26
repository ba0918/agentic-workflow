# Skill review profile

## Target

Apply this profile to `SKILL.md`, its references, evaluation cases and fixtures, and bundled
helpers. Include their declared inputs, outputs, side effects, completion conditions, and hand-off
to the preceding and following workflow stations.

## Dimensions

Review behavioral effectiveness, trigger and responsibility boundaries, context economy,
instruction clarity, script safety, evaluation coverage, and hand-off consistency. Verify that
each station consumes and produces the artifacts its contract promises and that the skill,
references, evaluations, helpers, and user-facing explanation retain the same meaning.

## Severity

- `security`: permits credential exposure, authority escalation, unsafe external effects, or an
  equivalent exploitable trust-boundary failure.
- `critical`: can select or build the wrong system, lose required evidence, bypass a consequential
  human decision, make completion unverifiable, or break the workflow hand-off.
- `warn`: materially weakens behavior or coverage but leaves the core workflow recoverable.
- `info`: optional clarity or maintainability improvement with no current behavioral failure.

## Allowed oracles

Use executable tests, evaluation cases, static validation or lint commands, and traceable
cross-reference checks between the skill contract and its produced/consumed artifacts. A
human-judgment oracle is allowed only when no mechanical oracle can decide the behavior; record
why it cannot be mechanized.

## Light review

Even a light review must check unsafe side effects, missing or unverifiable completion evidence,
role confusion, bypasses of consequential human decisions, evaluation coverage of the changed
behavior, and broken or meaning-changing workflow hand-offs. It collects `security` and
`critical` candidates only, but still requires the safety check and an oracle for every admitted
fixable finding; it does not collect `warn` or `info`.
