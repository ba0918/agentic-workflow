# Skill profile

The review profile for skill documents. The runtime selects it for changed files under
`skills/`; `--profile` overrides the selection. When a diff mixes skill documents with other
files, each group gets its own profile and the findings stay in one set.

## Covered files

`SKILL.md`, files under a skill's `references/`, and the helper scripts under its `scripts/`.

## Viewpoints

- **SKILL.md format and entry clarity**: the frontmatter is valid; the description says when
  the skill fires; the body states its responsibility and boundary without needing another
  document first.
- **Reference loading branches**: the body says which reference to read in which situation,
  and no reference is loaded unconditionally; every referenced file exists.
- **Self-containment**: nothing in the skill points outside its own directory — no repository
  paths, no other skill's files, no document that would be absent where the skill is
  installed.
- **Helper script boundary**: what the script decides versus what the prose instructs is
  explicit; the script is invoked as documented; the prose never re-implements a validation
  the script owns.
- **Explicit non-goals**: the skill states what it does not do, and the body never instructs
  an action listed there.
- **Cross-step hand-off**: when steps of a workflow promise each other deliverables, both
  sides of each seam still agree. A planning step hands the implementing step one approved
  plan whose machine-read parts are readable; an implementing step hands the reviewing step
  its dedicated branch, commit series, and append-only evidence with a terminal completion
  event; a reviewing step hands the fixing side a findings set that only the reviewer writes,
  answered by fix commits naming finding ids in their trailers. A change on one side of a
  seam shows the matching change, or an explicit reason, on the other.

## Severity criteria

- `security`: an instruction or script change that would leak a secret, escape the worktree,
  or widen permissions.
- `critical`: an instruction that contradicts the skill's specification or breaks a hand-off
  contract, so a following step would act on wrong meaning.
- `warn`: ambiguity, drift between prose and script, or a missing branch that will misdirect
  a future session.
- `info`: an observation worth recording; never acted on automatically.

## Allowed oracle kinds

`command` (structure checks such as `bunx skills-ref validate <skill>`, link or content greps)
and `test` for script changes. Both run inside the worktree under the same safety rules as the
default profile.

## Items that run even at light level

- The **Self-containment** viewpoint over every changed skill document, the **Cross-step
  hand-off** viewpoint over every changed seam, and the safety sweep of any changed script or
  instruction (secret handling, worktree escape, permission widening). Report its completion
  as the `security_check` input of `register`.
- `security` and `critical` candidates. `warn` and `info` are not collected at light level.
