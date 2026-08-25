# Cycle skillの移行修正

**Plan ID:** `20260822143915`  
**Plan revision:** `2`  
**作成日時:** 2026-08-22 17:58:17 JST  
**置換対象:** revision 1 `.agents/artifacts/plans/20260822143915_cycle-skill-migration.md`（`sha256:4652305e0913c87053836499f33a5d17b89d2c3c86e57d6666ea379952`）  
**公開先:** `.agents/artifacts/plans/20260822143915_cycle-skill-migration-r2.md`

**対象仕様:**

- `docs/spec/agentic-workflow.md`
  - 内容identity: `sha256:bf8964ceb45b18cf04c890619d73eec098d52bd8b4a37fcbd4f721a2286f5c59`
  - 適用条項: `WF-001`〜`WF-003`、`WF-020`〜`WF-025`、`WF-060`〜`WF-075`、`WF-080`〜`WF-085`、`WF-089`〜`WF-094`、`WF-100`〜`WF-104`、`WF-130`〜`WF-136`、`WF-150`〜`WF-152`、`WF-160`〜`WF-161`、`WF-170`〜`WF-174`、`WF-180`〜`WF-181`、`WF-183`、`WF-185`、`WF-187`〜`WF-188`、`WF-190`〜`WF-191`、`WF-204`〜`WF-205`、`WF-207`
- `docs/spec/plan-skill-migration.md`
  - 内容identity: `sha256:014e3a631cd8e697c46027b84d8d6bf683045b18dfd1e97f95f13eedc6fb17b9`
  - 適用条項: `PL-010`、`PL-020`〜`PL-026`、`PL-040`〜`PL-042`、`PL-050`〜`PL-056`、`PL-060`〜`PL-064`、`PL-070`〜`PL-071`
- `docs/spec/cycle-skill-migration.md`
  - 内容identity: `sha256:f9374aab08c335374a7a8b2eb3284876b24230f8d1851b59911c4a54cbf92b64`
  - 適用条項: `CY-000`〜`CY-004`、`CY-010`〜`CY-013`、`CY-020`〜`CY-025`、`CY-030`〜`CY-034`、`CY-040`〜`CY-043`、`CY-050`〜`CY-057`、`CY-060`〜`CY-065`、`CY-070`〜`CY-073`、`CY-080`〜`CY-083`、`CY-090`〜`CY-099`、`CY-100`〜`CY-102`、`CY-110`〜`CY-117`

**実装境界資料:**

- `ROADMAP.md`: `sha256:d396cd90126aaddbbcad10574b7c417d20f1b074845298654dfbbc9dc353752e`
- 移行元: `claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`
- 修正元branch: `cycle/20260822143915-implementation`
- 修正元HEAD: `1990ab62bc2e7db93a318246a389ebce475570ee`
- 専用worktree: `.agents/tmp/worktrees/20260822143915-cycle`
- Phase 3 reviewで再現した五つのBLOCK、CY-116未完、session provenance不足、validator基準の不一致

## 目的

Phase 3で実装済みの`ba0918-cycle`について、reviewで実証された致命的な抜けを修正する。凍結test identity、commit履歴全体、permission再試行、exactかつsecret-safeなevidence、planned human gateを機械的な境界にし、同一入力による旧版比較まで完了させる。

Cycleの責務は、承認済みplanを専用worktreeでTDD実装し、immutable evidenceとcommitをPhase 4へ渡すところまでとする。review、fix loop、復旧、再開、cleanup、mergeは追加しない。

## 利用者が得る結果

- REDで凍結したtest、fixture、command、設定を弱めてもGREENとして受理されない。
- 記録対象commitの祖先にscope外変更や未記録commitを隠せない。
- sandbox権限不足はattemptを終端せず、同じ操作を許可後に安全に再試行できる。
- evidenceとoracleはunknown field、raw出力、credentialらしい値、unsafe pathを拒否する。
- planで宣言したhuman gateだけが、対象identityとtimingを照合した承認によって通過できる。
- 正常、spec drift、意図しないRED、test弱体化の実process scenarioと、旧版との同一入力比較から品質を確認できる。

## 実装開始条件と一回限りの移行

このrevisionの実装には既存の専用branchとworktreeを継続使用する。これは未mergeのPhase 3実装を修正するための一回限りのbootstrapであり、Cycleへ任意base、既存worktree取込み、復旧、claim生成、cleanupの機能を追加する根拠にしない。

production修正前に次を順に行う。

1. mainで、承認済みの`docs/spec/plan-skill-migration.md`と`docs/spec/cycle-skill-migration.md`だけをprojectのcommit ruleに従う独立commitとして正本化する。
2. そのcommitを既存の実装branchへcherry-pickし、三仕様の内容identityが本planと一致することを確認する。
3. branch HEAD、worktree identity、revision 1の実装commit列を記録する。
4. revision 1の完了主張とregression lockを、修正対象surfaceの有効証拠としては扱わない。

mainへのPhase 3実装の早期merge、擬似claimの作成、既存worktreeの作り直しは行わない。前提を満たせない場合はproduction fileを変更せず停止する。

## 変更するもの

```text
skills/ba0918-plan/scripts/plan_artifact.py

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

仕様二文書は実装開始条件で正本化するが、合意済み条項以外の意味は変更しない。上記以外のfileが必要なら、責務、理由、検証方法をplan revisionとして提示する。

## 変更しないもの

- review policy、reviewer起動、finding、fix loop、final gate
- resume、checkpoint、Recovery、claim回収、rebind、worktree cleanup
- parallel cycle、merge、publication、issue、PR、release
- `status.md`、`session-history.md`、`plans/progress`
- Phase 5の共有artifact store、共通runtime manager、後方互換
- `README.md`やplugin配布構造を、外部validatorを通すためだけに変更すること
- 既存の無関係な`.claude`

## 外部への影響

- 仕様commitをmainに一つ作り、そのcommitだけを既存実装branchへcherry-pickする。
- 実装branchでは修正を一concern単位でcommitする。
- 実process検証は一時fixture repository、既存backend、provider sessionを使用し、実行時間と利用量を消費する。
- 比較用raw outputは`.agents/tmp/cycle-comparison/`に限定し、credential、全文ログ、provider内部情報を正本artifactへ複製しない。
- 新しいdependency、未許可network、push、PR、mainへの実装mergeは行わない。

## 設計と再利用判断

| 層 | 判断 | 理由 |
|---|---|---|
| planとhuman gate schema | `plan_artifact.py`を拡張 | Planが宣言形式を所有し、Cycle側のparser複製を防ぐ |
| identity、schema、state transition | `execution_model.py`を強化 | pure modelで境界条件を網羅し、副作用なしに拒否をtestできる |
| Git、filesystem、process | `cycle_runtime.py`へ限定 | 観測値をadapterで取得し、modelへ未検証値を渡さない |
| secret検査 | exact schemaを第一防衛線とし、既存`ba0918-secrets`契約とproject hookを再利用 | 新規scanner依存やraw evidence保存を避ける |
| regression | 既存eval case、runner、`regression-lock.json`を再利用 | Phase 3固有のscenarioだけを追加できる |
| 旧版比較 | pinned旧版と同一入力・同一backendで実測 | 静的な行数比較を実行品質の代用にしない |
| 復旧とcleanup | 実装しない | Phase 5の責務を侵食しない |

## Human gate declaration v1

plan stepにhuman gateが必要な場合だけ、次のJSON objectをそのstepへ置く。不要なstepでは宣言を省略する。

```json
{
  "version": 1,
  "gates": [
    {
      "gate_id": "unique-id",
      "clauses": ["CY-096"],
      "criterion": "人間が判断する単一の可否基準",
      "target": {
        "kind": "files",
        "paths": ["repo/relative/path"]
      },
      "timing": "before_edit",
      "allowed_results": ["approved", "rejected"]
    }
  ]
}
```

`target`は`files`とrepo-relative path集合、または`event`とimmutable `content_identity`のどちらかとする。timingは`before_edit`、`before_commit`、`before_implementation_green`に限定する。結果は`approved`または`rejected`だけである。

本修正plan自身にはplanned human gateを置かない。必要な意味判断は仕様へ反映済みであり、実装中に新たなproduct choiceが生じた場合はgateを即席に追加せずbrainstormへ戻す。権限要求はhuman gateではなく、既存のpermission処理に従う。

## 実装手順

### 0. 仕様を正本化し、修正baseを固定する

**対応仕様:** `PL-024`〜`PL-026`、`CY-096`〜`CY-099`  
**書込み範囲:** `docs/spec/plan-skill-migration.md`、`docs/spec/cycle-skill-migration.md`、Git metadata

- 二仕様の差分が承認済みhuman gate条項だけであることを確認する。
- 二fileだけをmainでcommitし、そのcommitを既存実装branchへcherry-pickする。
- worktree上で本plan記載の三仕様identityと修正元commitの祖先関係を検証する。
- revision 1のevidenceを参考資料として残し、新しい合否判定には再利用しない。

**必要証拠:** mainの仕様commit ID、cherry-pick先commit ID、三仕様のSHA-256、`git diff --check`、scope外fileが両commitにないこと。

**停止条件:** 合意外の仕様差分、conflictによる意味変更、既存実装branchとの不整合がある場合。

### 1. Planのhuman gate consumer契約を追加する

**対応仕様:** `PL-024`〜`PL-026`、`CY-096`  
**書込み範囲:** `skills/ba0918-plan/scripts/plan_artifact.py`、`tests/plan_artifact_test.py`

- 宣言なし、正常なv1宣言、unknown field、重複gate ID、不正clause、不正timing、不正result、absolute path、traversal、可変参照をtest-firstで固定する。
- stepの対応仕様とgateの`clauses`を照合し、versionedでexactな読取り専用consumer viewを返す。
- file targetのpath集合を正規化するがidentityはCycle実行時に実bytesから計算する。
- event targetは固定済み`sha256:` identityだけを受理する。
- publication、revision、current locatorの既存semanticsは変えない。

**必要証拠:** 新testのRED/GREEN、既存Plan test全件GREEN、拒否時のartifact非変更。

### 2. Oracle、evidence、human gateのpure modelを厳密化する

**対応仕様:** `CY-050`〜`CY-065`、`CY-090`〜`CY-099`、`CY-110`〜`CY-117`  
**書込み範囲:** `skills/ba0918-cycle/scripts/execution_model.py`、`tests/cycle_execution_model_test.py`

- binding、event、oracle、command、cwd、environment、provenanceを再帰的exact schemaにし、unknown fieldを拒否する。
- oracleへrepo-relativeなtest、fixture、設定path集合を束縛し、identityをcaller申告ではなく対象bytesから導出できる形にする。
- raw stdout/stderr、任意environment値、credentialらしいkey/value、absolute path、traversal、symlink aliasを受理しない。
- `human_gate` eventを`gate_id`、`step_id`、`target_identity`、`result`で検証する。
- declarationとの一致、timing、current target identity、approved/rejected、target変更によるstale化をstate transitionへ組み込む。
- 必須gateがすべてcurrent identityでapprovedの場合だけ`implementation_green`を許可する。

**必要証拠:** secret-like probe、unknown-field probe、human gate七scenario、正常・停止event列、canonical identityのunit test。

**停止条件:** 判定にraw provider log、第二の進捗正本、Phase 5のresume状態が必要になる場合。

### 3. Runtimeのfrozen identityとpermission境界を直す

**対応仕様:** `CY-030`〜`CY-034`、`CY-040`〜`CY-043`、`CY-050`〜`CY-057`、`CY-070`〜`CY-073`、`CY-080`〜`CY-083`  
**書込み範囲:** `skills/ba0918-cycle/scripts/cycle_runtime.py`、`tests/cycle_runtime_test.py`

- RED受理時にtest、fixture、設定、command、cwd、environmentの実identityを凍結する。
- GREEN、REFACTOR、commit、terminal判定の直前に同じ対象を再計算し、削除、追加、弱体化、差替えをdriftとして停止する。
- agent root、repository root、worktree、cwd、全target pathのcontainmentを実pathで検証し、symlink escapeを拒否する。
- filesystem操作は親directory作成を含めpermission分類の内側に置く。
- `permission_required`は非終端eventとし、許可後に同じoperation identityだけを再試行できるようにする。
- 永続化不能は安全なbounded summaryを返して停止し、成功を主張しない。
- commandごとのpass/fail/skipを構造化し、fail/skipをsummaryから欠落させない。

**必要証拠:** test弱体化probeが拒否、permission probeが同一identityでretry成功、mkdir拒否、symlink/cwd escape、永続化不能、pass/fail/skipのunit test。

### 4. Commit列とwrite scopeを履歴全体で検証する

**対応仕様:** `CY-070`〜`CY-073`、`CY-081`、`CY-083`  
**書込み範囲:** `skills/ba0918-cycle/scripts/cycle_runtime.py`、`skills/ba0918-cycle/scripts/execution_model.py`、対応test

- `previous_head`がcurrent commitの直接の親であることを必須にし、一操作一commitを保証する。
- `previous_head..HEAD`の全commitと全changed pathを列挙し、未記録commit、merge commit、scope外pathを拒否する。
- terminal判定ではbaseからHEADまでのcommit列が、eventへ順序付きで記録されたcommit列と完全一致することを確認する。
- stagingは個別pathだけを許し、hook無効化、`git add .`、`git add -A`を禁止する既存契約を維持する。

**必要証拠:** hidden ancestor probe、複数commit、merge commit、scope外path、正常な直列commitの一時Git repository test。

### 5. CLIとinstructionを最小更新する

**対応仕様:** `CY-002`〜`CY-004`、`CY-096`〜`CY-099`  
**書込み範囲:** `skills/ba0918-cycle/SKILL.md`、三reference、runtime CLI test

- skill本体はrouting、責務、完了条件だけを保持する。
- human gate記録用CLIを追加し、step、gate、approved/rejectedを受けてcurrent target identityをruntime自身が計算する。自由記述やraw transcriptは受け取らない。
- frozen identity、permission再試行、commit列検証、停止・引渡しを担当referenceへ配置する。
- review、Recovery、cleanup、subagent delegationをinstructionへ戻さない。
- 通常経路で必要なreferenceだけを読む構造と、旧版比67%以上の静的縮小を維持する。

**必要証拠:** CLI help/error test、reference link確認、責務外keywordと重複契約の静的確認。

### 6. Unit regressionを閉じる

**対応仕様:** `CY-110`〜`CY-117`  
**書込み範囲:** 三test file

- Phase 3既存testを保持し、reviewで再現した五つのBLOCKをそのまま回帰testへする。
- human gateについて、宣言なし正常、missing、malformed、target mismatch、rejected、target変更、全承認後成功を覆う。
- schema、permission、commit履歴、path境界の否定例をproperty tableとしてまとめる。
- RED、GREEN、REFACTORごとに対象test commandの実出力を保存し、production先行を認めない。

**必要証拠:** 各新testの期待RED、修正後GREEN、全unit suite GREEN、`py_compile`成功。

### 7. 実process scenarioとregression lockを再生成する

**対応仕様:** `CY-111`〜`CY-115`、`CY-117`  
**書込み範囲:** Cycleのeval case/input、`regression-lock.json`、一時fixture repository

- 正常完了、spec drift停止、意図しないRED拒否、test弱体化拒否の四scenarioを実processで実行する。
- subprocess終了だけでなく、artifact tree、binding、event chain、Git branch/worktree、commit列、resultを検査する。
- session ID、attempt ID、backend、入力identityをrun manifestで対応づける。
- inner processからsession IDを安全に取得できない場合だけbindingを`unavailable`とし、理由と外側manifestの実session IDを残す。推測値やsynthetic IDで代用しない。
- 全証拠が揃った後だけ該当lock entryを更新する。

**必要証拠:** 四scenarioの終了結果とpost-state、実session対応、lock再検証、raw logをcanonical artifactへ複製していないこと。

**停止条件:** backend利用不能、session provenance不明、artifactとprocess結果の不一致がある場合はlockを更新しない。

### 8. 旧Cycleと新Cycleを同一入力で比較する

**対応仕様:** `CY-116`  
**書込み範囲:** `.agents/tmp/cycle-comparison/`の一時run data、最終実装報告

- pinned旧版と修正版へ、同じrepository fixture、plan、prompt、backend、tool権限、timeoutを与える。
- 要件充足、重大欠落、質問数、operation/tool call数、instruction再読範囲、input/output token、経過時間を実測する。
- 各runのprovider session IDと入力identityを記録し、必要時だけ生ログへ遡れるようにする。
- 静的instruction量も併記するが、動的品質の代用にはしない。
- 修正版に重大欠落がある、要件充足が悪化する、または測定不能項目を成功扱いする場合は完了しない。

**必要証拠:** 同一入力条件、旧新session ID、測定表、重大欠落判定、静的量と動的結果を分離した結論。

### 9. 最終検証と引渡し

**対応仕様:** 全適用条項  
**書込み範囲:** なし。ただし失敗修正は該当手順の範囲へ戻す。

- 全unit test、`py_compile`、Markdown link、eval schema、regression lockを実行する。
- 外部`claude-skills/scripts/validate_repo.py`はdistribution全体の診断としてmain baselineと比較し、Phase 3由来の新規または未説明の違反がないことを確認する。既存違反を全件解消するためにscopeを広げない。
- `git diff --check`、secret scan、branch ancestry、commit列、worktree dirtiness、変更file一覧を確認する。
- BLOCKが一つでも残る、必要scenarioが未実行、証拠が永続化不能、旧新比較が未完の場合は`implementation_green`を主張しない。
- 合格時はbranch、HEAD、worktree、仕様identity、test結果、scenario session ID、比較結果、残存WARNをPhase 4へ引き渡す。merge、cleanup、復旧は行わない。

## 受入条件

- reviewで再現した五つのBLOCK probeがすべて拒否または安全な再試行へ変わっている。
- `CY-117`のhuman gate七scenarioが機械testで通る。
- baseからHEADまでにscope外または未記録commitを隠せない。
- evidence/oracleのunknown field、raw output、secret-like値、unsafe pathを拒否する。
- 四つの実process scenarioがartifactとGit post-stateを含め期待結果になる。
- CY-116の同一入力比較が実session ID付きで完了し、修正版に重大な品質劣化がない。
- project固有検証が全件成功し、外部validatorにPhase 3由来の未説明な悪化がない。
- 実装branchとworktreeを保持し、Phase 4が同じcommitとevidenceをreviewできる。
- review、Recovery、cleanup、merge、Phase 5 artifact管理をCycleへ持ち込んでいない。

## 停止と差戻し

次のいずれかでは推測で進めず、該当する上流へ戻す。

- 新しいproduct choiceまたは仕様矛盾: brainstorm
- 実装順、scope、検証方法の変更: plan revision
- sandbox permission不足: 同じoperation identityを保持して権限確認
- 永続化不能、identity drift、session provenance欠落、backend不能: evidenceを捏造せず停止
- review/fix、復旧、cleanupが必要: Phase 4またはPhase 5へ引渡し

