# Brainstorm草稿のfile確認方式

**Plan ID:** `20260823043708`  
**Plan revision:** `1`  
**作成日時:** 2026-08-23 04:37:08 JST  
**公開先:** `.agents/artifacts/plans/20260823043708_brainstorm-draft-file-review.md`

**対象仕様:**

- `docs/spec/agentic-workflow.md`
  - 内容identity: `sha256:b50e663b49847b597d1cf4ebce14fcd43c4943acd93da0b4cb30a1f14d3af883`
  - 適用条項: `WF-033`、`WF-039`、`WF-049`、`WF-053`〜`WF-056`、`WF-065`〜`WF-067`
- `docs/spec/plan-skill-migration.md`
  - 内容identity: `sha256:a1f3232e7162b82065b8d1221dac2f106b338303d3e42d9361dd40a526e41d7b`
  - 適用条項: `PL-030`、`PL-033`〜`PL-036`（plan側の同じ契約との整合確認にのみ参照する）

**実装境界資料:**

- `ROADMAP.md`: `sha256:f055692e5c79f8e81a2caef889832c3a914aa1467891d06a63fe5a99e85f6948`
- 発端issue: `.agents/artifacts/issues/20260822152244_replace-plan-draft-chat-with-file-review.md`
- 仕様改訂commit: `9398e486a0ea687b0fbe2b397f1bf10bb9858763`
- 先行cycle（plan側）: `.agents/artifacts/plans/20260823041415_plan-draft-file-review.md`、merge commit `a3e9920`

## 目的

brainstormのwrapで正本spec / ROADMAPへ書き込む内容を、chatへ全文提示する代わりに`.agents/tmp/ideas/`配下の一時fileとして置き、人間が自分のviewerで読んで、そのcontent identityへ承認を結び付けられるようにする。承認後は一時fileを正本の保存先へ移動し、読み戻し一致を確認してから成功とする。

## 利用者が得る結果

- wrap時、chatには正本ごとのpath、content identity、保存先と、`WF-033`の判断材料（各項目の要点、詳細は草稿本文の該当箇所を指す）だけが表示される。草稿全文はchatに現れない。
- 既存specを改訂するwrapでは、草稿は改訂後のfile全体であり、人間は現在の正本とdiffして変更箇所を確認できる。chatの判断材料が改訂条項IDを指す。
- 人間が一時fileを直接編集して承認しても、identity不一致として拒否され、対話による修正に戻される。
- 承認成功後、一時fileは残らず、正本は承認したidentityと一致し、progressは除去される。

## 変更するもの

```text
skills/ba0918-brainstorm/
  SKILL.md
  references/
    wrap-readiness.md
    state.md
  scripts/
    draft.py（新規）

tests/
  brainstorm_draft_test.py（新規）

evals/cases/ba0918-brainstorm/
  wrap-language-readiness.yaml

regression-lock.json
```

上記以外のfileが必要なら、責務、理由、検証方法を新しいplan revisionとして提示する。`state.py`は、progress除去の契約が変わらない限り変更しない。

## 変更しないもの

- plan skill（先行cycleで完了）
- progressの形式、保存、競合検出（`state.py`）
- 正本specとROADMAPの置き場所の決め方（`WF-065`、project合意に従う）
- viewerの選択・起動
- output tokenの実測比較（合意で完了条件から除外）

## 外部への影響と主要risk

- brainstormの正本は複数file（spec複数 + ROADMAP）になり得る。一時fileは正本ごとに作り、承認はすべてのidentityへ結び付ける。
- 既存正本を置き換えるため、移動前に既存正本を一時領域へ退避し、読み戻し不一致や後続fileの失敗時に復元する。復元できない場合は成功を主張せず、状態を明示して停止する。
- 一時fileに正本と同じbytesを置くため、fileを開いただけでは草稿だと分からない。pathとchat表示で区別する。
- 影響scenarioの実process再実走はOpenCodeのquotaを消費する。lockのimpact判定で対象を限定する。
- 新dependency、network、push、PR、mainへの自動mergeは行わない。

## Human gate

本planにplanned Human gateを置かない。草稿の承認はbrainstormの通常の人間確認であり、製品判断はすべて仕様へ反映済みである。

## 実装手順

### 1. 正本ごとの一時草稿を保存するhelperを追加する

**対応仕様:** `WF-053`、`WF-056`、`WF-039`  
**書込み範囲:** `skills/ba0918-brainstorm/scripts/draft.py`、`tests/brainstorm_draft_test.py`

- `draft.py save`を追加する。session ID、repository-relativeな保存先path、標準入力の草稿bytesを受け取り、`.agents/tmp/ideas/<session-id>/`配下へ保存先のbasenameで同一bytesをatomicに書き、同じdirectoryの`manifest.json`へ保存先・一時path・content identityを記録し、pathとidentityをJSONで返す。
- 同じ保存先の草稿が既にある場合は`--replace-identity`で指定したidentityと一致するときだけ置き換え、不一致または未指定なら書かずに失敗を返す。
- 保存先は`.agents/`配下、absolute path、traversal、symlinkを拒否する。草稿bytesにヘッダを足さない。書込み失敗は成功として返さない。

**必要証拠:** 新規testのRED→GREEN、既存brainstorm test全件GREEN。  
**停止条件:** 一時保存の保存先を`.agents/tmp/ideas/`以外にする必要が出た場合。

### 2. 承認済み草稿を移動して正本化するhelperを追加する

**対応仕様:** `WF-054`、`WF-055`、`WF-049`  
**書込み範囲:** `skills/ba0918-brainstorm/scripts/draft.py`、`tests/brainstorm_draft_test.py`

- `draft.py publish`を追加する。session IDと、保存先ごとの承認identityを受け取り、manifestの各草稿について現在のidentityが承認identityと一致する場合だけ正本pathへ移動する。一つでも不一致があれば何も移動せず失敗とし、草稿を残す。
- 既存の正本は移動前に同じ一時directoryへ退避する。移動後に正本を読み戻して一致を確認し、不一致または後続fileの失敗時は退避から復元する。
- すべて成功したときだけ一時directory（草稿、manifest、退避）を削除する。失敗時は残す。識別していない一時fileを削除しない。
- progressの除去は従来どおり`state.py`の`finish_wrap`が行い、本helperは行わない。

**必要証拠:** 編集済み草稿の拒否、複数fileの全件一致時のみ移動、途中失敗時の復元、成功時の一時directory不在、失敗時の残存の各testのRED→GREEN。  
**停止条件:** renameが同一filesystem内で行えない構成が判明した場合（copy+verify+unlinkへの変更はrevisionとして提示）。

### 3. 指示を新しい契約へ同期する

**対応仕様:** `WF-033`、`WF-039`、`WF-053`〜`WF-056`  
**書込み範囲:** `skills/ba0918-brainstorm/SKILL.md`、`skills/ba0918-brainstorm/references/wrap-readiness.md`、`skills/ba0918-brainstorm/references/state.md`

- `wrap-readiness.md`の「draftはchat応答だけで提示し、承認前にdraft fileを作らない」を、「`draft.py save`で正本ごとに一時保存し、chatにはpath、identity、保存先と判断材料の要点だけを出す」に改める。全文のchat複製と要約承認の禁止は残す。判断材料は承認対象でないことを書く。
- 承認後の手順を「`draft.py publish`、読み戻し一致、一時directory不在の確認、`finish_wrap`によるprogress除去」に改める。
- 人間がfileを編集した場合の扱い（拒否して対話で修正）と、再提示時の`--replace-identity`の使い方、既存specの改訂では草稿がfile全体であることと人間がdiffで確認できることを書く。
- `SKILL.md`のBoundary「ordinary dialogueではfileを作らない」は維持し、wrapでの一時保存を許可対象として最小限に追記する。`state.md`は一時草稿がprogressではないことを一文で明記する。

**必要証拠:** 指示の差分、Markdown参照の検査。  
**停止条件:** 指示だけで表現できない動作が見つかった場合（step 1〜2へ戻す）。

### 4. 影響scenarioを改訂して再実走し、lockを更新する

**対応仕様:** `WF-053`〜`WF-055`  
**書込み範囲:** `evals/cases/ba0918-brainstorm/`、`regression-lock.json`

- `wrap-language-readiness.yaml`の「承認前のdraftはchat応答だけで提示し、draft fileを作成・変更しない」を、「承認前の草稿を`.agents/tmp/ideas/`配下の一時fileとして保存し、正本specとROADMAPを変更せず、chatに全文を複製しない」に改訂し、正本不変を機械判定で固定する。
- 他のbrainstorm scenarioは、一時草稿の有無が期待に影響する場合だけ最小限に改訂する。
- `lock.py --impact-scenarios`で影響scenarioを求め、それだけを`opencode-go/deepseek-v4-flash`で再実走する。post-state（一時fileの存在と内容、正本の不変、report本文）から裁定し、lockを更新する。
- scenario改訂のcommitに改訂根拠の条項IDを書く。

**必要証拠:** impact判定の出力、再実走のgrade結果と裁定、lock差分。  
**停止条件:** backend利用不能、quota超過、裁定不能の場合はlockを更新しない。

### 5. 最終検証

**対応仕様:** 全対象条項  
**書込み範囲:** なし（検査のみ）

- 全unit test、`lock.py --check`、`git diff --check`、scope監査、secret形状検査を実行する。
- 結果をworst verdictで集約し、branch、commit列、証拠pathを返す。

**必要証拠:** 各commandの出力とexit code。  
**停止条件:** 必須test failure、scope外変更、secret疑い、lock stale。

## 実装へ委ねる選択

- 一時directory内のfile名とmanifestの形（session IDで区切られ、保存先とidentityが復元できれば可）。
- `save`/`publish`の引数名と出力JSONの形。
- 退避fileの命名。

## 完了条件

- 正本ごとの草稿が一時fileとして保存され、chatに全文が出ない。
- 人間が編集した一時fileでの承認が拒否される。
- 複数正本の承認が全件一致時だけ移動され、途中失敗時に既存正本が復元される。
- 成功時に一時directoryが残らず、失敗時は残る。
- 影響scenarioがPASSしlockが最終surfaceを指す。全unit testがGREEN。
