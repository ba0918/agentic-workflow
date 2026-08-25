# Core Agentic Workflow Migration

**Cycle ID:** `20260821172451`
**Started:** 2026-08-21 17:24:51
**Status:** ⚠️ Review Failed
**Implementation Base SHA:** 3e8b25abc45d886b0a4ef0723777b1e24d714f4b
**Spec:** docs/spec/agentic-workflow.md

---

## 📝 What & Why

肥大化した `claude-skills` から、仕事の進め方を担う機能をこのリポジトリへ移す。旧版をそのまま複製せず、話し合いで決めた仕様を正本とし、各工程の結果を機械で確認できる統合workflowとして作り直す。

先にbrainstormからreviewまでを一本通して動かす。その後でissue管理や並列実行などの補助workflowを接続する。これにより、旧版の高いトークン消費を再現せず、変更ごとに品質と費用を測りながら移植できる。

## 🎯 Goals

- 未決定の重要事項をLLMが勝手に補わず、必要な場所で作業を止められるcore workflowを作る。
- 仕様、検証、plan、実装結果、review、承認を同じ仕様番号で追跡できるようにする。
- 全文reviewの反復を避け、未解決の指摘と修正箇所だけを再確認できるようにする。
- compactや中断の後でも、合意と再開位置を失わないようにする。
- rulesとmetaへ移植済みの機能を重複して実装せず、UI固有workflowは今回の対象から外す。

## 👀 Human Change Forecast

| Area | Expected change |
|---|---|
| Repository foundation | Fill `PROJECT.md`, add plugin metadata, CI, local checks, contracts, skills, and evaluation trees following the two completed sister repositories. |
| Core trunk | Add integrated brainstorm, specification verification, planning, execution, review, stop/resume, and approval behavior. |
| Legacy workflow | Reuse deterministic validators and fixtures where their semantics still fit; do not preserve old command or artifact compatibility by default. |
| Existing scaffold | Keep the generated `AGENTS.md` routing shape and `agentic-skill-vendor` dependency, then add only project-specific context. |
| UI workflows | No mockup, pixel-diff, browser, accessibility, or UX implementation in this plan. |
| External repositories | A compatible `human-readable` rule update is required in `agentic-rules`, but its implementation is tracked as an explicit cross-repository prerequisite rather than silently edited here. |

Completion is demonstrated by the required regression scenarios in `docs/spec/agentic-workflow.md`, repository validation, distributable-skill validation, and measured workflow fixtures.

## 📐 Design

### Source Material

- Approved specification: `docs/spec/agentic-workflow.md`
- Human approval evidence: `.agents/artifacts/ideas/archives/20260821170053_machine-verifiable-agentic-workflow-redesign_approval-ja.md`
- Brainstorm provenance after archival: `.agents/artifacts/ideas/archives/20260821170053_machine-verifiable-agentic-workflow-redesign.md`
- Non-normative cost research: `docs/writings/20260821171711_llm-workflow-token-efficiency.md`
- Migration source revision: `claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`
- Structural references: `agentic-rules@63a5cb003a99a3937dca21d55c1e402cd7e7f539`, `agentic-meta@855f5b9351474fc435794c1839a862f27fefc6d7`

### Architecture

The repository is an integrated product. User-facing skills are thin entry adapters over one deterministic workflow core.

```text
skills/ba0918-{brainstorm,spec-verify,plan,cycle,plan-reviewer}/
  presentation and phase-specific procedure
                    |
                    v
workflow_core/
  domain/     immutable states, authority, dependencies, findings
  service/    compile, transition, invalidate, resume, aggregate
  adapter/    artifact store, command runner, clock, content identity
                    |
                    v
.agents/{artifacts,runtime,tmp,config}/
  durable evidence, host-local control, scratch, tracked policy
```

Dependency direction is `domain -> service -> adapter -> skill presentation`. Domain code has no filesystem, subprocess, network, clock, or model dependency. Adapters inject those effects.

The first release supports the integrated plugin as the product boundary. Individual thin skills must remain self-contained in prose through vendored contracts, while deterministic shared runtime code is shipped once with the integrated repository. Copy-only installation of one entry skill is not claimed until a fixture proves it.

### Canonical Contracts

Create canonical English contracts under `contracts/` and distribute their text with `agentic-skill-vendor`:

- `workflow-state.md` — phases, authority transfer, resumable failure states
- `agreement-state.md` — semantic events, revisions, compaction checkpoints
- `spec-clause.md` — normative clause identity and verification disposition
- `evidence.md` — RED, GREEN, human, review, and command evidence
- `dependency-invalidation.md` — graph edges, stale propagation, partial-stop proof
- `review-findings.md` — finding identity, severity, action, resolution
- `human-approval.md` — machine spec to plain-language view mapping and approval binding
- `extension.md` — domain verifier and human-gate integration

Conformance tests live beside a contract only when they can validate behavior without re-implementing the prose as a second authority.

### Migration Classification

| Class | Legacy skills | Treatment |
|---|---|---|
| Core rebuild | `using-workflow`, `brainstorm`, `spec-verify`, `plan`, `plan-implement`, `cycle`, `plan-reviewer` | Rebuild around the new core and clauses; preserve useful fixtures and deterministic code, not old orchestration. |
| Integrated behavior | `ledger`, `decision-journal`, `test-driven-development` | Do not port as standalone entry skills. Absorb agreement state, decision evidence, and the `ba0918-tdd` rule dependency into the trunk. |
| Core infrastructure | `artifacts`, selected `shared` contracts/scripts, `handoff` | Reduce to the artifact/runtime/tmp/config model and resumable checkpoints required by the spec. |
| Follow-up adapters | `iterate`, `issue`, `github-issue`, `parallel-cycle`, `goal-decomposition`, `goal-loop`, `loop-triage` | Port only after the core extension and state-transition contracts pass; each becomes a client of the core. |
| General work modes | `investigate`, `systematic-debugging`, `refactor`, `sweep-fix`, `problem-solving`, `doc-check`, `doc-write`, `doc-audit`, `generate-review-rules`, `commit`, `attack-review`, `codebase-review`, `review-deps`, `review-testing` | Classify and port in follow-up plans after the trunk. Reuse core evidence and gates; do not block the first vertical release. |
| Meta ownership | `context-audit`, `empirical-prompt-tuning`, `skill-improve`, `skill-interface-audit`, `skill-regression`, `skill-reviewer`, `trigger-eval` | Exclude from runtime workflow. The existing meta skills stay in `agentic-meta`; port the remaining `skill-reviewer` there under a separate plan. Consume released meta capabilities only through explicit integration. |
| Already in rules | Design, placement, secrets, TDD, testing, commit, release, delegation, verification, reuse, and scaffold norms | Exclude. Declare skill-name/version requirements; do not copy rule prose. |
| UI workflow | `brief`, `design-guide`, `design-scaffold`, `design-generate`, `design-lint`, `design-validate`, `mockup-diff` | Exclude from this plan. Preserve only a generic extension fixture. |
| Legacy migration only | `migrate-cycles-to-plans` and compatibility-only branches inside ported skills | Retire unless an unambiguous migration fixture proves continuing value. |

### Reuse Decisions

| Layer | Adopt or build | Ladder result and reason |
|---|---|---|
| Repository/package layout | Adopt | Existing sister repositories define plugin metadata, language, distribution, CI, and version invariants. |
| Shared rule distribution | Adopt | Installed `@ba0918-dev/agentic-skill-vendor` is the existing purpose-built mechanism. |
| Clause lint and traceability | Adapt | Legacy `spec-verify` has standard-library validators, schemas, trace matrix, fixtures, and tests that already cover much of WF-060 through WF-075. |
| Artifact path safety | Adapt minimally | Legacy artifact-store scripts contain useful containment and atomic-write behavior, but satellite/worktree complexity is not imported before a core fixture requires it. |
| Workflow state machine | Build | No existing component models the approved authority transfer, stale propagation, partial stop, and resumable failure semantics together. |
| Dependency graph | Build with Python standard library | The required graph operations are small, deterministic transitive closure and cycle checks; a new dependency buys little. |
| Schema validation | Start with Python standard library | Existing source validators use explicit parsers successfully; reconsider a JSON Schema package only if reused schema features make the local implementation non-trivial. |
| Test runner | Adopt | Follow sister repositories: `uv run --with pytest pytest ...`, with bytecode disabled where self-containment lint requires it. |
| Evaluation fixture contract | Adopt by versioned contract | Reuse the fixture and verdict contracts owned by `agentic-meta` rather than inventing another evaluation format. |
| Human-readable rule | Adopt externally | Update the canonical rule in `agentic-rules`, then vendor the selected version. Do not maintain a local fork. |

### Implementation Graph

```text
P1 Repository foundation and inventory
 |
 v
P2 Contracts and pure workflow core
 |
 +--> P3 Brainstorm and approval
 |
 +--> P4 Specification verification and RED
          |
          v
        P5 Plan graph
          |
          v
        P6 Execution, GREEN, invalidation, recovery
          |
          v
        P7 Review and final gates
          |
          v
        P8 Entry skills and routing
          |
          v
        P9 Follow-up workflow adapters
          |
          v
        P10 Packaging, measured acceptance, documentation
```

P3 and P4 may proceed independently after P2. Every later node consumes verified outputs rather than re-reading the whole prior conversation.

### Files to Change

```text
PROJECT.md                                      - project purpose, layout, commands, constraints
README.md                                       - installation and product overview
ROADMAP.md                                      - deferred UI and satellite migration boundaries
package.json                                    - package identity, scripts, files, version follower
bun.lock                                        - pinned development toolchain
.claude-plugin/plugin.json                      - canonical product version and identity
.claude-plugin/marketplace.json                 - plugin distribution follower
.opencode/plugins/agentic-workflow.js           - OpenCode skill registration
.github/workflows/ci.yml                        - deterministic repository gates
lefthook.yml                                    - local pre-push mirror
contracts/*.md                                  - canonical workflow protocols
contracts/*/conformance/                        - mechanically useful protocol fixtures
vendor-manifest.yaml                            - external contract origins
vendor-lock.json                                - adopted contract digests and source revisions
workflow_core/domain/*.py                       - pure immutable state and graph logic
workflow_core/service/*.py                      - workflow transitions and compilation
workflow_core/adapter/*.py                      - filesystem, process, time, artifact adapters
tests/unit/**/*.py                              - pure core tests
tests/integration/**/*.py                       - vertical trunk and failure/recovery tests
skills/ba0918-using-workflow/**                  - resident routing adapter
skills/ba0918-brainstorm/**                      - semantic decision and approval adapter
skills/ba0918-spec-verify/**                     - clause, verification, and RED adapter
skills/ba0918-plan/**                            - graph planning and human forecast adapter
skills/ba0918-plan-implement/**                  - planned TDD execution adapter
skills/ba0918-cycle/**                           - trunk orchestration adapter
skills/ba0918-plan-reviewer/**                   - finding and targeted re-review adapter
skills/ba0918-artifacts/**                       - artifact initialization and diagnosis
skills/ba0918-handoff/**                         - explicit session transfer adapter
evals/cases/core-trunk/*.yaml                    - committed behavior scenarios
evals/inputs/core-trunk/**                       - staged fixture repositories and conversations
docs/migration/skill-inventory.md                - exhaustive legacy classification with reasons
docs/migration/reuse-decisions.md                - layer-by-layer adopt/build record
docs/spec/agentic-workflow.md                    - approved normative source, updated only by re-entry
scripts/validate_repository.py                   - repository and distribution invariants
```

Follow-up adapter files are added only in P9 after their individual migration matrices are accepted.

## ✅ Tests

### Contract and domain tests

- [ ] Reject duplicate clause, event, finding, and evidence identities.
- [ ] Reject illegal authority transitions and distinguish undecided from delegated.
- [ ] Compute deterministic dependency closure and reject graph cycles.
- [ ] Mark dependent evidence stale after a clause revision while preserving proven-independent evidence.
- [ ] Reject stale generation, broken supersession, and checkpoint identity mismatch.

### Brainstorm and approval tests

- [ ] Stop the JSON-persistence regression while persistence is undecided (`WF-180`).
- [ ] Preserve agreements, prohibitions, delegations, and undecided matters across compaction (`WF-181`).
- [ ] Emit no state write for a no-semantic-change turn (`WF-041`).
- [ ] Reject convergence when a blocking decision or approval-view mapping is missing.
- [ ] Prove every required English clause appears in the user-language approval view.

### Specification and RED tests

- [ ] Adapt and retain relevant legacy `spec-verify` schema, lint, trace, and mutation fixtures.
- [ ] Select property, example, static, type, measurement, visual, or human verification without pretending unsupported evidence exists.
- [ ] Reject an unrelated command failure as RED (`WF-075`).
- [ ] Reject weakened checks or an unapproved spec revision as GREEN (`WF-091`).

### Planning and execution tests

- [ ] Require clause, verification, dependency, write-scope, authority, and evidence links on every plan node.
- [ ] Render a short human change forecast without copying the full machine plan.
- [ ] Stop fully when independence from a foundational gap cannot be proved.
- [ ] Continue an independent node while preserving the blocked dependency branch (`WF-183`).
- [ ] Distinguish an isolated database adapter replacement from leaked storage semantics (`WF-184`).
- [ ] Resume after provider, process, or artifact interruption without rerunning completed independent nodes.

### Review and authority tests

- [ ] Preserve actionable findings until fix evidence, human ruling, or spec supersession exists.
- [ ] Target re-review to unresolved findings and relevant diffs (`WF-186`).
- [ ] Reopen full review only when its prior assumptions or coverage became stale.
- [ ] Never start a second reviewer without current explicit authority (`WF-182`).
- [ ] Enforce one invocation, no retry, no duplicate, and no carry-forward.
- [ ] Leave unavailable mandatory gates incomplete and resumable (`WF-187`).

### Migration, extension, and packaging tests

- [ ] Reject or re-adjudicate ambiguous legacy artifacts (`WF-188`).
- [ ] Integrate a non-UI domain extension without changing core state logic (`WF-189`).
- [ ] Verify vendored contract digests and self-containment.
- [ ] Validate every distributed skill against the Agent Skills specification.
- [ ] Verify plugin, marketplace, and package versions agree.
- [ ] Run representative fixtures repeatedly and report quality, requests, review count, context reread, and completion cost.

## 🔧 Implementation Steps

1. **Establish the repository contract and exhaustive migration inventory (P1)**
   - Files: `PROJECT.md`, `README.md`, `ROADMAP.md`, `docs/migration/skill-inventory.md`, `docs/migration/reuse-decisions.md`, plugin metadata, CI, `lefthook.yml`, `scripts/validate_repository.py`
   - Fill the current scaffold using the completed sister repositories as structural references.
   - Record every legacy skill exactly once as core rebuild, integrated behavior, infrastructure, follow-up adapter, general mode, meta, rule, UI, or retired.
   - Record the pinned source revisions and per-layer adopt/build reasons.
   - Add failing repository-validation tests before each validator rule.

2. **Define contracts and implement the pure workflow core (P2)**
   - Files: `contracts/**`, `workflow_core/domain/**`, `workflow_core/service/**`, `tests/unit/**`, `vendor-lock.json`
   - Write conformance fixtures first for authority, state revision, dependency closure, evidence freshness, review findings, approval mapping, and extension results.
   - Implement immutable state transitions and pure graph functions with no filesystem or model access.
   - Generate vendored contract copies and verify their digests.

3. **Build brainstorm as the semantic authority and compaction-safe state owner (P3)**
   - Files: `skills/ba0918-brainstorm/**`, `workflow_core/service/agreement.py`, artifact adapter files, brainstorm integration tests, evaluation cases
   - Replace the standalone ledger with automatic semantic events and normalized checkpoints.
   - Integrate lightweight decision evidence only for high-impact choices.
   - Generate clause-mapped plain-language approval views and bind approval to both spec and view identities.
   - Make restoration failure reopen only the unrecoverable meaning.

4. **Adapt specification verification and require valid RED before planning (P4)**
   - Files: `skills/ba0918-spec-verify/**`, clause/evidence services, adapted legacy validator scripts and fixtures, mutation tests
   - Reuse proven standard-library lint and trace behavior after mapping it to the approved spec clauses.
   - Add verification dispositions for non-PBT methods and human judgment.
   - Require a known-contract failure for RED and defect-detection evidence for generated checks.
   - Do not copy the legacy dual-canon model where machine clauses could compete with the approved spec.

5. **Compile a machine plan graph and plain human forecast (P5)**
   - Files: `skills/ba0918-plan/**`, plan graph services, renderers, plan fixtures
   - Compile nodes only from approved clauses, current verification contracts, and explicit authority.
   - Validate dependencies, write scopes, evidence obligations, and forbidden overlap.
   - Render only the change forecast for human inspection; keep the canonical graph dense and English.

6. **Implement TDD execution, GREEN, stale propagation, and recovery (P6)**
   - Files: `skills/ba0918-plan-implement/**`, `skills/ba0918-cycle/**`, execution services/adapters, recovery tests
   - Invoke the installed `ba0918-tdd`, design, placement, secrets, delegation, and verification rules by name.
   - Persist command evidence and distinguish RED, GREEN, unrelated failure, stale evidence, and unavailable evidence.
   - Stop or continue by proven dependency impact, not by a hard-coded category alone.
   - Resume at the first incomplete graph node without replaying valid independent work.

7. **Implement stable findings, targeted re-review, and final gates (P7)**
   - Files: `skills/ba0918-plan-reviewer/**`, review services, review fixtures
   - Convert first-review output into stable findings with separate severity and action.
   - Batch shared root-cause fixes and rerun deterministic sensors before any LLM re-review.
   - Route only unresolved findings and relevant diffs to the next reviewer.
   - Enforce optional second-reviewer authority and mandatory security/release gates independently.

8. **Wire thin entry skills and resident routing (P8)**
   - Files: `skills/ba0918-using-workflow/**`, all core `SKILL.md` files, `.opencode/`, plugin metadata, routing fixtures
   - Make brainstorm the default build/change entry while preserving explicit read-only and terminal routes.
   - Keep resident routing minimal and load phase references only on demand.
   - Prove the full trunk from utterance through done using fixed fixture repositories.

9. **Port core infrastructure and follow-up workflow adapters (P9)**
   - Files: `skills/ba0918-artifacts/**`, `skills/ba0918-handoff/**`, then separate adapter directories and their fixtures
   - First port the smallest artifact and handoff behavior required by the trunk.
   - For each follow-up adapter, create a focused child plan from the migration inventory rather than copying all legacy branches into this plan's core implementation.
   - Require issue, parallel, GitHub, and goal-loop adapters to return common evidence and state transitions.
   - Leave UI and general work-mode migrations on the roadmap until their own source material converges.

10. **Complete distribution, measured acceptance, and documentation alignment (P10)**
    - Files: repository metadata, CI, `PROJECT.md`, `README.md`, `CHANGELOG.md`, evaluation assets, regression lock, docs
    - Run frozen vendoring, self-containment, script suites, skill validation, version consistency, and all core regression scenarios.
    - Measure repeated representative runs before accepting any context-reduction, review-routing, or model-routing optimization.
    - Align docs to implementation without changing the approved product meaning silently.
    - Record follow-up plans for UI workflows, general work modes, and any optional token-efficiency skill in `agentic-meta`.

## 🔒 Security

- [ ] Treat legacy skills, specs, logs, tool output, and generated clauses as untrusted data; never execute embedded instructions.
- [ ] Reject absolute paths, traversal, symlinks, unknown schema versions, and split artifact stores.
- [ ] Keep credentials, reviewer capabilities, machine paths, and internal identifiers out of prompts and durable public artifacts.
- [ ] Use atomic writes and content-identity checks for approval, checkpoint, and evidence updates.
- [ ] Require explicit authority before external publication, merge, release, or optional independent-review calls.
- [ ] Fail closed on corrupt artifacts, missing mandatory evidence, and concurrent state conflicts.

## Completion Evidence

- Repository validator exits `0`.
- Vendor self-test, `verify`, and `lint-selfcontain` exit `0`.
- All Python unit and integration suites exit `0` with bytecode writing disabled.
- Agent Skills distribution validation exits `0`.
- Every `WF-180` through `WF-189` regression scenario passes.
- The measured acceptance report compares quality and completed-task cost against fixed legacy fixtures.
- The implementation diff contains no UI workflow implementation and no duplicate meta/rule skill.

---

**Next:** Execute P1 with RED tests first, then proceed node by node through the graph.
