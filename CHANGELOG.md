# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

A change that alters what a skill instructs — as opposed to rewording, reformatting or adding
examples — is a breaking change and is listed under `Changed` with a **BREAKING** marker.

## [Unreleased]

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
- **BREAKING** `ba0918-review` — checks conformance in both directions, removes verification
  that does not qualify as evidence, carries the versioned evidence conditions, and requires
  every reviewer prompt to carry both-way conformance and the complete finding rules.

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

[Unreleased]: https://github.com/ba0918/agentic-workflow/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ba0918/agentic-workflow/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ba0918/agentic-workflow/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ba0918/agentic-workflow/releases/tag/v0.1.0
