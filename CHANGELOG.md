# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

A change that alters what a skill instructs — as opposed to rewording, reformatting or adding
examples — is a breaking change and is listed under `Changed` with a **BREAKING** marker.

## [Unreleased]

### Changed

- **BREAKING** `ba0918-brainstorm`, `ba0918-plan`, `ba0918-implement` — a round now asks only three kinds of question: product
  direction, preference or a trade-off that reading and trying cannot settle; a decision whose
  later change means rebuilding what was built or the data accumulated; and a point where the
  request, a sample or the records show the person cares. Whether a requirement belongs in the
  specification is still always asked, and a question that cannot be classified is asked.
  Everything else, including edge behavior the person never mentioned (boundary values, where
  combined rules split the result, rare inputs), is decided without asking and recorded under
  Delegated, one line each with what was decided and its grounds. This applies to ordinary
  rounds, ambiguous terms, scenarios, and the findings of the finishing review. When an external
  interface (command form, output, exit codes, files written) was decided without asking, the last
  round before approval shows one usage example and asks whether it is right. They are written only in the Delegated section, and
  the approval request shows every one of them. Delegated items
  decided this way start with `決定:` (`Decided:` in an English specification) and are approved
  behavior: `ba0918-plan` plans them like requirements and `ba0918-implement` builds them as
  written instead of choosing again. After upgrading,
  expect fewer questions per brainstorm and a longer Delegated section to read at approval; the
  previous version asked about every point that shaped behavior.

## [0.11.0] - 2026-11-28

### Changed

- `ba0918-iterate` — the description no longer triggers on a bare request to fix or add
  something ("one more fix", "add this too", 「ちょっと直して」「これも足して」). It now names a
  reviewed loop on a small fix or addition, matching the body, which already sent a bare "fix
  it" to a direct edit.
- `ba0918-using-workflow` — the opening no longer states that the skill is resident and read
  every turn. It applies to each new request once loaded, so it reads correctly both where it
  is kept resident and where it is loaded on demand.
- **BREAKING** `ba0918-iterate`, `ba0918-using-workflow`, `ba0918-investigate` — iterate is now
  only the entry for a small task whose one-line declaration adds review (several interdependent
  change sites, or the person asked for review). A small task that needs no review is edited
  directly by the main session, with implementation delegated only for volume, and investigate
  recommends that instead of iterate. A defect whose place and change are clear from the start
  skips investigate. In iterate, review and fixing always run in separate contexts, while the
  judgment and implementation are delegated only when their own conditions hold.
- **BREAKING** `ba0918-cycle`, `ba0918-brainstorm`, `ba0918-using-workflow` — cycle runs no
  review when the caller's one-line declaration adds none. Such a run converges on the
  per-condition verification results alone, sends an unmet or unchecked success condition to a
  fixer, ends as no progress at once (without the assumption check) when the same condition stays
  unmet twice, and creates no findings file. Its terminal report says in the body, never under
  "look here first", that no review was run and why. A resume that finds a findings file continues
  as a reviewed run whatever the declaration says. With no findings file, the merge conditions on
  "look here first" and the success conditions are judged from the report alone. Before starting
  cycle, after an approval or when the person calls it directly, the main session states the
  one-line declaration from the approval commit's scope; cycle takes it as an input and, when the
  conversation holds none as it starts, states it in the same form before its first step.
- `ba0918-cycle` — when it stops on an exposed secret, it asks the person how to revoke and
  handle it, not whether to fix it now or leave it open.

## [0.10.0] - 2026-11-27

### Added

- `ba0918-cycle` can go on to merge. When a repository's own agent instructions (`AGENTS.md`,
  `CLAUDE.md` and the like, not the person's user-scope file) say cycle merges after converging,
  cycle pushes the branch, opens a pull request with the terminal report as its body and has the
  hosting service merge it once its checks pass. It merges only when the report's "look here
  first" list is empty, every success condition is confirmed, the checks pass and the change
  touches no path a person must see (publishing or version declarations, secrets, reaching
  outside, deletions whose users cannot be listed, CI workflow files, the project's instruction
  files, and the check scripts and hook configuration they name). The setting is read from the
  merge target's copy of the instructions, so a branch cannot grant itself the merge. Otherwise it
  leaves the pull request — except that it neither pushes nor opens one when the run paused on an
  exposed secret, the diff touches secrets, or the list carries a `security` item, unless the
  project's instructions say to leave a pull request in those cases too. Cycle does not wait for the merge: when the checks are still running,
  the report says auto-merge is set and the merge waits on them. Saying "no merge this time" at the start turns it off for one run. The same
  setting applies to `ba0918-iterate`.

### Changed

- **BREAKING** `ba0918-cycle` — takes the approved specification paths and the approval commit
  instead of a plan. The requirements under the headings that commit added or changed are the
  scope, and their success conditions become part of convergence: a condition the
  specification names no verification for, or whose verification could not be run, ends the run
  as "unverified remaining". Cycle has a plan written only when the work is
  more than one implementer holds at once or a person will take over midway, goes on without
  approval, has the plan rewritten when a delegate finds it contradicts the work (ending at once
  on no progress when the same contradiction returns after the rewrite), and deletes it in a
  commit on convergence. Implement and fixers are told not to add checks, approvals or
  reviews of their own, and only a contradiction with the specification (or a file outside
  iterate's list) hands back to brainstorm. The terminal report gives each success condition's
  state, gives every provisional answer with where its evidence is, and ends with a "look here
  first" list.
- **BREAKING** `ba0918-implement` — takes the specification paths, the scope and the branch, and
  a plan path only when one was written. Without a plan it reads the scope's requirements and
  chooses the order itself, and it builds nothing outside the scope. It reports each success
  condition as confirmed with its evidence or unverified with why, lists problems found outside
  the scope without fixing them, and gives every provisional answer with where its evidence is. A
  requirement with no way to verify it no longer stops the run. When no test command is fixed, it
  picks one by reading the repository and runs it to show it works, instead of handing back. A
  contradiction with the plan goes back to cycle, not to the person; only a contradiction with the
  specification goes back to brainstorm. It adds no check, approval or review of its own.
- **BREAKING** `ba0918-plan` — no longer asks the person to approve the plan. Cycle calls it only
  when the work is too large for one implementer or a person will take over midway, and a person
  may still call it directly. It takes the specification paths, the scope when there is one, the
  work branch and its worktree path (plus the hand-back reason and the existing plan on a
  rewrite), commits the plan on that branch under the branch's name, and returns the path with its
  provisional answers, each with where its evidence is. A requirement with no qualifying test and no declared human or
  platform check no longer goes back to brainstorm: it is returned as unverified, with a proposed
  verification to add to the specification.
- **BREAKING** `ba0918-iterate` — a request whose impact cannot be read (condition 4) is now
  guided to brainstorm in every case, never to plan, and guiding to cycle is a counter-example. Its
  reading of cycle follows cycle's new inputs: the request stands in for the specification and
  scope, no plan is ever written, convergence also needs the request (and any success condition it
  touches) to be met, and the terminal report says in one line whether it was. Cycle's merge
  setting applies to iterate under the same conditions.
- **BREAKING** `ba0918-brainstorm` — a round holds only questions of product direction, preference
  and trade-off. Facts the repository or a quick run can answer are checked first and given as
  the question's background. A question every answer to which keeps the agreed behavior, and
  that is cheap to change later (a name, a small default), is decided without asking and recorded
  as delegated with its reason. Whether a requirement belongs in the specification is still
  asked, and so is anything in doubt. After approval the main session creates the branch and
  worktree and starts `ba0918-cycle` with the specification paths and the approval commit, unless
  the person said "specification only".
- **BREAKING** `ba0918-review` — when a person calls review directly, the main session fixes the
  confirmed `auto_fix` and `fix_and_verify` findings without asking, then hands over the report
  with what it fixed and the checks it ran afterwards. It does not fix when the person said to
  only look, when the target is not its own working branch, or when the target is the principles,
  the glossary or a specification. Findings that are an exposed secret, or that need an
  irreversible operation to fix, still go to the person unfixed.
- **BREAKING** `ba0918-using-workflow` — a medium or larger change always goes to brainstorm
  first, with the existing specification's path when there is one, and an approved
  specification with requirements not yet implemented goes to `ba0918-cycle`; plan is no longer
  an entry or a station declared here. A new section limits what to ask the person to an
  irreversible, privileged or dangerous operation, a spreading accident, and direction,
  preference or trade-offs that reading and trying cannot settle. It applies to work that goes
  through no skill too: obvious problems in the requested target and in what this session
  changed are fixed without asking, and problems found outside that are only reported.
- **BREAKING** `ba0918-investigate` — the recommended next action sends a medium or larger change
  to brainstorm, with the existing specification's path when there is one, and an approved
  specification with requirements not yet implemented to `ba0918-cycle`. It no longer recommends
  plan.

## [0.9.0] - 2026-10-07

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
  test tool that needs no install is used as a provisional answer. Its report returns its own
  provisional answers and the plan's, each with its overturn condition and where the rule it added
  lives, so cycle can pass them to every review.
- **BREAKING** `ba0918-cycle` — the loop stops for the person only just before an irreversible,
  privileged or dangerous operation, or on a spreading accident; a `security` finding is fixed in
  the loop unless it states an exposed secret or its fix needs such an operation. Judgments nothing
  approved settles are taken as provisional answers and reported with their overturn conditions;
  fixers hand back only on a contradiction with approved content. Before ending on no progress,
  cycle writes the assumptions the fixes shared, swaps the topmost once per run, and records the
  attempt in the findings file. A new no-progress condition stops on new findings near a fix twice
  in a row. Cycle takes optional review items and passes them, with the provisional answers so far,
  to every full and diff review. The terminal report adds provisional answers, a proposal to add
  to the specification for each rule absent from it and each rule a provisional answer added, and
  each attempt's assumptions.
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
  `ba0918-brainstorm` and `ba0918-plan` read them there by name. `ba0918-using-workflow` and the
  README's skill list use the new wording for the cases that stop the person and for implement.
  `ba0918-review` moves the optional-seat procedure to `references/optional-seats.md`, read
  only when the person lists seats; `ba0918-cycle` builds reviewer prompts by pointing at the
  review skill's reviewer setup instead of restating it; `ba0918-iterate` leaves the resume rules
  it shares with cycle to cycle's body.

## [0.8.0] - 2026-09-27

### Changed

- **BREAKING** `ba0918-review` — a full review, or a direct call, adds optional seats: reviewers
  on the quality perspective run by other models through launch means listed in the person's
  user-scope instructions. With no list nothing changes. Each seat runs in a throwaway copy of
  the worktree, is marked absent without retry when it fails, and its findings are merged like
  any other reviewer's; the report says which seats attended.
- **BREAKING** `ba0918-cycle` — takes the person's seat choice as an optional input and launches
  the optional seats itself at each full review, never at a diff review; an absent seat is not a
  failed review, and the terminal report lists attendance. `ba0918-iterate` inherits this as
  cycle's fifth optional input.

## [0.7.0] - 2026-09-24

### Changed

- **BREAKING** `ba0918-implement` — before handing back a design decision, checks whether a
  throwaway run in the worktree would answer it; such a question is a fact, settled by the smallest
  probe kept out of the commits, and only what the specification should mean is handed back.
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
- **BREAKING** `ba0918-review` — launches one reviewer by default, adding a conformance reviewer
  only when a counterpart exists and no machine check sees the match. Two reviewers are no longer
  the default, and whether a review runs at all is the caller's gate — interdependent change sites
  that let the implementation contradict itself — which cycle's first full review has already passed.
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
- **BREAKING** `ba0918-implement` — no longer invents tests that validate verification, and
  proves deletion findings by running the existing checks after removal.
- **BREAKING** `ba0918-cycle` — mechanically finalizes reviewer proposals before fixes, stops
  when visible findings cease to shrink, and supplies reviewers and fixers with the complete
  rules and evidence needed for their delegated work.
- **BREAKING** `ba0918-iterate` — follows cycle's expanded no-progress ending and its complete
  reviewer and fixer delegation rules through the cycle skill it reads.
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

- **BREAKING** `ba0918-cycle` — the loop ends after the second full review: its visible findings
  go through one more diff loop and the cycle converges. There is no third full review, and ending 3
  no longer counts consecutive full reviews. The full review now receives the findings that will not
  be fixed (open `record_only` / `human_judgment`, closed `accepted`) as known and does not raise
  them again. Resume rules are stated: round numbers continue from the inherited maximum, ending 3's
  streak resets at a new start and continues through "run more", and "run more" re-enters at
  implement when untraced plan steps remain.
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

[Unreleased]: https://github.com/ba0918/agentic-workflow/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/ba0918/agentic-workflow/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/ba0918/agentic-workflow/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/ba0918/agentic-workflow/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/ba0918/agentic-workflow/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/ba0918/agentic-workflow/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/ba0918/agentic-workflow/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/ba0918/agentic-workflow/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/ba0918/agentic-workflow/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ba0918/agentic-workflow/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ba0918/agentic-workflow/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ba0918/agentic-workflow/releases/tag/v0.1.0
