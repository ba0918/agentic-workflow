# Wrap and plan readiness

## Destination

- Promote product or workflow strategy and ordering to ROADMAP.
- Promote implementation behavior to one or more specifications following project-specific placement.
- Do not assume a one-to-one spec-plan mapping. One plan may use several specs; one spec may apply to several plans.

Before changing canonical documents, save the draft as a temporary file, present its path and content identity, and obtain explicit human approval bound to that identity. Write canonical content in the current user's language.

## Draft files

Save one draft per canonical destination with the helper at `scripts/draft.py`:

```text
python3 <draft-helper> save --repo <repo> --session-id <session-id> \
  --destination <repo-relative canonical path> < draft.md
```

The draft holds the complete future bytes of the destination — for a revision of an existing specification, the whole revised file, never a patch — and carries no header or front matter marking it as a draft. The helper writes it under `.agents/tmp/ideas/<session-id>/`, records the destination and the SHA-256 content identity of exactly those bytes, and prints the path and identity. Saving a draft is not a canonical write; the canonical specification, ROADMAP, and any other document stay untouched until publication. When a draft for that destination already exists (for example after a resumed session), pass `--replace-identity <identity-of-the-existing-file>`; the helper refuses to overwrite a draft whose identity was not named.

Present in chat only: each draft's path, identity, and destination, plus the judgment material below. Do not copy the draft text into chat, and do not offer a summary as the approval target; the human reads the file with their own viewer and, for a revision, can diff it against the current canonical file.

Always save and present the drafts before applying the plan-readiness gate. If readiness is incomplete, mark unresolved parts in the draft, present it the same way, and then stop planning with the missing items and next question.

## Judgment material

Before approval, present the representative scenarios, high-impact decisions, prohibitions, assumptions the agent added, strong rejected alternatives, remaining risks, unresolved matters, delegated matters, later automatic processing, and the boundaries where brainstorm must resume. Keep each item to its essentials and point to the place in the draft that holds the detail. This material is not the approval target; only the draft bytes identified above are.

## Approval and publication

Ask whether the drafts at those paths, with those identities, may become canonical at their destinations. Silence and a request to continue discussing are not confirmation. When the human wants a change, revise in dialogue and save a new draft; never ask them to edit the file.

After explicit approval:

```text
python3 <draft-helper> publish --repo <repo> --session-id <session-id> \
  --approve <destination>=<presented-identity> [--approve ...]
```

The helper moves every draft onto its destination only when each file still has its presented identity, parks the previous canonical bytes so that a failure part-way restores them, reads each destination back, and removes the session's draft directory only when every read-back matches. A draft the human edited after presentation fails the identity check and stays in place for the dialogue to continue. Then remove the session progress with the state helper's wrap-finishing step only after the publication succeeded.

## Pre-wrap self-review

Before saving the draft, inspect the complete current semantic state rather than only the latest exchange. Stop and continue dialogue when any of these is true:

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
