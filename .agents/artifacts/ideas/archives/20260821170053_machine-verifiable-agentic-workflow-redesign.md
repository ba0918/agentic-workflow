# Machine-Verifiable Agentic Workflow Redesign

**Created:** 2026-08-21 17:00:53
**Status:** 📋 Planned
**Tags:** `workflow`, `specification`, `verification`, `token-efficiency`, `human-gates`

---

## Summary

Migrate the workflow responsibilities from `claude-skills` into this repository by redesigning them directly for mechanical verification and lower token use. Do not reproduce the legacy runtime first. Treat legacy skills, artifacts, incidents, and token records as requirements and regression fixtures.

The target trunk is:

`brainstorm -> spec -> verification contracts and RED evidence -> plan -> implement -> GREEN evidence -> review -> done`

Brainstorm is the only phase allowed to settle missing product meaning. The approved specification becomes the implementation source of truth. Every downstream claim must have mechanical evidence when possible, or an explicit human gate when judgment cannot be reduced safely to a test.

## Key Discussion Points

- A real failure occurred when an implementation silently selected JSON file persistence for an internal account-management tool although a database was required. The workflow must stop instead of inventing a foundational decision.
- Fine-grained Yes/No questioning encourages passive approval. Human confirmation must expose representative scenarios, dangerous assumptions, rejected alternatives, residual risks, and delegated authority in plain language before authority moves downstream.
- Property-based testing is preferred for general behavioral contracts, but the verification method must match the claim. Static analysis, example tests, model checks, measurements, visual comparison, or human judgment may be more appropriate.
- Review loops are the largest recurring token cost. A review must create a stable finding set, batch related fixes, and re-review unresolved findings plus the fix diff instead of repeating a full adversarial review after every change.
- Context compaction is a normal failure boundary. The workflow must preserve semantic state incrementally without rewriting or rereading the full conversation on every turn.
- UI-specific work deserves a separate workflow. The core owns only the extension boundary through which domain-specific verification and human judgment report evidence.

## Decisions & Conclusions

- Optimize during migration. Legacy behavior is not an implementation baseline and full backward compatibility is not a goal.
- Use historical artifacts and known failures as fixed regression inputs so comparison does not require rerunning the expensive legacy workflow.
- Brainstorm owns semantic adjudication. Downstream phases may detect a specification gap but must not resolve it by inference.
- Maintain a lightweight, append-only agreement state inside brainstorm. Record only semantic changes such as agreements, prohibitions, undecided matters, delegations, revisions, and retractions.
- Do not migrate the standalone agreement-ledger skill. Compile the internal agreement state into the specification at approval time, then freeze it as provenance.
- Do not migrate the standalone decision-journal skill. Attach lightweight decision evidence to high-impact choices: alternatives, selection and rejection reasons, evidence provenance, confidence, stake, and reconsideration triggers.
- The approved specification is the sole implementation source of truth. Tests, plans, implementation evidence, reviews, and approvals must reference its clauses and version.
- Generate verification contracts before planning implementation. RED is valid only when the check fails for the intended unmet contract.
- The plan is a machine-readable execution graph. Its human view is a short change forecast, not a second proposal document.
- Permit partial continuation only when architecture, behavior, and operational dependencies prove that the unresolved item cannot affect the continuing work. Otherwise stop the whole workflow.
- Treat unexpectedly broad impact from a supposedly isolated infrastructure change as an architecture failure, not merely a reason to run more tests.
- Review findings form a persistent ledger. Fix actionable BLOCK and WARN findings, batch root-cause fixes, and target later review at unresolved findings. INFO findings are recorded by default.
- Keep finding severity separate from the required action so subjective or false-positive WARN findings can require judgment instead of automatic churn.
- An independent second reviewer is opt-in through an invocation option or an explicit conversational request. The grant applies only to the current command, allows one invocation, has no retry, and never carries forward.
- Mandatory security or release review is separate from an optional second opinion. If a mandatory gate cannot run, the workflow remains incomplete and resumable at that gate.
- Human gates must use plain language and concrete consequences. Machine-facing artifacts use English stable identifiers and structured states; human-facing views use the user's language and retain traceability to the source clauses.
- Improve the shared human-readable contract in `agentic-rules`, distribute it through `agentic-skill-vendor`, and consume it here without copying or editing the vendored rule locally.
- Keep UI mockups, pixel comparison, browser execution, accessibility policy, and UX rubrics outside this migration. The core provides only a versioned extension contract for artifacts, validators, evidence, human gates, and invalidation dependencies.
- Preserve compatibility only where conversion is safe and semantically unambiguous. Reject or require re-adjudication for ambiguous legacy artifacts rather than silently reinterpreting them.

## Open Questions

- Exact schema fields, command names, storage formats, review thresholds, and token budgets are delegated implementation decisions. They must not change the semantic contracts above and must be selected through measurable fixtures.
- The inventory that assigns each legacy skill to core workflow, UI workflow, rules, meta, or removal remains implementation preparation rather than a product decision.

## Next Steps

- Generate and approve the workflow specification in `docs/spec/`.
- Convert specification clauses into mechanically verifiable contracts and regression fixtures.
- Inventory the legacy workflow skills by responsibility before creating the implementation graph.
- Update the shared human-readable rule in `agentic-rules` and vendor the compatible version into this project.
- Establish a measured quality baseline from fixed historical fixtures before tuning token budgets or model choices.

---

## Exit Contract

**Exit Status:** CONVERGED

### Agreements

| # | Decision | Rationale | Destination |
|---|----------|-----------|-------------|
| A1 | Redesign directly for verification and token efficiency instead of reproducing the legacy runtime. | Re-running known expensive behavior would consume user quota without adding evidence; fixed historical inputs preserve comparison. | docs/spec |
| A2 | Brainstorm is the only authority for unresolved product meaning. | Downstream self-interpretation caused a real foundational persistence error. | docs/spec |
| A3 | Internal agreement state is maintained automatically during brainstorm and transfers authority to the approved spec. | Explicit side-skill invocation is easy to omit and creates competing sources of truth. | docs/spec |
| A4 | High-impact choices carry lightweight decision evidence within brainstorm. | Rejection and reconsideration conditions prevent repeated debates without retaining a heavyweight standalone journal. | docs/spec |
| A5 | The approved spec is the sole implementation source of truth and every downstream artifact is traceable to it. | Traceability permits drift detection and safe invalidation after a meaning change. | docs/spec |
| A6 | Verification contracts and valid RED evidence precede implementation planning. | Planning against executable obligations exposes omissions before implementation cost is incurred. | docs/spec |
| A7 | Partial continuation requires evidence that the continuing work is independent of the gap. | Change categories alone cannot prove impact; architecture and operational dependencies determine the safe boundary. | docs/spec |
| A8 | Reviews use a stable finding set, batched fixes, and targeted re-review. | Repeating full adversarial review causes avoidable token amplification and non-convergent loops. | docs/spec |
| A9 | Second-reviewer use is explicit, single-use, and non-retrying. | LLM quota is not observable, so implicit invocation can exhaust the user's remaining quota. | docs/spec |
| A10 | Mandatory human, security, and release gates fail closed and remain resumable. | An unavailable required reviewer or missing evidence must never be reported as success. | docs/spec |
| A11 | Human-facing confirmation uses plain language while machine-facing artifacts use stable English structure. | Human approval is meaningful only when the user can understand consequences without decoding internal terminology. | docs/spec |
| A12 | UI-specific verification is a separate workflow connected through a small core extension contract. | UI and UX require domain-specific evidence and judgment that would otherwise expand the core responsibility. | docs/spec |
| A13 | Full legacy compatibility is not a goal; only safe, unambiguous conversions are supported. | The migration exists to improve the workflow, and compatibility must not preserve the structure being replaced. | docs/spec |

### Undecided Items

| # | Item | Why undecided | Blocks plan? |
|---|------|---------------|--------------|
| U1 | Concrete schema, CLI, storage, and numeric budget choices | These are measurable implementation decisions constrained by the agreements and fixtures. | false |
| U2 | Exact legacy skill ownership inventory | It requires a read-only repository inventory before plan construction. | false |

### Acceptance Criteria

| # | Criterion | Verifiable? | Source |
|---|-----------|-------------|--------|
| C1 | A missing foundational decision, including persistence, authentication, or ownership, stops dependent implementation instead of receiving an inferred default. | yes | A2 |
| C2 | The known persistence regression rejects an attempt to select JSON file storage when persistence remains undecided. | yes | A2 |
| C3 | Every implementation task, generated check, review result, and approval identifies the specification clauses and version it supports. | yes | A5 |
| C4 | A RED transition is rejected unless the check fails for the expected unmet contract. | yes | A6 |
| C5 | A GREEN transition is rejected if the specification or its checks were weakened without a new approved specification revision. | yes | A5, A6 |
| C6 | A specification change marks dependent checks, plan nodes, implementation evidence, reviews, and approvals stale. | yes | A5, A7 |
| C7 | Partial continuation is allowed only when code, behavioral, and operational dependencies prove independence; absence of proof causes a full stop. | yes | A7 |
| C8 | Changing a well-isolated persistence adapter preserves domain contracts, while leaked storage semantics produce an architecture BLOCK. | yes | A7 |
| C9 | Review re-entry reads unresolved findings and the relevant diff rather than repeating every specialist review by default. | yes | A8 |
| C10 | Actionable findings do not disappear without fix evidence, an explicit human ruling, or a superseding specification revision. | yes | A8 |
| C11 | A second reviewer never starts without an option on the current command or an explicit current-session request. | yes | A9 |
| C12 | A second-reviewer grant permits at most one concurrent invocation, no automatic retry, and no carry-forward to another command. | yes | A9 |
| C13 | An unavailable mandatory gate results in an incomplete resumable state rather than success. | yes | A10 |
| C14 | After compaction, agreements, prohibitions, undecided matters, delegations, and their revisions are recovered from the latest checkpoint and later semantic events. | yes | A3 |
| C15 | Conversation turns with no semantic change do not rewrite the agreement state. | yes | A3 |
| C16 | The final human confirmation includes representative scenarios, high-impact decisions, model-added assumptions, rejected alternatives, residual risks, delegated authority, and the boundary that requires renewed discussion. | yes | A11 |
| C17 | Human-facing confirmation omits unnecessary internal terminology and explains unavoidable terms through concrete consequences. | no | A11 |
| C18 | The vendored human-readable rule identifies its source version and content, cannot be edited as the local source of truth, and is checked for drift. | yes | A11 |
| C19 | A minimal non-UI extension registers its artifact, verification method, evidence, human gate, dependency impact, version, and content identity without modifying core workflow logic. | yes | A12 |
| C20 | Ambiguous legacy artifacts are rejected or routed to human re-adjudication instead of being silently converted. | yes | A13 |
| C21 | Representative fixtures measure successful completion, serious omission detection, input volume, review count, and reread scope before token optimizations are accepted. | yes | A1, A8 |

### Codebase Evidence

| File | Finding | Relevance |
|------|---------|-----------|
| `AGENTS.md` | The scaffold routes design, placement, secrets, testing, delegation, release, and verification responsibilities to shared rules. | The workflow should consume shared contracts rather than duplicate them. |
| `PROJECT.md` | Project-specific purpose, commands, constraints, and glossary are still an empty scaffold. | Migration must establish the project contract before implementation. |
| `package.json` | `@ba0918-dev/agentic-skill-vendor` is already the only development dependency. | Shared rule distribution is available without inventing a new mechanism. |
| `.gitignore` | Agent artifacts, runtime state, and temporary state are separated and ignored. | The existing `.agents` direction is reusable, though schemas may change. |
| `claude-skills/skills/brainstorm` | The legacy workflow prohibits file edits during sparring and writes an idea memo only on wrap. | This explains the current compaction gap and informs incremental semantic checkpoints. |
| `claude-skills/skills/ledger` | Agreement adjudication is an explicitly invoked side workflow with its own authority model. | Its state machine is useful, but the invocation boundary and dual-source risk should not migrate. |
| `claude-skills/skills/decision-journal` | Architectural rationale is captured through a separately invoked, heavyweight case-law workflow. | Lightweight decision evidence should be integrated while retrospective case-law work remains outside the core. |
| Anthropic cost optimization cookbook | Quality baselines and evaluation must precede optimization; context reduction can reduce quality if omitted rules matter. | Token savings must be evaluated against completion quality, not token count alone. |

### Routing

| Destination | Items | Action |
|-------------|-------|--------|
| Plan | A1-A13 and C1-C21 | Create an implementation graph only after the specification and verification contracts exist. |
| Spec | A1-A13 and C1-C21 | Generated at `docs/spec/agentic-workflow.md`. |
| Docs | Token-efficiency evidence and applicability limits | Preserve a concise supporting reference based on the Anthropic source and observed review-loop costs. |
| Clauses (side line) | C1-C21 except human-judgment criterion C17 | Formalize through the future integrated specification-verification stage. |
