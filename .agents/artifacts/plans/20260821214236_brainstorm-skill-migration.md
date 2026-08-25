# Brainstorm skillの移行

**Cycle ID:** `20260821214236`
**Started:** 2026-08-21 21:42:36
**Status:** ✅ Complete
**Implementation Base SHA:** 51cae1d51c9880ab665d3d3b429a9c694da8a064
**Spec:** docs/spec/agentic-workflow.md

---

## 📝 What & Why

広い依頼を一つの巨大な実装計画へ変換せず、独立した利用者価値へ分けられるbrainstorm skillを作る。
対話途中の合意を保存してcompactや中断後にも復元し、利用者が読める仕様とplan readiness判定までを
安全に作れるようにする。plan生成や実装開始はこのskillへ含めない。

Source: `.agents/artifacts/ideas/20260821212118_brainstorm-migration-recurrence-prevention.md`

## 🎯 Goals

- 広い依頼から全体フェーズと、次に詳細化する一フェーズを人間の承認付きで決める。
- 合意、禁止、未決定、委任、却下、改訂、現在位置を途中保存し、安全に復元する。
- 現在の利用者の言語による仕様集合と、planへ進めるかを示すreadiness結果を作る。
- まず利用者指定の低コストな`opencode --auto` backendで回帰scenarioを実測し、品質を維持した完了task単位の費用を記録する。

## 📐 Design

### 対象

- `ba0918-brainstorm` skill単体の配布・実行
- 自然言語による対話、広い依頼の分割、pre-wrap確認
- session別progressの保存、復元、revision競合の拒否
- 戦略brainstormからROADMAP、実装brainstormから仕様集合へのwrap
- plan readiness判定と不足項目の提示
- `ba0918-skill-regression`による三つの代表scenario

### 対象外

- planの生成、更新、実装
- idea一覧、archive、drop、cycle開始
- 旧idea memoの自動変換と後方互換
- 独立したledger、decision-journal、spec-verify
- 共有runtime、plugin全体を必須とする設計、consumerのない独自metadata
- plan skill、review workflow、UI workflowの移行

### Files to Change

```text
skills/ba0918-brainstorm/
  SKILL.md                         - trigger、責務境界、workflow routing
  references/session.md            - 対話、広い依頼の分割、pre-wrap確認
  references/state.md              - 意味状態、revision、復元、競合、寿命
  references/wrap-readiness.md     - ROADMAP/specへの昇格とplan readiness
  scripts/state.py                 - session progressの決定的な検証・更新
tests/
  brainstorm_state_test.py         - state helperの観測可能な契約
evals/cases/ba0918-brainstorm/
  broad-request-decomposition.yaml - 広い依頼の分割とplan拒否
  recovery-and-conflict.yaml        - compact復元と同時更新競合
  wrap-language-readiness.yaml      - 利用者言語、wrap、progress寿命
evals/inputs/ba0918-brainstorm/     - scenarioが必要とする固定project入力
regression-lock.json                - 検証済みskill内容とscenarioの対応
```

実装中に別fileが必要になった場合、既存fileで責務を表せない根拠をplanへ記録する。
将来の差し替えだけを理由に抽象化または共有packageを追加しない。

### Key Points

- **薄い入口**: `SKILL.md`は共通workflowと参照先の選択だけを持ち、詳細は一段のreferencesへ分ける。
- **選択的な読み込み**: session進行時は`session.md`、保存・復元時は`state.md`、wrap直前だけ`wrap-readiness.md`を読む。開始時に全referenceを一括で読ませない。
- **意味状態とI/Oの分離**: 状態遷移と破損判定をpureな処理として表し、filesystem更新を境界へ閉じ込める。
- **session別progress**: `.agents/artifacts/ideas/progress/{session-id}.md`を使い、一つの`current-session.md`を正本にしない。
- **楽観的競合検出**: 読み込んだrevisionと保存直前revisionが異なる場合、上書き・自動mergeせず停止する。
- **言語境界**: 規範的なspec、plan、ROADMAPは現在の利用者の言語で作る。agentが読むskill本体と内部referenceはtoken効率のため英語にし、安定IDなどmachine識別子も英語を許可する。
- **project固有の検証**: plan前は検証契約と反例までとし、実行可能なREDはprojectの既存toolchainでproduction実装前に確認する。
- **任意reviewer**: 現在のflagまたは対話上の明示許可がある場合だけ最大一回起動し、許可を持ち越さない。
- **保存形式の委任境界**: 人間が読め、安定ID・revision・内容identity・履歴を保持できる最小形式を選ぶ。別backendや将来migrationのためだけの汎用schemaは作らない。

### Source disposition

移行元の文書をruntime依存として一括移植しない。必要な意味契約だけを次の責務へ移し、
移行しない部分を明示する。この表にない移行元契約を実装中に発見した場合は、黙って追加・破棄せず
表を更新してから扱う。

| 移行元 | 保持する契約 | 移行先 | 移行しない部分と理由 |
|--------|--------------|--------|----------------------|
| `brainstorm/references/workflow-session.md` | file-edit-freeな対話、sparring、意味決定 | `references/session.md` | 意味状態を会話contextだけに置く制約はcompact耐性がないため廃止 |
| `brainstorm/references/workflow-resume.md` | 中断後の再開、次の論点 | `references/state.md` | SummaryとOpen Questionsだけによる不完全復元は廃止 |
| `brainstorm/references/workflow-plan.md` | brainstorm終了条件とplan readiness | `references/wrap-readiness.md` | plan生成、idea操作、cycle開始はbrainstormの責務外なので移植しない |
| `brainstorm/references/spec-generation.md` | 合意を規範的な仕様集合へ昇格する | `references/wrap-readiness.md` | 単一specへの固定対応と、配置先を無条件に自律決定する挙動は廃止 |
| brainstorm内部の補助reference群 | 上記四責務に必要で、承認済みspec条項に対応する意味だけ | `SKILL.md`または三つのreference | command別の重複手順と旧file choreographyは移植しない。実装前にsource audit記録と照合する |
| shared artifact contract | 安全なproject内path、atomicな保存、競合時の非上書き、再開可能性 | `references/state.md`、`scripts/state.py` | plugin共通artifact runtimeへの依存と旧idea memo互換は移植しない |
| shared human-readable contract | 現在の利用者の言語、判断可能な情報粒度 | `references/session.md`、`references/wrap-readiness.md` | 汎用personaや他skill向け表現規則はagentic-rules所有なので複製しない |
| shared Codex invocation contract | second reviewerは現在の明示許可時だけ最大一回 | `SKILL.md` | 自動起動、許可の持越し、自動再試行は移植しない |
| `brainstorm/fixtures.json` | 既存挙動の比較材料 | 新しい三つの回帰scenario | file choreography中心の期待値は正本にせず、compact・広域分割・複数specを検証する |
| token efficiency参考文書 | 品質固定、完了task単価、再読量、一施策ずつの比較 | planの「品質と費用」と実測手順 | prompt cachingなど環境依存策は初期実装へ無条件に入れない |
| skill-regression process queue | operator定義argv、別process artifact、grader分離 | 回帰実行手順 | queue側によるargv追加とbackend間の証拠流用は認めない |

## ✅ Tests

### REDの成立条件

- [x] scenario三本がschema validationを通り、期待値が実装前に固定されている。
- [ ] `broad-request-decomposition`が、skill未実装または旧brainstormでは巨大依頼を安全に分割できず失敗する。
- [ ] `recovery-and-conflict`が、wrap前の完全復元またはrevision競合拒否を満たせず失敗する。
- [ ] `wrap-language-readiness`が、利用者言語の正本、readiness、progress寿命のいずれかを満たせず失敗する。
- [x] state helperのunit testが、production script作成前に期待した未実装理由で失敗する。

### GREENの完了条件

- [x] 広い依頼を全体フェーズへ分け、人間が最初の一フェーズを承認するまでplanへ進まない。
- [x] 意味変更turnだけがprogressを更新し、意味変更なしのturnではbytesが変わらない。
- [x] 通常のsession開始時に全referenceを一括で読むよう指示せず、現在の操作に必要なreferenceだけを選択する。
- [x] compact後に合意、禁止、未決定、委任、却下、改訂、現在位置、次の論点を復元する。
- [x] ID重複、壊れた参照、古いrevision、内容identity不一致を拒否する。
- [x] revision競合時に両方の変更を残して停止し、自動mergeしない。
- [x] wrapと承認の成功時だけprogressを除去し、失敗時は保持する。
- [x] plan readinessの全項目を満たさない場合、planを作らず不足項目を返す。
- [x] 明示許可なしにsecond reviewerを起動しない。
- [x] 旧idea memoを新形式へ自動変換しない。
- [x] 利用者指定の低コストな`opencode --auto` backendでcritical expectationがすべて通る。
- [x] Claudeは利用可能になるまで非blockingの保留とし、Codexを使う場合は`gpt-5.6-luna`を明示して既定modelと`gpt-5.6-sol`を禁止する。

### 品質と費用

- [x] 回帰実行前にcost dry-runを行い、未計測scenarioは一件実行後に費用を報告して停止する。
- [x] backendごとに入力token、出力token、request数、再読量、人間往復、完了可否を記録する。
- [x] 重大な漏れまたはgate迂回が増えた最適化を棄却する。
- [x] 一方のbackend成功を他方の証拠へ流用しない。

## 🔧 Implementation Steps

1. **回帰scenarioとstate unit testを先に固定し、REDを確認する**
   - Files: `evals/cases/ba0918-brainstorm/*.yaml`, `evals/inputs/ba0918-brainstorm/**`, `tests/brainstorm_state_test.py`
   - `ba0918-skill-regression`のschemaに従い、median一件とedge二件、各三〜七expectationを記述する。
   - critical flagはexecutorへ渡さず、期待値を結果に合わせて弱めない。
   - fixture schema validation後、未実装のskillとstate helperに対する失敗を観測する。

2. **Agent Skill標準の最小構成を作る**
   - Files: `skills/ba0918-brainstorm/SKILL.md`, `skills/ba0918-brainstorm/references/*.md`
   - `skill-creator`で標準構成を初期化し、placeholderと不要fileを除去する。
   - `SKILL.md`を500行未満のroutingと核心契約へ限定し、参照を一段に保つ。
   - skill本体と内部referenceは英語で書き、session、state、wrap/readinessの責務を分けて同じ契約を重複記載しない。
   - Source disposition表を移行元source auditと照合し、保持対象が三つのreferenceまたは入口のどこにあるか確認する。
   - 各referenceを読む条件を入口に明記し、skill開始時の一括読み込みを要求しない。

3. **意味状態の検証と競合拒否を最小helperで実装する**
   - Files: `skills/ba0918-brainstorm/scripts/state.py`, `tests/brainstorm_state_test.py`
   - 安定ID、revision、内容identity、状態種別、参照整合性を検証するpure logicを実装する。
   - filesystem境界で期待revisionを再確認し、競合時はどちらも上書きせず診断を返す。
   - project外path、symlink、secretらしい値、旧memo変換を拒否する。
   - Python標準libraryだけで実装し、新しいruntime packageまたは依存を追加しない。

4. **対話、フェーズ分割、wrap、readinessを接続する**
   - Files: `skills/ba0918-brainstorm/SKILL.md`, `skills/ba0918-brainstorm/references/session.md`, `skills/ba0918-brainstorm/references/wrap-readiness.md`
   - 広い依頼の判定、全体フェーズ提示、最初の一フェーズの人間承認を実装する。
   - 意味変更ごとにstate helperを使い、通常の会話で製品fileを編集しない。
   - 戦略brainstormはROADMAP、実装brainstormはproject契約に従う仕様集合のdraftを提示する。
   - 承認後だけ正本へ反映し、readinessを評価してprogressを除去する。

5. **localの検査をGREENにしてからskillを静的検証する**
   - Files: 上記skill、script、test、scenario files
   - state unit test、fixture schema validation、Agent Skill validatorを順に実行する。
   - `ba0918-skill-interface-audit`で副作用、失敗処理、完了条件、参照切れを確認する。
   - consumerのないmetadata、共有runtime、未宣言の外部I/Oがないことを確認する。

6. **低コストな一つの実process backendで回帰scenarioを実行する**
   - Files: `regression-lock.json`
   - process queueのoperator管理backendを使い、queueからargvを追加しない。
   - 初回は`opencode --auto` backendだけを使う。sandbox内でcommand解決または実行に失敗した場合は、推測で迂回せずsandbox外実行の承認を求める。
   - cost dry-runを行い、未計測scenarioは一件だけ実行して費用を報告してから続行判断を待つ。
   - Claudeは利用可能になるまで実行せず、Phase 1の完了条件にしない。
   - Codexを使う場合はmodelに`gpt-5.6-luna`を明示し、既定modelまたは`gpt-5.6-sol`なら実行を拒否する。
   - artifactをgraderで判定し、全critical expectationがGREENになったbackendだけ証拠を記録する。
   - 実行したbackendの成功後にregression lockを更新し、未実行backendを成功扱いしない。

7. **実測結果を反映し、Phase 1だけを完了する**
   - Files: `ROADMAP.md`, `docs/spec/agentic-workflow.md`（実装が承認済み意味と異なる場合だけbrainstormへ戻して更新）
   - 三つの回帰scenarioは変更せず、承認成功pathをPhase 1専用の独立したacceptance runとして隔離環境で実行する。
   - acceptance runでは同一run IDのもとで、progress作成、日本語draft提示、人間承認、正本更新、内容確認、progress除去の順序を証明する。progress不在だけを成功証拠にせず、承認対象と正本内容をhashで結び付ける。
   - 人間ゲートはdraftの正本反映承認一回だけとし、準備、照合、失敗分類、証拠作成は自動で行う。
   - 旧版と品質、操作、request、reference読込数、再読、tokenを比較する。
   - 旧版は`claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`とし、同一入力で新版と比較する。
   - まず低コストな契約完全性検査を行い、内容品質の実測は最後に限定する。公開挙動、安全制約、失敗時保護、補助機能を全件対応付けし、重要機能の欠落、安全違反、重大な品質劣化は即時FAILとする。
   - 正当な削除は承認済みspecの廃止、置換、責務移管を根拠とし、同等の外部契約と失敗時保護を確認する。spec外でも互換性、安全性、データ保護、brainstormの中核価値を損なう欠落は人間へ相談する。
   - 最終判定を「移行可」「修正後に再評価」「移行不可」のいずれかで記録する。
   - 実装で判明した事実だけをdocumentationへ反映し、未実測の改善を記載しない。
   - Phase 1の完了証拠を提示して停止する。Phase 2のplan移行へ自動進行しない。

## 🔒 Security

- [x] progress、scenario、reportへcredential、個人情報、内部hostnameを保存しない。
- [x] 外部backendへ渡す会話からsecretと不要なcodebase調査結果を除く。
- [x] progress pathをsession IDから安全に解決し、absolute path、traversal、symlinkを拒否する。
- [x] scenarioはfake dataだけを使い、commit対象の入力に機密情報を含めない。
- [x] skill単体が必要とするfilesystem権限と外部process呼び出しを明示する。

---

**Next:** scenarioとunit testを作成してREDを確認する。実装完了後にdocumentationを整合し、Phase 1で停止する。

## Implementation log

- 2026-08-21 22:05 JST: `state.py`未実装による期待どおりのunit test REDを確認した。
- 2026-08-21 22:08 JST: state helper 7件をGREENにし、skill入口と三つの選択的referenceを追加した。
- 2026-08-21 22:11 JST: 全状態種別を常に必須とする過剰制約を追加testのREDで検出して除去し、壊れたrevision参照の拒否を追加した。unit test 9件がGREEN。
- 2026-08-21 22:11 JST: YAML parse、3〜7 expectations、入力参照、frontmatter、参照切れ、500行制限、Python構文、diff whitespaceをlocal検証した。
- 2026-08-21 22:11 JST: `opencode/hy3-free`でmedian scenario一件を隔離directoryから実行したが、session作成前のbootstrapでexit 1。usageは0 token、$0.00、生成fileなし。回帰REDまたは成功には数えず、再試行していない。
- 2026-08-21 22:39 JST: `ba0918-skill-regression`正式schema validationとAgent Skill quick validatorがPASS。interface auditは構造INFO一件と、wrap失敗時のprogress保持を読み落とすWARN候補一件を検出し、人間承認後に修正した。
- 2026-08-21 22:39 JST: median scenarioを`opencode/hy3-free`と`opencode-go/deepseek-v4-flash`で各一件実測。freeは全reference再読と成果物不足で不合格。DeepSeekはcritical動作と選択的読み込みを満たしたが、通常対話で未承認の対話記録fileを作成したため、skill境界の不足として未完了にした。
- 2026-08-21 22:40 JST: 人間承認により、通常対話はchat応答だけを返してfileを作成・変更しない境界をskillへ追加し、median scenarioの対応expectationをcriticalへ厳密化した。当面の実測backendを`opencode-go/deepseek-v4-flash`とした。
- 2026-08-21 22:45 JST: 修正版median scenarioをDeepSeekで再実測し、全critical expectation、選択的reference読込、baseline driftなしをartifactで確認した。約19.3K input、約3.7K output、80.198秒、約$0.0076。未実行二scenarioがあるためpartial lock更新は正式に拒否され、lockは未作成。
- 2026-08-21 22:51 JST: recovery fixtureへ実progressと競合candidateを追加し、DeepSeekで一件実測。復元、RevisionConflict、現在側hash不変、candidate conflict fileを実証したが、report JSON末尾の余分なcommaによりgraderは`malformed_artifact`。約40.2K input、約5.1K output、42.645秒、約$0.0133。正式passではないため再実行待ち。
- 2026-08-21 22:55 JST: recovery scenarioを正式rerunし、grader artifactで全critical expectationのPASS、現在側progressのhash不変、candidate conflict fileの分離保存を確認した。約39.4K input、約5.4K output、60.665秒、約$0.0140。
- 2026-08-21 23:05 JST: wrap/readiness scenarioをDeepSeekで実測。plan停止、承認前の正本非更新、progress保持、second reviewer非起動は満たしたが、日本語の規範draftを提示せずcritical一件が`partial`となり正式FAIL。24,070 input、1,882 output、74.627秒、$0.010794304。skill契約修正の判断待ち。
- 2026-08-21 23:12 JST: draft提示をreadiness gateより先に行い、chat draftと正本書き込みを区別するskill契約を追加してrerun。executorは契約を読んだが、fixtureにdraft材料となる合意済み要件がなく捏造を避けたため、同じcritical expectationが`no`で正式FAIL。17,029 input、5,004 output、63.005秒、$0.007812412。expectationを維持したfixture修正の判断待ち。
- 2026-08-21 23:18 JST: fixtureへ合意済み要件を追加した実測はgrader上全critical PASSだったが、実worktreeに未承認draft fileを作成していたため手動FAIL。17,932 input、2,271 output、60.222秒、$0.00862466。承認前のfile非変更をskillとscenarioのcritical expectationへ明記した。
- 2026-08-21 23:22 JST: file非変更境界追加後のwrap/readinessをDeepSeekで再実測し、全7 expectation、baseline driftなし、worktree差分なしを確認して正式PASS。21,286 input、2,186 output、71.516秒、$0.010202292。三scenarioの成功を`regression-lock.json`へ記録した。
- 2026-08-22 01:06 JST: Phase 1専用acceptanceで承認対象hashと正本反映hashの一致、progress除去を確認した。旧版固定revisionとの同一入力比較、42契約監査、最終contract上の三scenario再実測を完了し、判定を「移行可」とした。旧版14 request/$0.023638796に対し新版5 request/$0.009712944。Phase 2へは進んでいない。
