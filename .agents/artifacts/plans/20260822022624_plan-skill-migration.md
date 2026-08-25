# Plan skillの移行

**Cycle ID:** `20260822022624`  
**Plan revision:** `1`  
**作成日時:** 2026-08-22 02:26:24 JST  
**対象仕様:**

- `docs/spec/agentic-workflow.md`
  - 内容identity: `sha256:bf8964ceb45b18cf04c890619d73eec098d52bd8b4a37fcbd4f721a2286f5c59`
- `docs/spec/plan-skill-migration.md`
  - 内容identity: `sha256:1eb5a91519529937548dadb62211dceb5b2a161acd0576e0705723879081b75e`

## 目的

承認済み仕様と検証契約を、不足した意味を補わず、人間と後続runnerが同じ内容を理解できる実行計画へ変換する`ba0918-plan` skillを作る。

旧plan skillに混在していた進捗更新、session history、TDD、実装、resume、checkpointは移植しない。plan作成、手順revision、安全な現在対象の切替だけに責務を限定する。

## 利用者が得る結果

- plan全体を日本語で読み、実装前に変更内容とriskを判断できる。
- 各手順が、承認済み仕様条項と必要な完了証拠へ追跡できる。
- 人間が確認する前に正本planが作られない。
- runnerがstatus更新を忘れても、planの正しさや完了判定が壊れない。
- 未完了planが複数残っても、既存planを無言で上書きしない。
- dirty worktreeから別planへ変更を混入させない。

## 変更するもの

```text
skills/ba0918-plan/
  SKILL.md
  references/
    creation.md
    lifecycle.md
    readability.md
  scripts/
    plan_artifact.py

tests/
  plan_artifact_test.py

evals/cases/ba0918-plan/
  create-human-readable-plan.yaml
  reject-incomplete-source.yaml
  protect-existing-plan.yaml

evals/inputs/ba0918-plan/
  small-approved-change.md
  incomplete-change.md
  existing-open-plan/

regression-lock.json
```

実装中に別ファイルが必要になった場合は、既存ファイルで責務を表せない理由をplan revisionとして人間へ提示する。

## 変更しないもの

- `ba0918-brainstorm`の動作と保存形式
- 承認済みspecとROADMAPの意味
- TDD、実装、reviewの実行
- branchまたはworktreeの作成と切替
- Recoveryの実装
- `parallel-cycle`
- GitHub、issue、PR、commit操作
- 旧artifactの自動migration
- 既存の無関係な`.claude`

## 外部への影響

- network接続は追加しない。
- 外部serviceやdatabaseは使用しない。
- branch、worktree、commitを操作しない。
- project内のplan artifactと未完了plan索引だけを読み書きする。
- 新しい外部packageを追加しない。
- skill単体で配布できる構成を維持する。

## 設計

### Skillの構成

`SKILL.md`はtrigger、責務境界、現在の操作に必要なreferenceの選択だけを持つ。

- `creation.md`  
  入力検査、plan生成、草稿提示、人間確認、正本化を扱う。
- `lifecycle.md`  
  revision、未完了plan索引、現在対象の切替、dirty worktreeでの停止を扱う。
- `readability.md`  
  正本plan全体の読みやすさと必須表示内容を扱う。
- `plan_artifact.py`  
  内容identity、正本化、索引検証・更新など、決定的に処理すべき部分を扱う。

通常のplan作成時に全referenceを一括で読まず、その操作に必要なreferenceだけを読む。

### 正本planの形式

正本planには少なくとも次を含める。

- plan IDとrevision
- 適用するspec path、revisionまたは内容identity、条項
- 目的と利用者が得る結果
- 変更するものと変更しないもの
- 外部影響と主要risk
- 実装手順
- 各手順の先行項目
- 各手順の期待成果物
- 書込み範囲
- 必要証拠
- 実装へ委任された判断
- 人間判断が必要な場所
- 停止条件

人間向け概要とLLM専用の規範層には分けない。後続runnerは、人間が確認した同じplanを使用する。

### 未完了plan索引

未完了plan索引は、人間が直接編集するstatus文書にはしない。

保持できる情報を次に限定する。

- plan ID
- 安定したplan path
- plan revisionまたは内容identity
- `current`または`held`

実際の工程、完了状態、実装証拠、review findingは複製しない。

具体的なserialization形式は、上記fieldと再構築可能性を満たす最小形式を実装時に選ぶ。汎用workflow schemaや共有runtimeにはしない。

### Revision

進捗のためにplan本文を変更しない。

手順修正が必要な場合は、

1. specの意味を変えるか判定する。
2. 意味を変える場合はbrainstormへ戻す。
3. 意味を変えない場合は新しいplan revisionを草稿として提示する。
4. 人間確認後に新revisionを正本化する。
5. 影響する古い証拠を失効対象として記録する。

### Plan切替

既存の`current` planがある場合、新planを無言で現在対象にしない。

人間へ次を提示する。

- 既存planの目的
- 新planの目的
- 既存planを`held`へ移すこと
- dirty worktreeの有無
- 切替後も既存planは未完了として残ること

dirty worktreeを再開可能に隔離できていない場合は、人間確認があっても切替を停止する。plan skill自身はcommit、checkpoint、branch、worktree操作を行わない。

## 再利用判断

| 層 | 判断 | 理由 |
|---|---|---|
| skillの構成 | 既存パターンを採用 | `ba0918-brainstorm`の薄い`SKILL.md`と選択的reference読込みが、単体配布とtoken削減を実証済み |
| 内容identity | Python標準libraryを採用 | `hashlib`と決定的serializationで足り、外部依存は不要 |
| artifact更新 | 小さな専用実装を作る | plan固有の確認後書込みと索引契約が必要。共有runtimeは作らない |
| path安全性 | 既存の境界検査方法を採用 | traversal、symlink、repository外書込みを一つのvalidatorで拒否する |
| unit test | Python標準`unittest`を採用 | Phase 1と同じ既存toolchainで検証できる |
| end-to-end評価 | 既存のskill regression方式を採用 | backend別process、固定scenario、旧版比較の仕組みがすでにある |
| status/session履歴 | 作らない | 正本と証拠の重複状態になり、更新忘れで乖離する |
| resume/checkpoint | 作らない | Phase 5 Recoveryの責務 |
| TDD runner | 作らない | Phase 3 Implement and Cycleの責務 |

## 実装手順

### 1. 期待動作を固定し、REDを確認する

**対応仕様:** `PL-010`〜`PL-012`、`PL-021`〜`PL-023`、`PL-030`〜`PL-032`、`PL-060`〜`PL-064`、`PL-080`〜`PL-081`

**変更対象:**

```text
tests/plan_artifact_test.py
evals/cases/ba0918-plan/
evals/inputs/ba0918-plan/
```

**行うこと:**

- plan artifact helperが未実装であるため失敗するunit testを先に作る。
- 次の三つの利用者向けscenarioを固定する。
  - 完全な小規模仕様から、日本語で追跡可能なplan草稿を作る。
  - 未決定事項や検証契約不足を検出し、正本を書かずbrainstormへ戻す。
  - 既存planとdirty worktreeがある状態で、無言の切替を拒否する。
- 失敗理由が未実装の期待契約であり、fixture設定不良ではないことを確認する。

**必要証拠:**

- fixture schema検証結果
- unit testが期待した未実装理由で失敗した出力
- scenario実行が重大条件を満たせず失敗した記録

**停止条件:**

fixtureだけで期待動作を説明できない場合は、production実装へ進まずplan revisionまたはbrainstormへ戻す。

### 2. Plan artifactの決定的処理を実装する

**先行項目:** 手順1  
**対応仕様:** `PL-030`〜`PL-032`、`PL-040`〜`PL-041`、`PL-053`〜`PL-055`、`PL-061`〜`PL-063`

**変更対象:**

```text
skills/ba0918-plan/scripts/plan_artifact.py
tests/plan_artifact_test.py
```

**行うこと:**

- plan草稿の内容identityを計算するpure functionを作る。
- 人間が確認したidentityと書込み対象のidentityが一致しない場合に拒否する。
- plan ID、path、revision、内容identityを検証する。
- repository外path、traversal、symlinkを拒否する。
- 未完了plan索引を決定的に検証・更新する。
- 既存`current` planを無言で置き換えない。
- `current`から`held`への切替には人間確認証拠を要求する。
- dirty worktreeでは切替を書き込まず停止する。
- 一時ファイルとatomic renameで、正本planと索引の部分書込みを防ぐ。
- indexが古い場合に、正本planとのidentity不一致を検出する。

**必要証拠:**

- pure functionのunit test成功
- path traversalとsymlink拒否のtest成功
- identity不一致時に正本も索引も変化しないtest成功
- 既存plan切替の確認不足とdirty worktree拒否test成功
- 同一入力から同一bytesを生成するtest成功

**変更しないもの:**

- 実装証拠の生成
- 完了判定
- branchまたはworktree操作
- Recovery

### 3. Human-readableなplan skillを実装する

**先行項目:** 手順2  
**対応仕様:** `PL-001`、`PL-010`〜`PL-023`、`PL-030`〜`PL-042`、`PL-070`〜`PL-072`

**変更対象:**

```text
skills/ba0918-plan/SKILL.md
skills/ba0918-plan/references/creation.md
skills/ba0918-plan/references/lifecycle.md
skills/ba0918-plan/references/readability.md
```

**行うこと:**

- 完全な入力では追加質問を増やさず草稿を作る。
- 不足した入力は具体的な影響とともに拒否する。
- 適用specを内容から自動推測しない。
- 正本plan全体を現在の利用者の言語で作る。
- 技術用語を最初の使用時に説明する。
- 正本へ保存する全内容をchatで提示する。
- 人間確認前はplan artifactと索引を書き換えない。
- 確認後だけhelperを使って正本化・索引登録する。
- plan revision時も同じ確認手順を使う。
- resume、status更新、session history、TDD、実装、review、commitをtriggerまたはworkflowとして持たせない。
- caller-supplied modeとspec自動検出を実装しない。
- second reviewerを自動起動しない。

**必要証拠:**

- skillの静的interface検査成功
- Agent Skills標準検証成功
- 通常経路が必要なreferenceだけを読むことの静的確認
- 旧責務が新skillへ残っていないことの検索結果

### 4. 利用者向けscenarioをGREENにする

**先行項目:** 手順3  
**対応仕様:** `PL-080`〜`PL-083`、`WF-170`〜`WF-174`

**変更対象:**

```text
evals/cases/ba0918-plan/
evals/inputs/ba0918-plan/
regression-lock.json
```

**行うこと:**

- 完全入力から、日本語のplan草稿を質問なしで生成する。
- 人間確認前にfileが作られていないことを確認する。
- 確認後、草稿と同じidentityの正本planと索引が作られることを確認する。
- 不完全入力がbrainstormへ戻されることを確認する。
- 既存planを自動abandonedにしないことを確認する。
- dirty worktreeで切替が停止することを確認する。
- `status.md`と`session-history.md`が作成・更新されないことを確認する。
- plan全項目がspec条項と必要証拠へ追跡できることを確認する。
- 検証済みのbehavior surfaceを`regression-lock.json`へ登録する。

**必要証拠:**

- 全critical expectationの成功
- worktree内の変更一覧
- 正本planと確認対象のidentity一致
- status/session historyの非変更証拠
- regression lockの内容検査成功

### 5. Skill単体の実動作と旧版比較を行う

**先行項目:** 手順4  
**対応仕様:** `PL-082`〜`PL-083`、`WF-170`〜`WF-174`

**変更対象:**

実装fileは変更しない。実測結果だけをPhase 2のreviewまたはROADMAPへ記録する。

**行うこと:**

- `ba0918-plan`だけを対象clientへ配置する。
- 入力、草稿提示、人間確認、正本書込み、identity確認、索引登録までを実processで完走する。
- Phase 1と同様、利用可能な低コストbackendを使用する。
- 旧版と同じ完全入力で比較する。
- 要求充足、重大な漏れ、質問数、操作数、tool呼出し、再読範囲、入出力tokenを記録する。
- 重要機能の欠落、安全制約違反、重大な品質劣化を平均値で相殺しない。
- 最終判定を「移行可」「修正後に再評価」「移行不可」のいずれかで記録する。

**必要証拠:**

- Agent Skills標準検証結果
- 対象clientでのend-to-end実行記録
- backend別の独立した回帰結果
- 旧版との品質・操作・token比較
- 未確認事項と最終判定

## Test一覧

### 入力拒否

- blockingな未決定事項を持つ入力を拒否する。
- 検証契約または反例がない入力を拒否する。
- 適用specが明示されていない入力を拒否する。
- source audit未完了の入力を拒否する。
- specにない設計をplanへ追加しない。

### Human-readable

- 正本plan全体が現在の利用者の言語になる。
- 技術用語が最初の使用時に説明される。
- 変更対象、非変更対象、risk、外部影響、必要証拠をplan単体で判断できる。
- LLMだけが理解する規範層を持たない。

### 正本化

- 人間確認前にplanと索引を書き込まない。
- 確認した草稿と異なるidentityを拒否する。
- 書込み失敗時に部分的な正本や索引を残さない。
- revisionをin-placeで変更しない。

### 未完了plan

- plan本体の安定pathを維持する。
- 索引へ工程や証拠内容を複製しない。
- 既存planを無言で置き換えない。
- 保留と放棄を区別する。
- 自動abandonedを行わない。
- dirty worktreeで切替を停止する。

### 責務境界

- statusとsession historyを更新しない。
- plan本文のcheckboxを進捗正本にしない。
- resumeとcheckpointを実装しない。
- TDD、実装、reviewを開始しない。
- branch、worktree、commitを操作しない。
- caller-supplied modeを提供しない。
- second reviewerを無断起動しない。

## 主要risk

- 未完了索引が第二の正本になるrisk  
  保持fieldを限定し、正本planとのidentity照合を必須にする。
- planが読みやすさのために必要情報を落とすrisk  
  短さではなく、目的・影響・非変更範囲・証拠の理解可能性を検証する。
- plan確認が形式化するrisk  
  要約ではなく、保存する正本内容そのものを提示する。
- dirty worktreeの誤判定risk  
  自動隔離は行わず、安全に切替できない場合は停止する。
- Phase 3またはRecoveryの責務を先取りするrisk  
  証拠の必要条件と接続情報だけを定義し、実行・完了・復旧処理を実装しない。
- 旧caller-supplied consumerとの互換性risk  
  完全互換を目標にせず、`parallel-cycle`移行時に明示adapterとして再設計する。

## 実装開始前の人間gate

このplanの正本化は、実装開始の権限を与えない。

正本化後も、Phase 3を開始するには別途「実装して」などの明示指示が必要である。second reviewerの起動権限も含まない。
