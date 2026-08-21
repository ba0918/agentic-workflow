# Agentic Workflow

## Purpose

`WF-001` This project MUST provide a domain-independent workflow that turns an idea into an implemented and reviewed change without allowing an agent to invent missing product meaning.

`WF-002` The workflow MUST optimize for mechanically verifiable correctness before token efficiency. A cheaper configuration MUST NOT be accepted when representative fixtures show worse completion quality, serious-omission detection, or gate integrity.

`WF-003` The primary workflow MUST be:

`brainstorm -> spec -> verification and RED -> plan -> implement -> GREEN -> review -> done`

## Scope

`WF-010` The core MUST own phase transitions, common artifact states, missing-specification escalation, stopping and resumption, invalidation, human gates, review control, and domain-extension boundaries.

`WF-011` UI mockups, pixel comparison, browser execution, accessibility policy, and UX rubrics MUST remain outside the core workflow.

`WF-012` A domain-specific workflow MAY connect through the extension contract without changing core workflow logic.

## Authority

`WF-020` Brainstorm MUST be the only phase allowed to settle missing product meaning.

`WF-021` Outside brainstorm, an agent MAY identify a missing decision and explain its consequences, but MUST NOT select a value by inference.

`WF-022` Silence, lack of objection, and an agent's own proposal MUST NOT grant implementation authority.

`WF-023` An undecided item and a delegated implementation choice MUST remain distinct states.

`WF-024` After human approval, the specification MUST become the sole source of implementation truth. Brainstorm state MUST become frozen provenance rather than a second source of authority.

`WF-025` Tests, plans, implementation evidence, reviews, and approvals MUST identify the specification revision and clauses they support.

## Brainstorm

`WF-030` Brainstorm MUST derive design obligations from the requirements and MUST inspect at least state, persistence, ownership, concurrency, transactions, authentication, authorization, external systems, failure behavior, migration, security, operations, recovery, release, and irreducible human judgment when relevant.

`WF-031` The completeness check MUST expose missing decisions and MUST NOT fill them.

`WF-032` Brainstorm MUST NOT seek convergence through a sequence of narrow Yes/No questions.

`WF-033` Before authority moves to the specification, the human-facing confirmation MUST show representative scenarios, high-impact decisions, prohibitions, agent-added assumptions, rejected strong alternatives, residual risks, unresolved matters, delegated choices, downstream automation, and the boundary that requires renewed brainstorm.

`WF-034` Human confirmation MUST first invite correction of the largest mismatch and the most harmful missing scenario before asking the human to delegate the stated scope.

## Agreement State and Compaction

`WF-040` Brainstorm MUST maintain an internal append-only semantic state. A turn MUST be classified as no semantic change, add, revise, retract, or resolve.

`WF-041` A turn with no semantic change MUST NOT rewrite the stored state.

`WF-042` The state MUST distinguish agreed, delegated, undecided, forbidden, rejected, and superseded meanings with stable identities and revisions.

`WF-043` The latest checkpoint plus later semantic events MUST restore agreements, prohibitions, undecided matters, delegated authority, rejected alternatives, revision relationships, and the next unresolved topic after compaction or interruption.

`WF-044` Restoration MUST reject duplicate identities, broken references, unresolved contradictions, missing prohibitions, stale generations, and content-identity mismatches.

`WF-045` If required meaning cannot be restored, the workflow MUST reopen the affected matter and MUST NOT claim convergence.

## Decision Evidence

`WF-050` A high-impact architecture or technology choice MUST record considered alternatives, the selection, selection and rejection reasons, evidence provenance, confidence, impact, and an observable reconsideration condition.

`WF-051` Decision evidence MUST support provenance and re-evaluation but MUST NOT become a second implementation source of truth.

`WF-052` The standalone agreement-ledger and decision-journal workflows MUST NOT be required. Their necessary state and evidence functions MUST be integrated into brainstorm.

## Specification

`WF-060` Each normative specification clause MUST have a stable identity and revision.

`WF-061` The specification MUST distinguish selected behavior, allowed variation, forbidden behavior, unresolved behavior, and explicitly delegated implementation choices.

`WF-062` A blocking unresolved item MUST prevent downstream planning.

`WF-063` The specification MUST NOT silently turn a missing value into a default.

## Verification and RED

`WF-070` Each specification clause MUST be assigned the strongest appropriate verification method: property-based test, example test, static analysis, type check, state or model check, measurement, visual comparison, or human judgment.

`WF-071` Property-based testing SHOULD be preferred only when it expresses the contract faithfully.

`WF-072` A human-judgment criterion MUST remain visible and MUST block completion until its required human gate is recorded.

`WF-073` A generated check SHOULD demonstrate defect-detection power through a mutation, counterexample, known violation, or equivalent evidence when practical.

`WF-074` RED MUST occur before implementation planning.

`WF-075` RED evidence MUST reference an approved clause, fail before implementation, and fail for the expected unmet contract. An unrelated command failure MUST NOT count as RED.

## Plan

`WF-080` The canonical plan MUST be a machine-readable execution graph.

`WF-081` Each plan node MUST identify its specification clauses, verification contracts, decision dependencies, predecessor nodes, expected artifacts, write scope, required evidence, and delegated authority.

`WF-082` The human-facing plan MUST be a short change forecast that shows expected changes, expected non-changes, external effects, major risks, and completion evidence.

`WF-083` The plan MUST NOT become a second requirements proposal.

## Implementation and GREEN

`WF-090` GREEN MUST require fresh evidence for every applicable contract against the approved specification revision.

`WF-091` GREEN MUST be rejected when the specification or a generated check was weakened without renewed approval, affected checks were omitted, required human evidence is absent, or evidence belongs to an older revision.

`WF-092` Dependency-specific representations and behavior MUST remain inside their declared architecture boundary.

`WF-093` Replacing an infrastructure adapter MAY preserve domain evidence only when static dependency checks, shared contract tests, behavioral contracts, and operational contracts prove isolation.

`WF-094` Unexpectedly broad impact from a supposedly isolated change MUST be treated as an architecture failure.

## Specification Gaps and Invalidation

`WF-100` A downstream phase MAY report a specification gap but MUST return the missing meaning to brainstorm.

`WF-101` Unrelated work MAY continue only when code, behavioral, and operational dependencies prove independence from the gap. Without proof, the workflow MUST stop fully.

`WF-102` Foundational gaps, including persistence, authentication, authorization, data ownership, public interfaces, and transaction behavior, MUST default to a full stop unless independence is demonstrated.

`WF-103` A stopped workflow MUST record the missing decision, affected clauses and graph nodes, preserved evidence, stale evidence, and exact resume point.

`WF-104` An approved specification revision MUST mark every dependent check, plan node, implementation result, review, and approval stale.

## Review

`WF-110` The first review MUST create findings with stable identities, severity, required action, affected clauses, evidence, state, and resolution or supersession evidence.

`WF-111` Finding severity and required action MUST be separate fields. Supported actions MUST include automatic fix, fix and verify, human judgment, and record only.

`WF-112` Actionable BLOCK and WARN findings MUST remain open until fixed, explicitly ruled on by a human, or superseded by an approved specification revision. INFO findings SHOULD be recorded without creating a fix loop.

`WF-113` Related findings SHOULD be fixed by shared root cause in one batch.

`WF-114` Later review MUST focus on unresolved findings, the relevant fix diff, affected evidence, and new risk introduced by the fixes. It MUST NOT repeat every specialist review by default.

`WF-115` A full review MAY run again only when the change invalidates earlier review assumptions or coverage.

## Independent and Mandatory Review

`WF-120` An optional independent reviewer MUST run only when the current command carries an explicit option or the human explicitly requests it in the current interaction.

`WF-121` The grant MUST apply only to the current command, permit at most one invocation, permit no automatic retry or duplicate, and MUST NOT carry into another command or phase.

`WF-122` The workflow MUST NOT depend on an agent being able to inspect remaining model quota.

`WF-123` If an explicitly required reviewer is unavailable, the workflow MUST pause for human direction rather than continue silently.

`WF-124` Mandatory security and release reviews MUST remain separate from optional second opinions. An unavailable mandatory review MUST leave the workflow incomplete and resumable at that gate.

## Human-Facing Language and Approval

`WF-130` Machine-facing artifacts MUST use English stable identifiers, states, dependencies, and evidence references.

`WF-131` Human-facing views MUST use the current user's language and plain words.

`WF-132` The human-readable writing contract MUST be owned by `agentic-rules`, distributed through `agentic-skill-vendor`, and consumed without locally editing the vendored source.

`WF-133` The workflow MUST prove that every required clause is represented in the human-facing approval view and that every displayed item maps back to its source clauses.

`WF-134` The human MUST approve the meaning shown in the human-facing view, not claim to have read a machine-facing language they cannot understand.

`WF-135` Approval evidence MUST identify the specification revision and approval-view revision. A meaning-changing update MUST invalidate approval for the affected clauses.

`WF-136` Unnecessary internal names, paths, and states MUST be omitted from the normal human view. An unavoidable technical term MUST be explained through a concrete consequence.

## Extension Contract

`WF-140` A domain extension MAY register artifact types and validators, verification methods, common-format evidence, domain-specific human gates, invalidation dependencies, an extension version, and content identity.

`WF-141` A minimal non-UI fixture MUST demonstrate extension without changing core workflow logic.

## Migration

`WF-150` Migration MUST implement the optimized workflow directly. The legacy workflow MUST be used only as requirements, incident evidence, fixed fixtures, and comparison evidence.

`WF-151` Full compatibility with legacy command names, arguments, artifacts, and in-progress runs MUST NOT be a goal.

`WF-152` A legacy artifact MAY be converted only when its meaning is unambiguous and the conversion is validated. An ambiguous artifact MUST be rejected or returned for human re-adjudication.

## Failure and Recovery

`WF-160` An unavailable required human, reviewer, provider, piece of evidence, valid artifact, or concurrency resolution MUST produce an incomplete resumable state rather than success.

`WF-161` Failure evidence MUST identify what completed, what remains valid, what became stale, and the exact resume point.

## Cost and Quality Evaluation

`WF-170` Optimization MUST begin with fixed representative fixtures and MUST measure successful completion, known serious-omission detection, model input, review invocation count, repeated context volume, and omission-driven rework.

`WF-171` Initial numeric limits MAY be selected during implementation from measured fixtures, but MUST NOT weaken the semantic contracts in this specification.

`WF-172` Caching, context isolation, narrow tool results, and targeted rereading MAY be adopted only when measurements show that required quality is preserved.

## Required Regression Scenarios

`WF-180` The regression suite MUST stop an agent that attempts to choose JSON file persistence while persistence remains undecided.

`WF-181` The regression suite MUST preserve prohibitions and undecided matters across context compaction.

`WF-182` The regression suite MUST prove that no independent reviewer starts without current explicit authority.

`WF-183` The regression suite MUST prove that a local specification gap stops only work whose independence is demonstrated.

`WF-184` The regression suite MUST distinguish an isolated database-adapter replacement from a change that leaks storage semantics into domain behavior.

`WF-185` The regression suite MUST make affected GREEN evidence and approvals stale after a specification revision.

`WF-186` The regression suite MUST preserve unresolved review findings while targeting re-review.

`WF-187` The regression suite MUST leave an unavailable mandatory gate incomplete and resumable.

`WF-188` The regression suite MUST reject ambiguous legacy conversion.

`WF-189` The regression suite MUST integrate a domain extension without modifying the core state machine.

## Completion

`WF-190` The workflow MUST reach done only when every blocking clause has current evidence, no actionable review finding remains unresolved, every required human and policy gate is recorded, and no required artifact or approval is stale.

`WF-191` The final human-facing summary MUST state what changed, what was verified, and which non-blocking concerns remain.
