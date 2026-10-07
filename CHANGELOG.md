# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

A change that alters what a skill instructs — as opposed to rewording, reformatting or adding
examples — is a breaking change and is listed under `Changed` with a **BREAKING** marker.

## [Unreleased]

### Changed

- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — the loop stops for the person only just before an irreversible,
  privileged or dangerous operation, or on a spreading accident; a `security` finding is fixed in
  the loop unless it states an exposed secret or its fix needs such an operation. Judgments nothing
  approved settles are taken as provisional answers and reported with their overturn conditions;
  fixers hand back only on a contradiction with approved content. Before ending on no progress,
  cycle writes the assumptions the fixes shared, swaps the topmost once per run, and records the
  attempt in the findings file. A new no-progress condition stops on new findings near a fix twice
  in a row. Cycle takes optional review items and passes them, with the provisional answers so far,
  to every full and diff review. The terminal report adds provisional answers, rules absent from
  the specification with proposals, and each attempt's assumptions.
- **BREAKING** `ba0918-iterate` — the implementer hands back only for a file outside the
  enumeration or a contradiction with the specification, and the fixer only for the latter; a
  request found to read two ways, or a missing design judgment, during implementation is taken as
  a provisional answer and reported. A request that reads two ways at the judgment still stops at
  condition 1. Iterate takes cycle's review items input, and since each start sets a new
  comparison base, each start may try cycle's assumption check once.
- **BREAKING** `ba0918-review` — the `human_judgment` action is gone; actions are `auto_fix`,
  `fix_and_verify` and `record_only`. A finding whose fix needs a judgment about meaning carries a
  provisional answer (the answer and the person's word that would overturn it) and is fixed in the
  loop. A rule or section with no specification behind it is a deletion finding when the diff
  added it silently, left alone when the caller lists it as a provisional answer, and `record_only`
  when it predates the diff. Reviews take optional review items, and the Skill profile's
  `critical` now reads as bypassing a case that stops the person or changing approved content.
- The workflow skills are trimmed of redundant, duplicated and low-effect instructions; what they
  instruct does not change. Descriptions say when to use each skill and leave how it works to the
  body. The evidence conditions live only in `ba0918-review`'s `references/oracle-evidence.md`;
  `ba0918-brainstorm` and `ba0918-plan` read them there by name. `ba0918-review` moves the optional-seat procedure to `references/optional-seats.md`, read
  only when the person lists seats; `ba0918-cycle` builds reviewer prompts by pointing at the
  review skill's reviewer setup instead of restating it; `ba0918-iterate` leaves the resume rules
  it shares with cycle to cycle's body.

## [0.8.0] - 2026-09-27

### Changed

- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — the loop stops for the person only just before an irreversible,
  privileged or dangerous operation, or on a spreading accident; a `security` finding is fixed in
  the loop unless it states an exposed secret or its fix needs such an operation. Judgments nothing
  approved settles are taken as provisional answers and reported with their overturn conditions;
  fixers hand back only on a contradiction with approved content. Before ending on no progress,
  cycle writes the assumptions the fixes shared, swaps the topmost once per run, and records the
  attempt in the findings file. A new no-progress condition stops on new findings near a fix twice
  in a row. Cycle takes optional review items and passes them, with the provisional answers so far,
  to every full and diff review. The terminal report adds provisional answers, rules absent from
  the specification with proposals, and each attempt's assumptions.
- **BREAKING** `ba0918-iterate` — the implementer hands back only for a file outside the
  enumeration or a contradiction with the specification, and the fixer only for the latter; a
  request found to read two ways, or a missing design judgment, during implementation is taken as
  a provisional answer and reported. A request that reads two ways at the judgment still stops at
  condition 1. Iterate takes cycle's review items input, and since each start sets a new
  comparison base, each start may try cycle's assumption check once.
- **BREAKING** `ba0918-review` — a full review, or a direct call, adds optional seats: reviewers
  on the quality perspective run by other models through launch means listed in the person's
  user-scope instructions. With no list nothing changes. Each seat runs in a throwaway copy of
  the worktree, is marked absent without retry when it fails, and its findings are merged like
  any other reviewer's; the report says which seats attended.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — takes the person's seat choice as an optional input and launches
  the optional seats itself at each full review, never at a diff review; an absent seat is not a
  failed review, and the terminal report lists attendance. `ba0918-iterate` inherits this as
  cycle's fifth optional input.

## [0.7.0] - 2026-09-24

### Changed

- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — before handing back a design decision, checks whether a
  throwaway run in the worktree would answer it; such a question is a fact, settled by the smallest
  probe kept out of the commits, and only what the specification should mean is handed back.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — the fixer contract carries the same probe rule, and so does
  `ba0918-iterate`'s implementer, which uses that contract. When a finding is still present after
  a fix, the fixer receives that fix's commits and, before changing code, tests the premise that
  fix assumed; its return adds the premise with the command and output.

## [0.6.0] - 2026-09-24

### Changed

- **BREAKING** `ba0918-brainstorm` — splits specifications by responsibility and keeps each fact
  in one place, referring to others by Markdown link. One session may change several
  specifications and returns the list of paths it changed. Before writing it searches for the
  same fact and rereads the specifications that link to any heading it changes; past a 300-line
  guide it checks for mixed responsibilities. The finishing review sees only the changed
  specifications and those one link away.
- **BREAKING** `ba0918-plan` — takes the paths of several committed specifications, never
  traversing from an index. It may read the specifications they link to, one link deep, lists
  every one its steps rest on, and references them by Markdown link and heading.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — reads the specification paths the plan lists, one or more, and
  hands only those to review as the counterpart, never an index or an unrelated specification.
- **BREAKING** `ba0918-iterate` — takes several specification paths to match against, never an
  index. When none is given, whoever judges finds every specification covering the files to
  change, indexes not counted.

## [0.5.0] - 2026-09-20

### Changed

- **BREAKING** `ba0918-using-workflow` — decides how much of the workflow runs as well as where
  it starts. No station is added by default; adding one needs a one-line reason stated before
  acting, and the entry table gains a first row for editing directly. Carries the reasons for
  each station, the three things never traded away, and the four signs of outside reach.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — the loop stops for the person only just before an irreversible,
  privileged or dangerous operation, or on a spreading accident; a `security` finding is fixed in
  the loop unless it states an exposed secret or its fix needs such an operation. Judgments nothing
  approved settles are taken as provisional answers and reported with their overturn conditions;
  fixers hand back only on a contradiction with approved content. Before ending on no progress,
  cycle writes the assumptions the fixes shared, swaps the topmost once per run, and records the
  attempt in the findings file. A new no-progress condition stops on new findings near a fix twice
  in a row. Cycle takes optional review items and passes them, with the provisional answers so far,
  to every full and diff review. The terminal report adds provisional answers, rules absent from
  the specification with proposals, and each attempt's assumptions.
- **BREAKING** `ba0918-iterate` — the implementer hands back only for a file outside the
  enumeration or a contradiction with the specification, and the fixer only for the latter; a
  request found to read two ways, or a missing design judgment, during implementation is taken as
  a provisional answer and reported. A request that reads two ways at the judgment still stops at
  condition 1. Iterate takes cycle's review items input, and since each start sets a new
  comparison base, each start may try cycle's assumption check once.
- **BREAKING** `ba0918-review` — launches one reviewer by default, adding a conformance reviewer
  only when a counterpart exists and no machine check sees the match. Two reviewers are no longer
  the default, and whether a review runs at all is the caller's gate — interdependent change sites
  that let the implementation contradict itself — which cycle's first full review has already passed.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — runs a second full review only when a fix could spread beyond
  where it was made, and delegates nothing the caller's reason did not name.
- **BREAKING** `ba0918-iterate` — judges the four small-task conditions in the main session,
  delegating a judge only when the impact enumeration cannot be closed, and implements in the
  main session when delegated implementation was not named.
- **BREAKING** `ba0918-plan` — reviews the plan only when its steps can contradict each other.
- **BREAKING** `ba0918-brainstorm` — reviews the specification only when its requirements can
  contradict each other.

## [0.4.0] - 2026-09-03

### Changed

- **BREAKING** `ba0918-brainstorm` — asks where non-product requirements belong, rejects or
  reclassifies unverifiable requirements, and carries the versioned evidence conditions.
- **BREAKING** `ba0918-plan` — names only tests that qualify as evidence, avoids tests for
  already-established conditions, returns unverifiable requirements, and carries the versioned
  evidence conditions.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — no longer invents tests that validate verification, and
  proves deletion findings by running the existing checks after removal.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — mechanically finalizes reviewer proposals before fixes, stops
  when visible findings cease to shrink, and supplies reviewers and fixers with the complete
  rules and evidence needed for their delegated work.
- **BREAKING** `ba0918-iterate` — follows cycle's expanded no-progress ending and its complete
  reviewer and fixer delegation rules through the cycle skill it reads.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — the loop stops for the person only just before an irreversible,
  privileged or dangerous operation, or on a spreading accident; a `security` finding is fixed in
  the loop unless it states an exposed secret or its fix needs such an operation. Judgments nothing
  approved settles are taken as provisional answers and reported with their overturn conditions;
  fixers hand back only on a contradiction with approved content. Before ending on no progress,
  cycle writes the assumptions the fixes shared, swaps the topmost once per run, and records the
  attempt in the findings file. A new no-progress condition stops on new findings near a fix twice
  in a row. Cycle takes optional review items and passes them, with the provisional answers so far,
  to every full and diff review. The terminal report adds provisional answers, rules absent from
  the specification with proposals, and each attempt's assumptions.
- **BREAKING** `ba0918-iterate` — the implementer hands back only for a file outside the
  enumeration or a contradiction with the specification, and the fixer only for the latter; a
  request found to read two ways, or a missing design judgment, during implementation is taken as
  a provisional answer and reported. A request that reads two ways at the judgment still stops at
  condition 1. Iterate takes cycle's review items input, and since each start sets a new
  comparison base, each start may try cycle's assumption check once.
- **BREAKING** `ba0918-review` — checks conformance in both directions, proposes deleting
  verification that does not qualify as evidence, carries the versioned evidence conditions, and
  requires every reviewer prompt to carry both-way conformance and the complete finding rules.

## [0.3.0] - 2026-09-01

### Added

- `ba0918-using-workflow` — decides which skill a new request enters from: a small task goes
  to iterate, a medium-or-larger change to brainstorm (or to plan then cycle when a
  specification exists), and an unexplained defect or a question needing file reading to
  investigate. Questions answerable in conversation and chat are answered directly instead of
  being routed. Written to stay resident and be read every turn; how to keep it resident is in
  the README.

## [0.2.0] - 2026-09-01

### Changed

- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — the loop ends after the second full review: its visible findings
  go through one more diff loop and the cycle converges. There is no third full review, and ending 3
  no longer counts consecutive full reviews. The full review now receives the findings that will not
  be fixed (open `record_only` / `human_judgment`, closed `accepted`) as known and does not raise
  them again. Resume rules are stated: round numbers continue from the inherited maximum, ending 3's
  streak resets at a new start and continues through "run more", and "run more" re-enters at
  implement when untraced plan steps remain.
- **BREAKING** `ba0918-plan` — a judgment the specification does not make (a new input kind, an
  acceptance boundary, error handling) is written into the plan as a provisional answer and shown
  with its overturn condition among the approval's judgment points, instead of going back to
  brainstorm. Plan-review findings that need a decision are fixed the same way; only a fix that
  would contradict the approved specification goes back. A requirement with no qualifying test and
  no declared human or platform check still goes back to brainstorm. `ba0918-brainstorm` states
  that specification silence is its own rule for writing, and that a term drift found after
  approval goes to the next brainstorm.
- **BREAKING** `ba0918-implement` — a judgment the plan and specification do not settle no longer
  stops the run: the implementer takes the answer with the strongest grounds, goes on, and reports
  it with its overturn condition. It stops for the person only on a confirmation the plan asks for,
  a spreading accident, or an irreversible, privileged or dangerous probe, and hands back upstream
  only on a contradiction with approved content or when no test command can be determined. When a
  step makes no progress after one changed approach, it writes the assumptions its attempts shared,
  swaps the topmost once, and hands back with them only if that fails too. An ecosystem's standard
  test tool that needs no install is used as a provisional answer.
- **BREAKING** `ba0918-cycle` — the loop stops for the person only just before an irreversible,
  privileged or dangerous operation, or on a spreading accident; a `security` finding is fixed in
  the loop unless it states an exposed secret or its fix needs such an operation. Judgments nothing
  approved settles are taken as provisional answers and reported with their overturn conditions;
  fixers hand back only on a contradiction with approved content. Before ending on no progress,
  cycle writes the assumptions the fixes shared, swaps the topmost once per run, and records the
  attempt in the findings file. A new no-progress condition stops on new findings near a fix twice
  in a row. Cycle takes optional review items and passes them, with the provisional answers so far,
  to every full and diff review. The terminal report adds provisional answers, rules absent from
  the specification with proposals, and each attempt's assumptions.
- **BREAKING** `ba0918-iterate` — the implementer hands back only for a file outside the
  enumeration or a contradiction with the specification, and the fixer only for the latter; a
  request found to read two ways, or a missing design judgment, during implementation is taken as
  a provisional answer and reported. A request that reads two ways at the judgment still stops at
  condition 1. Iterate takes cycle's review items input, and since each start sets a new
  comparison base, each start may try cycle's assumption check once.
- **BREAKING** `ba0918-review` — a rewording that leaves the reader's meaning unchanged is no longer
  a finding, not even `info`; `info` is reserved for changes that alter how the text is read. Full
  reviews receive the known findings.
- **BREAKING** `ba0918-iterate` — ending 3's streak no longer counts consecutive full reviews,
  following cycle; its resume rules are now cycle's own rather than an exception. At the decision
  on the judge's verdict, a test file the implementer needs test-first but the enumeration lacks
  is added to the enumeration, and the person-set round-trip limit counts this run's reviews from
  when it was set — both now stated in the specification.
- **BREAKING** `ba0918-investigate` — the brainstorm row of the recommendation table now applies
  to medium-or-larger changes with no specification, so a small task without one goes to iterate;
  fix options are counted per problem, not per report; and the read-only guarantee copied into
  subagent prompts carries the conditions for running tests.

### Fixed

- README — the `gh skill install` command now passes `--all`; without it the command prompts for
  a skill selection and installs nothing when no terminal is attached.

## [0.1.0] - 2026-08-31

### Added

- `ba0918-brainstorm` — interviews the person in numbered question rounds, each question
  carrying a recommended answer, defines terms and boundary scenarios on the spot, and writes
  the specification once shared understanding is complete. The specification goes through an
  adversarial review and a staged approval before it is handed on.
- `ba0918-plan` — turns an approved specification into one Markdown plan that an implementer
  with no prior context can execute. Steps reference specification sections instead of copying
  them, and each step names its completion evidence and its stop conditions.
- `ba0918-cycle` — a small orchestrator that takes a plan and a branch, delegates
  implementation, review and fixing to separate-context agents, and loops full review → diff
  loop → full review until the findings converge, then hands the result to the person once.
- `ba0918-implement` — executes a plan step by step, test-first for code, committing one
  concern at a time, and hands back instead of guessing when a design decision is missing.
- `ba0918-review` — adversarial review of a diff or a document set by separate-context
  reviewers that return findings as JSON and never edit. Called by cycle inside its loop, and
  callable on its own for a codebase diagnosis or a full review.
- `ba0918-iterate` — an entry point beside the workflow for a task too small to need a
  specification or a plan: a separate-context judge proposes whether the request is small,
  the skill decides, and cycle's loop then runs on the request; anything bigger is turned away
  with the next skill to call.
- `ba0918-investigate` — read-only investigation from a symptom or a question to the direct
  cause, the root cause, the impact and whether tests cover it, reported with fix options and
  without changing a file.
- Install routes for Claude Code and Codex CLI (plugin marketplace), OpenCode (plugin), APM
  (package manager), and `gh skill` / `npx skills` (copy).

[Unreleased]: https://github.com/ba0918/agentic-workflow/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/ba0918/agentic-workflow/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/ba0918/agentic-workflow/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/ba0918/agentic-workflow/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/ba0918/agentic-workflow/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/ba0918/agentic-workflow/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ba0918/agentic-workflow/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ba0918/agentic-workflow/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ba0918/agentic-workflow/releases/tag/v0.1.0
