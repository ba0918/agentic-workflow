# 実装と skill を、承認を減らした現行仕様へ追いつかせる

**Target specifications:**

- `docs/spec/workflow.md`
  - sections: `受け渡す物`, `どのステップにも共通すること`, `承認を儀式にしない`, `文書が書き換わったとき`, `記録の置き場所`
- `docs/spec/brainstorm.md`
  - sections: `途中経過の保存`, `仕上げ（wrap）`, `plan に進めるかの判定`, `skill の構成`
- `docs/spec/plan.md`
  - sections: `手順書に書くこと`, `独立したレビュー`, `承認`, `手順書の改訂`, `skill の構成`
- `docs/spec/cycle.md`
  - sections: `実装を委譲する`, `続けるか止めるかの判定`, `修正を委譲する`, `終わったときに見せるもの`, `skill の構成`
- `docs/spec/implement.md`
  - sections: `始める前に確かめること`, `委譲されて動くとき`, `残っている作業があるとき`, `手順の実行`, `コミット`, `証拠の残し方`, `止まり方`, `文書が書き換わったとき`, `完了と引き渡し`, `skill の構成`
- `docs/spec/review.md`
  - sections: `受け取るもの`, `指摘（finding）`, `最初のレビュー`, `差分の再レビューと収束`, `最終全体レビューと 2 人目のレビュアー`, `直す側との約束`, `記録の置き場所`
- `docs/spec/README.md`
  - sections: `これは何か`, `配布と動かし方`

現行仕様は、人の確認を仕様書、手順書、最終成果物の境界へ集めます。しかし現在の実装と
skill には、文書・出来事の独自ハッシュ、予定範囲を絶対的な許可リストとして扱う処理、
実装途中の成果物承認、固定回数による停止など、以前の契約が残っています。さらに、実装から
review の収束までを束ねる `ba0918-cycle` はまだ存在しません。

この手順書は、正本のランタイム、各 skill の指示、評価ケース、配布用の複製を現行仕様へまとめて
追従させます。作り替えているワークフロー自身は完成まで使わず、TDD、設計、コミット、秘密情報の
規則を直接適用します。

この手順書は、同じ変更を旧仕様に基づいて分割していた
`docs/plans/20260826_plan-artifact-slimming.md` と
`docs/plans/20260826_implement-slimming.md` を統合して置き換えます。旧手順書は承認時に
`docs/plans/` から除き、必要な場合は Git 履歴から参照します。

## この計画で採る方針

- **Git を文書の版と承認の正本にする。** 手順書を承認したコミットから参照仕様を読み、独自の
  SHA-256 は持ちません。RED テストの凍結だけは Git で代替できないため残します。
- **機械は差分を観測し、意味は AI が判断する。** ランタイムは承認コミットと現在の Git 差分を
  返し、重要な設計判断が動いたかを規則で決めません。
- **予定範囲と安全境界を分ける。** Scope 外の通常の補完は理由を記録して通し、秘密情報、危険な
  パス、一時ファイル、ログ、生成物の検査は全コミットへ適用します。
- **正本を直してから配布用の複製を生成する。** `tools/workflow-runtime/` と skill 本文を先に直し、
  `skills/*/scripts/` は vendor 生成で同期します。
- **旧形式は移行しない。** 新しい契約は完成後に始める実行へだけ適用します。

## 再利用するもの

| 層 | 採用または実装 | 理由 |
|---|---|---|
| 文書の版と承認 | 採用: Git CLI と既存の `gitio.py` | 既に必須の基盤で、独自ハッシュと承認台帳を置き換えられる |
| Markdown の読み取り | 採用: 既存の `plan_artifact.py` | 固定形式の2箇所を読む責任が既に集約されている |
| 証拠の保存 | 改修: 既存の `storage.py` と番号付きJSON | 新しい保存方式を増やさず、ハッシュ鎖だけを除ける |
| テストの凍結 | 改修: 既存のTDDランタイム | Gitで代替できない唯一の同一性検査なので維持する |
| orchestration | 実装: `ba0918-cycle` の指示文 | implementとreviewを再利用でき、専用スクリプトは不要 |
| 配布の同期 | 採用: `agentic-skill-vendor` | 正本と複製の二重編集を避けられる |

新しい外部依存は追加しません。Python 標準ライブラリ、Git、導入済みの vendor 生成機構だけを
使います。

## Scope

```text
.gitignore
evals/
  cases/
  inputs/
skills/
  ba0918-brainstorm/
    SKILL.md
    references/
    scripts/
  ba0918-cycle/
    SKILL.md
  ba0918-implement/
    SKILL.md
    references/
    scripts/
  ba0918-plan/
    SKILL.md
    references/
    scripts/
  ba0918-review/
    SKILL.md
    references/
    scripts/
tools/
  workflow-runtime/
    brainstorm/
    implement/
    plan/
    review/
    tests/
vendor-lock.json
vendor-manifest.yaml
```

## Steps

### 1. plan の正本を `docs/plans/` と Git に一本化する

**目的:** `plan.md` の「承認」と「手順書の改訂」に合わせ、草稿、手動の ID・版、仕様書の
内容ハッシュを廃止する。

**前提:** なし。

**変更するファイル:** `tools/workflow-runtime/plan/plan_artifact.py`、
`tools/workflow-runtime/implement/runtime/deps.py`、`types.py`、`planning.py`、`repository.py`、
`context.py`、`resume.py`、`cli.py`、`tools/workflow-runtime/tests/plan_artifact_test.py`、
`implement_runtime_test.py`、`implement_evidence_test.py`。

**Completion:** test

確かめること:

- `docs/plans/` のファイルだけを正本として扱い、パス逸脱とシンボリックリンクを拒否する
- `Target specifications` のパスと節、および `Scope` の木だけを固定形式として読む
- 参照仕様がコミット済みであることを Git で確認し、ハッシュ、Plan ID、版を要求しない
- 草稿保存・publish・置換用 identity の API と CLI が存在しない
- implement側の型、binding、CLIを含む全reader利用箇所も同じコミットで新しいAPIへ移し、
  手動ID・版・文書identityを残さず、全runtime testが通る

**実装側に任せてよい選択:** Git コマンド結果を表す内部データ型とエラー名。

**止まる条件:** Git とは別の承認台帳や承認前の別ファイルが必要になった場合。

### 2. brainstorm の途中経過とwrapから独自ハッシュと草稿置き場を外す

**目的:** `brainstorm.md` に合わせ、途中経過を `.agents/tmp/ideas/` へ移し、別の草稿置き場と
改変防止ハッシュを廃止する。`draft.py` は正本へ直接、安全に書く補助へ縮小する。

**前提:** なし。

**変更するファイル:** `tools/workflow-runtime/brainstorm/state.py`、`draft.py`、
`tools/workflow-runtime/tests/brainstorm_state_test.py`、`brainstorm_draft_test.py`、`.gitignore`。

**Completion:** test

確かめること:

- 状態を `.agents/tmp/ideas/<セッションID>.md` へ安全に保存・復元できる
- 状態に identity を要求しない。整数revisionは、複数会話の古い書き込みを検出する用途だけに残す
- revision競合時は後発候補を時刻付き別ファイルへ退避して停止し、どちらの内容も失わない
- `draft.py` はcanonical文書を所定の場所へ直接書き、パス逸脱、symlink、部分書き込みを防ぐ
- 草稿manifest、別置き場からのpublish、identity照合が残っていない
- 承認後に途中経過を消せる
- `.agents/` 全体がGitから除外され、`docs/` の承認文書は追跡対象になる

**止まる条件:** 整数revision以外の新しい競合制御方式や、複数書き手の自動マージが必要になった場合。

### 3. 実行を Git コミットと番号付き証拠へ束ねる

**目的:** `implement.md` と `cycle.md` に合わせ、証拠を `.agents/evidence/` に置き、cycle が
作った実行IDとGitコミットで文書の版を示す。

**前提:** 手順1。

**変更するファイル:** `tools/workflow-runtime/implement/runtime/types.py`、`storage.py`、
`planning.py`、`repository.py`、`context.py`、`gitio.py`、`cli.py`、
`tools/workflow-runtime/tests/implement_evidence_test.py`、`implement_runtime_test.py`。

**Completion:** test

確かめること:

- 証拠が `.agents/evidence/<手順書ID>/<実行ID>/` に作られる
- binding と `rebound` は手順書を承認した Git コミットを参照する
- 出来事は番号順に1件1ファイルで追記され、identity鎖を持たない
- cycle が委譲開始・終了を記録でき、委譲中のimplementだけが証拠を書く
- TDDの凍結対象だけは同一性検査を維持する

**止まる条件:** 旧形式の証拠を読み替える移行処理が必要になった場合。

### 4. Scope を予定範囲に変え、安全検査を全コミットへ適用する

**目的:** 通常のファイル漏れを自走で補いながら、危険な変更をコミット境界で止める。

**前提:** 手順3。

**変更するファイル:** `tools/workflow-runtime/implement/runtime/planning.py`、`staging.py`、
`cli.py`、`context.py`、`tools/workflow-runtime/tests/implement_runtime_test.py`、
`implement_evidence_test.py`。

**Completion:** test

確かめること:

- Scope外という理由だけで編集・ステージ・コミットを拒否しない
- 通常の補完は理由とパスを記録し、終端報告へ渡す
- 秘密情報、危険なパス、一時ファイル、ログ、生成物を範囲内外を問わず拒否する
- 安全な予定外コミットや変更について途中のhistory承認を要求しない
- 危険な対象または重要な設計判断に関係する変更をコミット前に人へ返せる

**止まる条件:** 危険な対象をファイル名だけで完全に判定する必要が生じた場合。

### 5. 実装途中の承認を重要な例外だけに限定する

**目的:** 成果物と外部確認の受け入れをcycle終端へ集約する。

**前提:** 手順3、4。

**変更するファイル:** `tools/workflow-runtime/implement/runtime/gates.py`、`deliverables.py`、
`cli.py`、`context.py`、`tools/workflow-runtime/tests/implement_runtime_test.py`、
`implement_evidence_test.py`。

**Completion:** test

確かめること:

- `artifact` と `external` で人の承認を要求せず、独立レビュー可能な証拠を残す
- human gate は不可逆な操作、人の権限、危険な対象の事前確認だけを受け付ける
- hook失敗、記録漏れ、凍結テストの取り直しなどを自動回復できる
- 原因診断後に方法を変えても進まない場合だけ人へ返す

**止まる条件:** 成果物の意味を実装途中で人が承認しないと完了を判定できない場合。

### 6. 文書変更と残存実行を意味判定へ渡す

**目的:** 差分の存在だけで停止せず、一意な残存実行を自動再開する。

**前提:** 手順1、3。

**変更するファイル:** `tools/workflow-runtime/implement/runtime/context.py`、`resume.py`、
`planning.py`、`cli.py`、`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** test

確かめること:

- ランタイムは承認コミットと現在の文書の差分を返し、重要度を自動判定しない
- AIの意味判定を記録し、重要な判断が動かなければ現在のコミットへ追従できる
- 重要な判断が動いた場合だけ `rebound` または新規実行の選択を人へ返す
- 未完了実行が一意なら自動再開し、複数候補の場合だけ人へ返す
- 停止記録は文書差分がある状態でも書ける

**止まる条件:** 重要な設計判断の変更を機械規則で決める必要が生じた場合。

### 7. review の記録を Git 版と追記だけにする

**目的:** reviewの文書・出来事ハッシュ鎖を除き、`stale` を非終端へ変える。

**前提:** 手順3。

**変更するファイル:** `tools/workflow-runtime/review/review_model.py`、`review_runtime.py`、
`tools/workflow-runtime/tests/review_model_test.py`、`review_runtime_test.py`。

**Completion:** test

確かめること:

- 実行reviewは `.agents/evidence/<手順書ID>/<実行ID>/review/`、単体reviewは
  `.agents/evidence/reviews/<レビューID>/` に置かれる
- review出来事は番号順の追記で、plan/spec/event/profileのidentity鎖を持たない
- 指摘の状態は `open` と `closed` に限定し、`findings_stale` は再開可能な一時停止になる
- 指摘IDは確かめ方や観測から安定して導ける
- 実行IDの無いreview用に、ブランチまたは2コミットを束ねたstandalone bindingを作れる

**実装側に任せてよい選択:** 指摘IDの内部ハッシュ。文書版や改変防止へ転用しないこと。

**止まる条件:** 同じ実行へ同時に複数reviewを書かせる要件が見つかった場合。

### 8. review を初回全体・限定・最終全体の三段階にする

**目的:** 品質を落とさず、修正中のレビューを収束させる。

**前提:** 手順7。

**変更するファイル:** `tools/workflow-runtime/review/review_model.py`、`review_runtime.py`、
`tools/workflow-runtime/tests/review_model_test.py`、`review_runtime_test.py`。

**Completion:** test

確かめること:

- 初回は全体、修正中は未解決指摘・修正差分・持ち込まれたリスクだけを見る
- 回帰、安全上または致命的な問題を追加し、無関係な軽微事項は終端へ送る
- 未解決数 `(security, critical, warn)` の辞書順減少を進捗として記録する
- 進捗が無い場合は原因診断し、方法変更後も進まない場合だけ人へ返す
- 未解決指摘が無くなると、別文脈の最終全体レビューを必ず1回行う
- 最終レビューの新規指摘は限定再レビューで閉じ、全体レビューを繰り返さない
- 仕様の重要な判断が動かなければGit版へ追従し、動いた場合だけ一時停止する
- ブランチ入力の比較元を明示指定、pull requestの取り込み先、既定ブランチとのmerge-baseの順で決める
- ブランチ、2コミット、implement実行IDの3入力から同じreview工程へ入れる
- 実行IDの無い入力では、人が指定した仕様書または `docs/spec/` を根拠として記録する
- 既定ブランチや比較元を一意に決められない場合は、review開始前に人へ返す

**止まる条件:** 進捗順序、最終レビュー回数、新規指摘の扱いを変える必要が出た場合。

### 9. `ba0918-cycle` をオーケストレータとして追加する

**目的:** implement、review、修正を別文脈へ委譲し、終端まで束ねる入口を作る。

**前提:** 手順3〜8。

**変更するファイル:** `skills/ba0918-cycle/SKILL.md`、`evals/cases/ba0918-cycle/`、
`evals/inputs/ba0918-cycle/`。

**Completion:** artifact

確かめること:

- cycle自身は実装、レビュー、修正をせず同期委譲する
- 実行ID、証拠場所、委譲開始・終了を管理する
- 証拠が増える限り実装委譲を続け、止まれば診断後に方法を1回変える
- reviewの進捗を読み、重要な例外以外では人を呼ばない
- 終端報告は成果物、検証、差分を基本とし、例外事項があるときだけ追加する
- 重要でないファイル漏れでは自走し、重要な設計判断では停止する評価ケースがある
- 別文脈のreviewerが仕様とskill全文を読み、指摘なしと判断する

**止まる条件:** cycle固有の永続状態または専用ランタイムが必要になった場合。

### 10. brainstorm と plan の skill に独立レビューを組み込む

**目的:** 仕様と手順の承認前レビューを、実際のLLM指示へ反映する。

**前提:** 手順1、2。

**変更するファイル:** `skills/ba0918-brainstorm/SKILL.md` と `references/`、
`skills/ba0918-plan/SKILL.md` と `references/`、対応する `evals/cases/` と `evals/inputs/`。

**Completion:** artifact

確かめること:

- brainstormは別文脈のアーキテクトに目的、暗黙の未決定、既存構造との衝突を全体レビューさせる
- 意味が変わる修正後は全体レビューをやり直す
- 保存状態、外部サービス、権限、新しい外部依存を決定・委任・該当なしのいずれかへ確定する
- planは最初に全体レビューを行い、局所修正は影響範囲だけ、構造・前提・順序・依存・完了条件・
  参照仕様が動く場合は全体を見直す
- 両skillとも正本へ直接書き、Gitのステージ済み差分を承認対象にする
- 別文脈のreviewerが仕様、skill、評価ケースを読み、指摘なしと判断する

**止まる条件:** レビューで仕様に無い重要な設計判断が見つかった場合。

### 11. implement と review の skill を新しいランタイムへ合わせる

**目的:** 手順3〜8の振る舞いを、ランタイムを呼ぶ指示とreview観点へ反映する。

**前提:** 手順3〜8。

**変更するファイル:** `skills/ba0918-implement/SKILL.md` と `references/`、
`skills/ba0918-review/SKILL.md` と `references/`、新しい
`skills/ba0918-review/references/profile/document.md`、対応する `evals/cases/` と `evals/inputs/`。

**Completion:** artifact

確かめること:

- implementが自動再開、意味判定、予定範囲の補完、例外だけの人判断、最小終端報告を行う
- reviewが三段階レビュー、動的な指摘追加、進捗診断、非終端のstaleを行う
- 文書用profileが仕様・skill・説明文書の意味と受け渡しをレビューできる
- 古い置き場、草稿、文書identity、固定回数、毎手順承認を期待する評価ケースが無い
- 別文脈のreviewerが仕様、skill、profile、評価ケースを読み、指摘なしと判断する

**止まる条件:** skill本文で仕様を再設計しないとランタイムを呼べない場合。

### 12. 正本から配布用スクリプトを再生成する

**目的:** 正本の変更を配布用の複製へ同期する。

**前提:** 手順1〜8、10、11。

**変更するファイル:** `skills/ba0918-brainstorm/scripts/`、`skills/ba0918-plan/scripts/`、
`skills/ba0918-implement/scripts/`、`skills/ba0918-review/scripts/`、`vendor-lock.json`、
必要な場合だけ `vendor-manifest.yaml`。

**Completion:** check

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `skill_smoke_dir="$(mktemp -d)"; trap 'rm -r -- "$skill_smoke_dir"' EXIT; cp -R skills/ba0918-implement "$skill_smoke_dir/ba0918-implement" && env -i PATH="$PATH" python3 "$skill_smoke_dir/ba0918-implement/scripts/implement_runtime.py" --help`

vendor設定では、`plan_artifact.py` の同じ正本を `ba0918-plan` と `ba0918-implement` の両方へ
生成します。隔離起動では、`ba0918-plan` が隣に無くてもimplementがreaderを読み込めることを
確かめます。一時ディレクトリは検査後に削除します。

**止まる条件:** 配布用の複製を手で修正する必要が生じた場合。

### 13. 全体の回帰検査と仕様適合レビューを通す

**目的:** 個別変更がつながった状態で、コード、skill、仕様の一致を確認する。

**前提:** 手順1〜12。

**変更するファイル:** 新しい製品変更は行わない。失敗の修正は原因を持つ手順へ戻す。

**Completion:** check

**Checks:**

- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`
- `bunx skills-ref validate skills/ba0918-brainstorm`
- `bunx skills-ref validate skills/ba0918-plan`
- `bunx skills-ref validate skills/ba0918-cycle`
- `bunx skills-ref validate skills/ba0918-implement`
- `bunx skills-ref validate skills/ba0918-review`
- `bunx agentic-skill-vendor verify`

確かめること:

- 各仕様契約がコード、skill、評価ケースの少なくとも1つで検証可能になっている
- 文書・出来事identity、古い置き場、草稿publish、固定回数停止、Scope外の一律拒否、毎手順の
  人承認、終端扱いのstaleが残っていない
- REDテストの凍結identityとvendor-lockのdigestは、用途が異なるため残っている
- 別文脈の最終reviewerが全仕様、変更差分、テスト結果を読み、未解決の指摘が無いと判断する

**止まる条件:** 検査を通すために仕様の意味を変更する必要が出た場合。

## 進め方の前提

- 全手順が終わるまで、作り替えている `ba0918-brainstorm`、`ba0918-plan`、`ba0918-cycle`、
  `ba0918-implement`、`ba0918-review` は実行に使わない
- コード変更は失敗するテストを先に追加し、実装・整理後にも同じテストを通す
- 手順ごとに1つ以上の論理的なコミットを作り、メッセージへ変更理由を書く
- 独自の証拠記録は作らず、Gitコミットとテスト結果を作業記録にする
- 旧形式の途中実行やartifactを移行しない
