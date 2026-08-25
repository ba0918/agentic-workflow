# Cycle skillの移行修正

**Plan ID:** `20260822143915`  
**Plan revision:** `3`  
**作成日時:** 2026-08-22 19:50:24 JST  
**置換対象:** revision 2 `.agents/artifacts/plans/20260822143915_cycle-skill-migration-r2.md`（`sha256:f5116456abf1bb86b1f4087366ac56a1b7ac81e677d9c6a5f27efa77b736fc04`）  
**公開先:** `.agents/artifacts/plans/20260822143915_cycle-skill-migration-r3.md`

**対象仕様:**

- `docs/spec/agentic-workflow.md`
  - 内容identity: `sha256:bf8964ceb45b18cf04c890619d73eec098d52bd8b4a37fcbd4f721a2286f5c59`
  - 適用条項: `WF-001`〜`WF-003`、`WF-020`〜`WF-025`、`WF-060`〜`WF-075`、`WF-080`〜`WF-085`、`WF-089`〜`WF-094`、`WF-100`〜`WF-104`、`WF-130`〜`WF-136`、`WF-150`〜`WF-152`、`WF-160`〜`WF-161`、`WF-170`〜`WF-174`、`WF-180`〜`WF-181`、`WF-183`、`WF-185`、`WF-187`〜`WF-188`、`WF-190`〜`WF-191`、`WF-204`〜`WF-205`、`WF-207`
- `docs/spec/plan-skill-migration.md`
  - 内容identity: `sha256:014e3a631cd8e697c46027b84d8d6bf683045b18dfd1e97f95f13eedc6fb17b9`
  - 適用条項: `PL-010`、`PL-020`〜`PL-026`、`PL-040`〜`PL-042`、`PL-050`〜`PL-056`、`PL-060`〜`PL-064`、`PL-070`〜`PL-071`
- `docs/spec/cycle-skill-migration.md`
  - 内容identity: `sha256:bafb3c45c11cfa549b452eeedb7eab3c4322412036ab3892251b599215820c6e`
  - 適用条項: `CY-000`〜`CY-004`、`CY-010`〜`CY-013`、`CY-020`〜`CY-025`、`CY-030`〜`CY-034`、`CY-040`〜`CY-043`、`CY-050`〜`CY-057`、`CY-060`〜`CY-065`、`CY-070`〜`CY-073`、`CY-080`〜`CY-083`、`CY-090`〜`CY-102`、`CY-110`〜`CY-117`

**実装境界資料:**

- `ROADMAP.md`: `sha256:d396cd90126aaddbbcad10574b7c417d20f1b074845298654dfbbc9dc353752e`
- 追加合意: `.agents/artifacts/ideas/20260822194546_cycle-test-evidence-availability.md`
- 追加仕様commit: `3734958cd341d6221a55e055c2a2a1d7c6211097`
- 移行元: `claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`
- 継続branch: `cycle/20260822143915-implementation`
- 継続元HEAD: `d4335c69825f7791a4a23be6732effc853861ebb`
- 専用worktree: `.agents/tmp/worktrees/20260822143915-cycle`

## 目的

承認済みplanを専用branchとlinked worktreeでTDD実装する`ba0918-cycle`を完成させる。凍結したtestを弱められないこと、未記録commitを隠せないこと、権限取得後に同じ操作だけを再試行できること、予定済みの人間判断だけを対象identity付きで通せることを機械的に保証する。

revision 3では、test runnerが件数を構造化して返せない場合に偽のpass、fail、skip件数を作らず、取得不能と理由を証拠へ残す。また、Plan skillがHuman gate宣言を実際に生成できるよう、作成指示を実装scopeへ追加する。

Cycleの責務はTDD実装、immutable evidence、step単位commit、Phase 4への引渡しまでとする。review、fix loop、Recovery、resume、cleanup、mergeは持たせない。

## 利用者が得る結果

- REDで凍結したtest、fixture、設定、commandを変更してもGREENとして受理されない。
- baseからHEADまでのcommit列と変更pathが証拠と一致しなければ完了しない。
- sandbox権限不足は終端failureと区別され、許可後に同じidentityの操作だけを再試行できる。
- test件数は取得できた事実だけを保存し、取得不能時も合否の中核証拠を失わない。
- Planに宣言したHuman gateだけが、現在の対象identityに対する承認で境界を通過できる。
- 正常系と停止系を実processで検証し、旧Cycleとの同一入力比較で重大な品質劣化を検出できる。

## 変更するもの

```text
skills/ba0918-plan/
  references/
    creation.md
  scripts/
    plan_artifact.py

skills/ba0918-cycle/
  SKILL.md
  references/
    execution.md
    tdd.md
    evidence.md
  scripts/
    execution_model.py
    cycle_runtime.py

tests/
  plan_artifact_test.py
  cycle_execution_model_test.py
  cycle_runtime_test.py

evals/cases/ba0918-cycle/
  complete-approved-plan.yaml
  stop-on-spec-drift.yaml
  reject-unintended-red.yaml
  reject-weakened-test.yaml

evals/inputs/ba0918-cycle/
  （上記scenarioの最小fixture）

regression-lock.json
```

上記以外のfileが必要なら、責務、理由、検証方法を新しいplan revisionとして提示する。

## 変更しないもの

- review policy、reviewer起動、finding、fix loop、final gate
- resume、checkpoint、Recovery、claim回収、rebind、worktree cleanup
- parallel cycle、merge、publication、issue、PR、release
- `status.md`、`session-history.md`、`plans/progress`
- Phase 5の共有artifact store、共通runtime manager、後方互換
- READMEやplugin配布構造を外部validatorのためだけに変更すること
- 既存の無関係な`.claude`

## 外部への影響と主要risk

- mainへ確定済みの追加仕様commitを実装branchへcherry-pickする。
- 実装branchでは一concern単位でcommitし、hookを無効化しない。
- 実process検証と旧新比較は既存backendの実行時間と利用量を消費する。
- raw outputは一時領域だけに置き、credentialや全文logを正本artifactへ複製しない。
- test runner出力を曖昧に解析すると偽の件数が証拠化されるため、一意に取得できない場合は`unavailable`にする。
- 新dependency、未合意network、push、PR、mainへの実装mergeは行わない。

## Human gate

本修正plan自身にはplanned Human gateを置かない。必要な製品判断は仕様へ反映済みである。実装中に新しい製品判断が必要になった場合は即席gateを追加せずbrainstormへ戻る。権限要求はHuman gateではなくpermission処理に従う。

## 実装手順

### 0. 追加仕様commitを実装branchへ取り込む

**対応仕様:** `CY-063`  
**書込み範囲:** Git metadata

- mainの`3734958cd341d6221a55e055c2a2a1d7c6211097`が`CY-063`だけを変更することを確認する。
- 継続worktreeがcleanで、HEADが`d4335c69825f7791a4a23be6732effc853861ebb`であることを確認する。
- 追加仕様commitをcherry-pickし、三仕様の内容identityを再検証する。
- revision 2へ束縛された実行証拠はrevision 3の合否証拠として再利用しない。

**必要証拠:** cherry-pick commit、三仕様のSHA-256、祖先関係、`git diff --check`。  
**停止条件:** conflict、合意外のspec差分、dirty worktreeがある場合。

### 1. PlanのHuman gate生成・consumer契約を閉じる

**対応仕様:** `PL-024`〜`PL-026`、`CY-096`  
**書込み範囲:** `skills/ba0918-plan/references/creation.md`、`skills/ba0918-plan/scripts/plan_artifact.py`、`tests/plan_artifact_test.py`

- Plan作成指示に、必要なstepだけが`Human gates:` markerとversion 1 JSONを持つことを記載する。
- JSONは一意なgate ID、仕様条項、単一の判断基準、file集合またはimmutable event identity、timing、`approved/rejected`だけを持つ。
- 宣言なし、正常宣言、unknown field、重複ID、不正clause、不正timing、不正result、absolute path、traversal、可変参照をtest-firstで固定する。
- Planのpublication、revision、current locatorの既存semanticsは変えない。

**必要証拠:** instructionの静的test、parser testのRED/GREEN、既存Plan test全件GREEN。  
**停止条件:** Human gateが製品選択を含む、または正本仕様にない判断を追加する場合。

### 2. Oracle、evidence、Human gateのpure modelを厳密化する

**対応仕様:** `CY-050`〜`CY-065`、`CY-090`〜`CY-102`、`CY-110`〜`CY-117`  
**書込み範囲:** `skills/ba0918-cycle/scripts/execution_model.py`、`tests/cycle_execution_model_test.py`

- binding、event、oracle、command、cwd、environment、provenanceを再帰的exact schemaにし、unknown fieldを拒否する。
- test、fixture、設定pathをbytes identityへ束縛し、caller申告のidentityを信用しない。
- raw output、credentialらしい値、absolute path、traversal、symlink aliasを拒否する。
- test summaryは`complete`または`unavailable`のexact objectとする。`complete`だけが非負整数のpass、fail、skipを持ち、`unavailable`はboundedな理由だけを持つ。
- Human gate eventと、missing、malformed、target mismatch、rejected、target変更、全承認のstate transitionをpure functionで検証する。

**必要証拠:** exact schema、secret-like probe、summary二状態、Human gate七scenario、canonical identityのunit test。  
**停止条件:** 判定にraw log、第二の進捗正本、Phase 5のresume状態が必要な場合。

### 3. Runtimeの凍結identity、permission、test summary境界を閉じる

**対応仕様:** `CY-030`〜`CY-057`、`CY-063`、`CY-070`〜`CY-083`  
**書込み範囲:** `skills/ba0918-cycle/scripts/cycle_runtime.py`、`tests/cycle_runtime_test.py`

- RED受理時にtest、fixture、設定、command、cwd、environmentの実identityを凍結する。
- GREEN、REFACTOR、commit、terminal直前に対象bytesを再計算し、変更をdriftとして停止する。
- repository、worktree、cwd、targetの実path containmentを検証し、symlink escapeを拒否する。
- 親directory作成を含むfilesystem failureをpermissionまたは永続化不能へ分類する。
- `permission_required`を非終端eventとし、同じoperation identityだけを許可後に再試行する。
- command、exit code、outcome、対象identityは常に保存する。構造化reporterからpass、fail、skipを一意に得られた場合だけ`complete` summaryを保存し、それ以外は理由付き`unavailable`を保存する。
- raw output、推測件数、command成功数によるtest件数代用を永続化しない。

**必要証拠:** test弱体化、mkdir拒否、permission retry、symlink/cwd escape、永続化不能、summary complete/unavailableのRED/GREEN。  
**停止条件:** 件数の取得に曖昧なrunner出力の推測が必要な場合は`unavailable`とし、実装を拡張しない。

### 4. Commit列とwrite scopeを履歴全体で検証する

**対応仕様:** `CY-070`〜`CY-073`、`CY-081`、`CY-083`、`CY-090`〜`CY-093`  
**書込み範囲:** `skills/ba0918-cycle/scripts/cycle_runtime.py`、`skills/ba0918-cycle/scripts/execution_model.py`、対応test

- 一回の記録操作がprevious HEADを直接親とする一つの非merge commitだけを受理する。
- baseからHEADまでの全commitと全changed pathを列挙し、event列・write scopeと完全一致させる。
- fileを個別stageし、hook無効化、`git add .`、`git add -A`を禁止する既存契約を維持する。

**必要証拠:** hidden ancestor、複数commit、merge commit、scope外path、正常直列commitの一時repository test。  
**停止条件:** commit履歴を一意に観測できない場合。

### 5. CLIとinstructionを最小更新する

**対応仕様:** `CY-002`〜`CY-004`、`CY-096`〜`CY-099`  
**書込み範囲:** `skills/ba0918-cycle/SKILL.md`、`skills/ba0918-cycle/references/execution.md`、`skills/ba0918-cycle/references/tdd.md`、`skills/ba0918-cycle/references/evidence.md`、runtime CLI test

- skill本体はrouting、責務、完了条件だけを持つ。
- Human gate記録CLIはstep、gate ID、approved/rejectedだけを受け、runtime自身がcurrent target identityを計算する。
- `before_edit`は明示check command、`before_commit`はstage、`before_implementation_green`はterminalで越境を防ぐ。
- frozen identity、permission再試行、test summary、commit列、停止・引渡しを担当referenceへ置く。
- review、Recovery、cleanup、subagent delegationをinstructionへ戻さず、旧版比67%以上の静的縮小を保つ。

**必要証拠:** CLI help/error test、reference link確認、責務外keywordと重複契約の静的確認。  
**停止条件:** instructionだけでは強制できずruntime境界が必要な場合は、対応helper testを先に追加する。

### 6. Unit regressionを閉じる

**対応仕様:** `CY-110`〜`CY-117`  
**書込み範囲:** 三test file

- reviewで再現した五つのBLOCKを回帰testとして保持する。
- Human gate七scenario、schema、permission、commit履歴、path境界、summary二状態を覆う。
- 新しいproduction変更ごとに小さなRED、GREEN、必要なREFACTORを順に実行する。
- 全unit suiteとPython構文検査を通す。

**必要証拠:** 各新testの期待REDと修正後GREEN、全unit suite GREEN、`py_compile`成功。  
**停止条件:** production先行または対象testを弱めないとGREENにならない場合。

### 7. 実process scenarioとregression lockを再生成する

**対応仕様:** `CY-111`〜`CY-115`、`CY-117`  
**書込み範囲:** Cycleのeval case/input、`regression-lock.json`、一時fixture repository

- 正常完了、spec drift停止、意図しないRED拒否、test弱体化拒否を実processで実行する。
- artifact tree、binding、event chain、branch、worktree、commit列、resultを検査する。
- outer run manifestへ実session ID、attempt ID、backend、入力identityを対応づける。inner processで安全に取得不能なIDだけ理由付き`unavailable`にする。
- 全証拠が揃った後だけ該当lock entryを更新する。

**必要証拠:** 四scenarioの終了結果とpost-state、実session対応、lock再検証、raw logが正本artifactにないこと。  
**停止条件:** backend利用不能、session provenance不明、artifactとprocess結果の不一致がある場合はlockを更新しない。

### 8. 旧Cycleと新Cycleを同一入力で比較する

**対応仕様:** `CY-116`  
**書込み範囲:** `.agents/tmp/cycle-comparison/`の一時run data、最終実装報告

- pinned旧版と修正版へ同じfixture、plan、prompt、backend、権限、timeoutを与える。
- 要求充足、重大欠落、質問数、operation数、tool call数、再読範囲、token、経過時間を実測する。
- 各runのprovider session IDと入力identityを記録し、必要時だけ生logへ遡れるようにする。
- 静的instruction量と動的品質を分けて報告し、測定不能を成功扱いしない。

**必要証拠:** 同一入力条件、旧新session ID、測定表、重大欠落判定。  
**停止条件:** 修正版の重大欠落、要求充足低下、比較条件不一致がある場合。

### 9. 最終検証と引渡し

**対応仕様:** 全対象条項  
**書込み範囲:** 変更対象全体、最終実装報告

- 全unit test、eval lock検証、scope監査、credential形状検査、`git diff --check`を実行する。
- secretlintはprojectで解決可能な設定がある場合に実行する。設定dependencyが解決不能なら、その事実と代替検査を明示し、成功を装わない。
- old/new比較を含む必要証拠をworst verdictで集約する。
- `implementation_green`到達時はcommit列、branch、worktree、evidence path、残る非blocking事項を返す。
- mainへの実装merge、worktree cleanup、review、Recoveryは行わない。

**必要証拠:** command、exit code、全test数、spec identity、commit列、scope内diff、比較結論。  
**停止条件:** 必須test failure、identity drift、scope外変更、secret疑い、比較未完、証拠欠落がある場合。

## 実装へ委ねる選択

- 構造化test summaryを取得できる既存runner形式のうち、曖昧さなく検証できるadapterを追加してよい。
- 取得不能理由のboundedな定型文と、内部function名は実装時に決めてよい。
- 同じobservable behaviorとexact schemaを保つ範囲でpure functionの分割と命名を改善してよい。
- より広い検証commandは追加してよいが、凍結oracleを置換または弱化してはならない。

## 完了条件

- revision 3のplan、三仕様identity、repository、base HEAD、branch、worktreeが実行前と各境界で再検証される。
- Human gate declaration v1をPlan skillが生成でき、Cycleがexactに検証する。
- test、fixture、設定、command、cwd、environmentのidentity driftをGREEN、REFACTOR、commit、terminal前に拒否する。
- test summaryは構造化取得時の`complete`または理由付き`unavailable`であり、推測件数を含まない。
- permission retry、exact evidence、全commit履歴、write scope、secret、path containmentの否定例が通る。
- Human gate七scenario、正常・停止event列、四実process scenarioが通る。
- 旧版との同一入力比較が実session ID付きで完了し、重大な品質劣化がない。
- 全変更がplan scope内の独立commitで、全unit testと最終検査がGREENである。
