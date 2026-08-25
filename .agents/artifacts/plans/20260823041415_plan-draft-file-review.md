# Plan草稿のfile確認方式

**Plan ID:** `20260823041415`  
**Plan revision:** `1`  
**作成日時:** 2026-08-23 04:14:15 JST  
**公開先:** `.agents/artifacts/plans/20260823041415_plan-draft-file-review.md`

**対象仕様:**

- `docs/spec/plan-skill-migration.md`
  - 内容identity: `sha256:a1f3232e7162b82065b8d1221dac2f106b338303d3e42d9361dd40a526e41d7b`
  - 適用条項: `PL-030`〜`PL-036`、`PL-053`〜`PL-054`、`PL-061`、`PL-063`
- `docs/spec/agentic-workflow.md`
  - 内容identity: `sha256:b50e663b49847b597d1cf4ebce14fcd43c4943acd93da0b4cb30a1f14d3af883`
  - 適用条項: `WF-033`、`WF-039`（brainstorm側の実装は本planの対象外。同じ契約の整合確認にのみ参照する）
- `docs/spec/cycle-skill-migration.md`
  - 内容identity: `sha256:bafb3c45c11cfa549b452eeedb7eab3c4322412036ab3892251b599215820c6e`
  - 適用条項: `CY-010`〜`CY-013`（一時草稿をcurrent planとして解決しない側の確認）

**実装境界資料:**

- `ROADMAP.md`: `sha256:f055692e5c79f8e81a2caef889832c3a914aa1467891d06a63fe5a99e85f6948`
- 発端issue: `.agents/artifacts/issues/20260822152244_replace-plan-draft-chat-with-file-review.md`
- 仕様改訂commit: `9398e486a0ea687b0fbe2b397f1bf10bb9858763`（`docs: 承認前草稿の提示をchat全文からfile確認へ改める`）

## 目的

長い正本plan草稿をchatへ流す代わりに、正本と同一bytesの一時fileとして`.agents/tmp/plans/`へ置き、人間が自分のviewerで読んで、そのcontent identityへ承認を結び付けられるようにする。承認後は一時fileを正本へ移動し、読み戻しidentityの一致を確認してから索引登録する。

## 利用者が得る結果

- plan作成時、chatにはpath、content identity、正本の保存先、確認してほしい判断事項だけが表示される。草稿全文はchatに現れない。
- 人間が一時fileを直接編集して承認しても、identity不一致として拒否され、対話による修正に戻される。
- 承認成功後、一時fileは残らず、正本と索引は承認したidentityと一致する。

## 変更するもの

```text
skills/ba0918-plan/
  SKILL.md
  references/
    creation.md
  scripts/
    plan_artifact.py

tests/
  plan_artifact_test.py
  cycle_runtime_test.py

evals/cases/ba0918-plan/
  create-human-readable-plan.yaml
  protect-existing-plan.yaml
  reject-incomplete-source.yaml（期待の整合確認のみ。変更が不要なら触らない）

regression-lock.json
```

上記以外のfileが必要なら、責務、理由、検証方法を新しいplan revisionとして提示する。`skills/ba0918-cycle/scripts/cycle_runtime.py`は、step 3のtestが既存の拒否で通る場合は変更しない。

## 変更しないもの

- brainstorm skill（`WF-053`〜`WF-056`の実装は次のcycle）
- plan本文の構成、Human gate宣言、revision、索引の形式
- 正本plan・`open-plans.json`の保存先とpath規則
- viewerの選択・起動
- output tokenの実測比較（合意で完了条件から除外）

## 外部への影響と主要risk

- `.agents/tmp/plans/`は`.gitignore`済みで、commit対象にならない。
- 一時fileに正本と同じbytesを置くため、fileを開いただけでは草稿だと分からない。pathとchat表示で区別する。
- 一時保存と正本化の間で人間がfileを編集した場合、拒否は設計どおりだが、編集内容は失われず一時fileに残る。
- 影響scenarioの実process再実走はOpenCodeのquotaを消費する。lockのimpact判定で対象を限定する。
- 新dependency、network、push、PR、mainへの自動mergeは行わない。

## Human gate

本planにplanned Human gateを置かない。草稿の承認はplan skillの通常の人間確認であり、製品判断はすべて仕様へ反映済みである。

## 実装手順

### 1. 一時草稿の保存commandを追加する

**対応仕様:** `PL-030`、`PL-033`、`PL-036`  
**書込み範囲:** `skills/ba0918-plan/scripts/plan_artifact.py`、`tests/plan_artifact_test.py`

- `plan_artifact.py`に`draft`commandを追加する。標準入力の草稿bytesを`.agents/tmp/plans/<plan-id>_<slug>_r<revision>_draft.md`へatomicに書き、pathとcontent identityをJSONで返す。
- 既存fileがある場合は`--replace-identity`で指定したidentityと一致するときだけ置き換え、不一致または未指定なら書き込まず失敗を返す。
- `.agents/tmp/plans/`配下以外、absolute path、traversal、symlinkを拒否する。書込み失敗は成功として返さない。
- 草稿bytesにヘッダやfrontmatterを足さない（返すidentityは入力bytesそのもの）。

**必要証拠:** 新規testのRED（command不在）→GREEN、既存plan test全件GREEN。  
**停止条件:** 一時保存の保存先を`.agents/tmp/plans/`以外にする必要が出た場合。

### 2. 正本化を一時fileからの移動と読み戻し一致に変える

**対応仕様:** `PL-031`、`PL-032`、`PL-034`、`PL-035`、`PL-053`、`PL-054`、`PL-061`、`PL-063`  
**書込み範囲:** `skills/ba0918-plan/scripts/plan_artifact.py`、`tests/plan_artifact_test.py`

- `publish`の`--source`に一時草稿fileを指定したとき、その現在のidentityが`--approved-identity`と一致する場合だけ正本pathへ移動（rename）する。不一致は失敗とし、一時fileを残す。
- 移動後に正本を読み戻し、identity一致を確認してから索引へ登録する。不一致は失敗とし、成功を主張しない。
- 成功時は一時fileが残らないこと、失敗時は残ることを固定する。既存のswitch確認とdirty worktreeの拒否は変えない。
- 識別していない一時fileを削除しない。

**必要証拠:** 編集済み草稿の拒否、読み戻し一致、成功時の一時file不在、失敗時の残存の各testのRED→GREEN。  
**停止条件:** renameが同一filesystem内で行えない構成が判明した場合（copy+verify+unlinkへの変更はrevisionとして提示）。

### 3. 一時草稿がcurrent planとして解決されないことを固定する

**対応仕様:** `PL-033`、`CY-010`〜`CY-013`  
**書込み範囲:** `tests/cycle_runtime_test.py`（必要な場合のみ`skills/ba0918-cycle/scripts/cycle_runtime.py`）

- `.agents/tmp/plans/`配下の草稿を`--plan-path`で渡したとき、`resolve`が登録外としてpath解決を拒否することをtestで固定する。
- 既存の`plan_registration_missing`または安全path拒否で通るなら、runtimeは変更しない。通らない場合だけ最小の拒否を追加する。

**必要証拠:** testのRED（または既存拒否で初回からGREENならその旨と根拠）、Cycle test全件GREEN。  
**停止条件:** 拒否のためにCycleのplan解決順序を変える必要が出た場合。

### 4. 指示を新しい契約へ同期する

**対応仕様:** `PL-030`、`PL-033`〜`PL-036`  
**書込み範囲:** `skills/ba0918-plan/SKILL.md`、`skills/ba0918-plan/references/creation.md`

- `creation.md`の「草稿はconversationだけに保持し、承認前にfileを作らない」を、「`draft`commandで一時fileへ保存し、chatにはpath、identity、保存先、判断事項だけを出す」に改める。全文のchat複製と要約承認の禁止は残す。
- 承認後の手順を「一時fileを`--source`にして`publish`、読み戻し一致、一時file不在の確認」に改める。
- 人間がfileを編集した場合の扱い（拒否して対話で修正）と、再提示時の`--replace-identity`の使い方を書く。
- `SKILL.md`のBoundary/Completionは、語が変わる箇所だけ最小限に直す。

**必要証拠:** 指示の差分、Markdown参照の検査。  
**停止条件:** 指示だけで表現できない動作が見つかった場合（step 1〜2へ戻す）。

### 5. 影響scenarioを改訂して再実走し、lockを更新する

**対応仕様:** `PL-030`、`PL-033`〜`PL-035`  
**書込み範囲:** `evals/cases/ba0918-plan/`、`regression-lock.json`

- `create-human-readable-plan.yaml`に「草稿が`.agents/tmp/plans/`配下の一時fileとして存在し、chat応答に全文が含まれない」「提示されたidentityと一時fileのidentityが一致する」をcriticalで追加する。「人間確認前にplan、索引、status、session historyを作成または変更しない」は維持する。
- `protect-existing-plan.yaml`と`reject-incomplete-source.yaml`は、一時草稿の有無が期待に影響する場合だけ最小限に改訂する。
- `lock.py --impact-scenarios`で影響scenarioを求め、それだけを`opencode-go/deepseek-v4-flash`で再実走する。post-state（一時fileの存在と内容、正本・索引の不変、report本文）から裁定し、lockを更新する。
- scenario改訂のcommitに改訂根拠の条項IDを書く。

**必要証拠:** impact判定の出力、再実走のgrade結果と裁定、lock差分。  
**停止条件:** backend利用不能、quota超過、裁定不能の場合はlockを更新しない。

### 6. 最終検証

**対応仕様:** 全対象条項  
**書込み範囲:** なし（検査のみ）

- 全unit test、`lock.py --check`、`git diff --check`、scope監査、secret形状検査を実行する。
- 結果をworst verdictで集約し、branch、commit列、証拠pathを返す。

**必要証拠:** 各commandの出力とexit code。  
**停止条件:** 必須test failure、scope外変更、secret疑い、lock stale。

## 実装へ委ねる選択

- 一時file名の具体形（plan ID、slug、revisionを含み`.agents/tmp/plans/`配下であれば可）。
- `draft`/`publish`の引数名と出力JSONの形。
- `publish`で既存`--source`（任意path）を残すか一時file限定にするか。観測可能な挙動（identity一致時のみ正本化、読み戻し検証）が同じなら可。

## 完了条件

- 草稿が一時fileとして保存され、chatに全文が出ない。
- 人間が編集した一時fileでの承認が拒否される。
- 正本化後の正本・索引のidentityが承認identityと一致し、一時fileが残らない。失敗時は残る。
- 一時草稿がCycleのcurrent planとして解決されない。
- 影響scenarioがPASSしlockが最終surfaceを指す。全unit testがGREEN。
