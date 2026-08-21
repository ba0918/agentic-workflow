# Wrap and plan readiness

## Destination

- Promote product or workflow strategy and ordering to ROADMAP.
- Promote implementation behavior to one or more specifications following project-specific placement.
- Do not assume a one-to-one spec-plan mapping. One plan may use several specs; one spec may apply to several plans.

Before changing canonical documents, show the draft and destination and obtain explicit human approval. Write canonical content in the current user's language.

Always show the proposed normative draft and its destination before applying the plan-readiness gate. If readiness is incomplete, mark unresolved parts in the draft, present it only in the chat response, and then stop planning with the missing items and next question. Do not create or edit a draft file before approval. Showing a draft in chat is not a canonical write and does not require prior approval; writing any draft or canonical document to the filesystem does.

## Pre-wrap self-review

Before presenting the draft, inspect the complete current semantic state rather than only the latest exchange. Stop and continue dialogue when any of these is true:

- a placeholder, contradiction, ambiguous normative term, or unstated scope boundary remains;
- persistence, lifetime, ownership, concurrency, transaction boundaries, authorization, external systems, failure behavior, migration, security, operations, recovery, or release semantics materially affect the phase but are missing;
- a decision was silently inferred instead of recorded as agreed, delegated with a reason, or undecided with an owner;
- the observable success, counterexample, verification method, or required human gate is incomplete.

Repeat this review after every material draft revision. There is no forced exit that bypasses a blocker.

## Plan readiness

Require all of the following:

- approved user value, scope, exclusions, and constraints for this phase;
- no contradiction among agreements, prohibitions, undecided/delegated matters, rejected options, and revisions;
- sufficient project and source investigation, with remaining unknowns explicit;
- an observable success condition;
- at least one known failure or counterexample;
- the smallest adequate verification method for the project's language and existing toolchain;
- human approval of the specification set or ROADMAP.

If anything is missing, do not create a plan. Return the missing items and the next single question. Executable RED is not required before planning; create it after plan approval and before production implementation.

On successful completion, give the human a compact summary of what canonical content changed, how the result was verified, and any remaining non-blocking matter. Do not report completion when the approval, write, verification, or progress cleanup evidence is missing.
