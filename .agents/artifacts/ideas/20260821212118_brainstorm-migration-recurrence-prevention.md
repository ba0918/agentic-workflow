# Brainstorm移行の要件と前回失敗の再発防止

**Created:** 2026-08-21 21:21:18
**Status:** ✅ Converged
**Tags:** `brainstorm,migration,workflow,recovery,regression`

---

## Summary

移行の最初の対象をbrainstormに限定する。広い依頼を独立した利用者価値へ分割し、
意味状態を途中保存してcompact後も復元できるようにする。利用者の言語による仕様集合と
plan readinessを整え、未合意の設計をplanへ持ち込ませない。まず利用者指定の低コストな
実process backend一つで回帰scenarioを実行し、品質を維持した完了brainstorm一件あたりの費用を測定する。

## Key Discussion Points

- 前回は広すぎる移行依頼を一つのplanへ変換し、planが共有runtime、skill分割、独自schemaなどの未合意設計を補った。
- 旧brainstormはwrap前の意味状態を会話contextだけに置くため、compactや中断で合意・禁止・未決定・委任・却下理由を失い得る。
- 旧brainstormのCONVERGED判定には、依頼の分割、source audit、実行境界、完了oracle、一回で完了できる根拠がない。
- 旧brainstormはplan作成とcycle開始まで所有し、責務境界を越えている。
- 英語の正本specとplanを日本語の要約だけで承認したため、利用者が未合意設計を直接検証できなかった。
- 旧skillの自動Codex呼び出しは、現在の明示許可時だけ一度という承認済み契約に反する。
- トークン効率は短文化ではなく、品質を満たして完了したbrainstorm一件あたりの総費用で評価する。

## Decisions & Conclusions

- 最初にbrainstormを移行し、その実測後にplanを移行する。
- 広い依頼は全体ロードマップと独立フェーズへ分け、最初の一フェーズだけを詳細化する。
- brainstorm中の意味状態を中間データとして保持し、承認後は仕様集合だけを実装上の正本とする。
- 正本spec、正本plan、ROADMAPは現在の利用者の言語で記述する。
- brainstormはplan readiness判定までを所有し、plan生成、archive、drop、cycle開始を所有しない。
- 初回実測は利用者指定の低コストな`opencode --auto` backend一つで行う。Claudeは利用可能になるまで保留し、Codexを使う場合は`gpt-5.6-luna`を明示して既定modelと`gpt-5.6-sol`を禁止する。
- 旧idea memoは自動移行せず、必要な内容だけを新しいbrainstormで再合意する。

## Open Questions

- なし。具体的な保存形式、revision表現、atomic write、backend CLI引数、validatorコマンドは、下記制約内で実装へ委任する。

## Next Steps

- 本合意を利用者の言語による正本specとROADMAPへ反映する草稿を提示する。
- 承認後、brainstormだけを対象にした小さな実装planを作る。
- 実装前に `ba0918-skill-regression` の回帰scenarioをREDとして作成する。

---

## Exit Contract

**Exit Status:** CONVERGED

### Agreements

| # | Decision | Rationale | Destination |
|---|----------|-----------|-------------|
| A1 | 広い依頼を独立した利用者価値ごとのフェーズへ分割し、人間が全体構成と最初の一フェーズを承認するまで詳細specやplanへ進まない | 前回は複数skill・複数利用者価値を一つのplanへ入れたことが失敗の起点だった | ROADMAP / spec |
| A2 | 意味状態が変わったターンの終了時に、セッション別progressへ合意・禁止・未決定・委任・却下・改訂・現在位置を保存する | wrap前のcompactや中断でも意味を復元する必要がある | spec |
| A3 | 同時更新はrevision比較で検出し、上書きや自動mergeをしない | 意味の異なる合意を機械的に混ぜると合意を捏造する | spec |
| A4 | 戦略brainstormはROADMAP、実装brainstormは仕様集合へ昇格し、承認成功後にprogressを削除する。失敗時はprogressを残す | 中間状態を第二の正本にせず、再開可能性も守るため | spec |
| A5 | 正本spec、正本plan、ROADMAPは利用者の言語で記述し、英語は安定IDなど機械識別子に限定する | 利用者が未合意設計や意味の乖離を直接検出できる必要がある | spec |
| A6 | brainstormは対話、意味状態、フェーズ分割、仕様集合、人間承認、plan readinessまでを所有する | plan生成やcycle開始まで所有した旧版は責務境界を越えていた | spec |
| A7 | second reviewerは現在の実行でflagまたは対話により明示された場合だけ最大一回起動し、許可を持ち越さず自動再試行しない | 無断起動と反復による費用増加を防ぐ | spec |
| A8 | まず利用者指定の低コストな`opencode --auto`実process backend一つでscenarioを評価する。Claudeは利用可能になるまで保留し、Codex利用時は`gpt-5.6-luna`を明示する | 費用と現在のprovider可用性を完了条件へ反映し、意図しない高額modelの起動を防ぐため | plan / tests |
| A9 | トークン効率は参考資料 `20260821171711_llm-workflow-token-efficiency.md` を入力に、一度に一施策を複数回測定し、品質を維持した完了taskあたりで評価する | 短文化や安価なmodelへの置換が品質低下とretry増加を隠すため | spec / tests |
| A10 | 旧idea memoの自動移行と後方互換を提供しない | 曖昧な旧状態を合意済みとして復元しないため | spec |
| A11 | plan前は検証契約と反例を確定し、実行可能なREDはplan後かつproduction実装前に確認する | project固有の言語・toolchainを無視した検証基盤の先行実装を防ぐため | spec |

### Undecided Items

| # | Item | Why undecided | Blocks plan? |
|---|------|---------------|--------------|
| U1 | progressの具体的なファイル形式 | 回帰fixtureと配布単位を満たす最小形を実装時に選べる | false |
| U2 | revisionと内容識別子の具体的表現 | 競合・破損検出契約を満たす範囲で実装へ委任する | false |
| U3 | Codex・Claude backendの具体的CLI引数 | 利用可能なCLIと権限を実装時に観測して決める | false |
| U4 | トークン効率の数値目標 | 基準値の実測前に数値を捏造しない | false |

### Acceptance Criteria

| # | Criterion | Verifiable? | Source |
|---|-----------|-------------|--------|
| C1 | 今回のような広い移行依頼から、全skill一括planを作らず、全体フェーズと最初の一フェーズを提示する | yes | A1 |
| C2 | 意味変更後にcompactまたはセッション中断しても、合意・禁止・未決定・委任・却下・改訂・次の論点を復元する | yes | A2 |
| C3 | 欠損、矛盾、revision逆行、重複ID、古い判断の復活を復元成功として扱わない | yes | A2, A3 |
| C4 | 同じsessionを二つのprocessが更新した場合、後発が先発を上書きせず競合として停止する | yes | A3 |
| C5 | wrapと人間承認の成功後は仕様集合またはROADMAPが正本となりprogressが除去され、失敗時はprogressが残る | yes | A4 |
| C6 | 利用者が日本語の場合、正本spec、正本plan、ROADMAPの規範的説明が日本語で生成される | yes | A5 |
| C7 | plan readinessを満たさない状態からplanを作らず、不足項目をbrainstormへ戻す | yes | A6 |
| C8 | planに未合意のruntime、保存方式、skill分割、architectureが初登場した場合、実装委任と扱わず拒否する | yes | A6 |
| C9 | 明示許可がない実行ではsecond reviewerを起動せず、許可時も最大一回で自動再試行しない | yes | A7 |
| C10 | 利用可能なbackendの結果を別々の証拠として記録し、一方の成功を他方へ流用しない。初回は`opencode --auto` backendをblocking証拠とする | yes | A8 |
| C11 | 品質基準を固定してから費用を測定し、重大な漏れまたはgate迂回が増えた最適化を棄却する | yes | A9 |
| C12 | 旧idea memoを新形式へ自動変換せず、合意済み状態としてplanへ渡さない | yes | A10 |
| C13 | projectの既存toolchainで十分な最小の検証方法を選び、PBTや独立validatorを目的なく追加しない | yes | A11 |

### Codebase Evidence

| File | Finding | Relevance |
|------|---------|-----------|
| `/home/mizumi/develop/claude-skills/skills/brainstorm/references/workflow-session.md` | session中の全file writeを禁止し、意味状態を会話contextだけに保持する | wrap前compactの復元不能 |
| `/home/mizumi/develop/claude-skills/skills/brainstorm/references/workflow-resume.md` | SummaryとOpen Questionsを主に読み、完全な意味状態を復元しない | 合意・禁止・改訂の欠落 |
| `/home/mizumi/develop/claude-skills/skills/brainstorm/references/workflow-plan.md` | exit contractのない旧memoをtitleとsummaryだけでplan化し、optionでcycleまで開始する | readiness迂回と責務超過 |
| `/home/mizumi/develop/claude-skills/skills/brainstorm/references/spec-generation.md` | AIが単一domain fileの追記先・新規作成を自律決定する | 仕様集合とproject固有構成への不適合 |
| `/home/mizumi/develop/claude-skills/skills/brainstorm/fixtures.json` | 既存8scenarioはfile choreographyとpre-wrap検出を主に検証し、compact・広域分割・複数specを扱わない | 新しい回帰scenarioが必要 |
| `/home/mizumi/develop/agentic-workflow/docs/writings/20260821171711_llm-workflow-token-efficiency.md` | 品質固定後に完了task単位の費用を測り、一度に一施策だけ比較する | トークン効率化の非規範入力 |
| `/home/mizumi/.agents/skills/ba0918-skill-regression/references/process-queue.md` | operator定義backendでscenarioを別processへ渡し、artifactをgraderが判定する | Codex・Claudeでの独立評価 |

### Routing

| Destination | Items | Action |
|-------------|-------|--------|
| Spec | A1-A10, C1-C12 | Generated at `/home/mizumi/develop/agentic-workflow/docs/spec/agentic-workflow.md` |
| ROADMAP | A1, A4, A6, A8, A9 | Updated at `/home/mizumi/develop/agentic-workflow/ROADMAP.md` |
| Plan | なし | 正本specとROADMAPの承認後、brainstorm単体のplanを別工程で作る |
| Regression scenarios | C1-C12 | median 1件とedge 2件へまとめ、実装前にREDを確認する |
