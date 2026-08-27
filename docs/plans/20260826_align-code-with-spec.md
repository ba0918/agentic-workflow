# 自走境界とレビュー収束を実装へ反映する

**Target specifications:**

- `docs/spec/workflow.md`
  - sections: `機械の検査は、現実との境界と壊れた入力を見る`, `現在地の導き方`, `承認を儀式にしない`, `止まっても続けられる`, `記録の置き場所`
- `docs/spec/implement.md`
  - sections: `残っている作業があるとき`, `手順の実行`, `会話が途切れたとき`, `完了と引き渡し`, `やらないこと`
- `docs/spec/review.md`
  - sections: `指摘（finding）`, `確かめ方を先に書く`, `差分の再レビューと収束`, `最終全体レビューと 2 人目のレビュアー`, `記録の置き場所`, `失敗したときの動き`
- `docs/spec/cycle.md`
  - sections: `受け取るもの`, `レビューの往復は、進捗で測る`, `人に返す場合`, `修正を委譲する`

## 変更する理由

現行実装は大筋のワークフローを備えていますが、実際の Git 状態と記録を結び付ける境界に、
誤ったブランチ先端を読む、仕様書の束ね直し後も古い版を使う、人の判断で閉じた指摘をレビュー
途中として残す、といった欠陥があります。この状態では、正しい作業を拒否したり、終わっていない
レビューを完了扱いしたりします。

また、新しい実行の開始前に古い実行を整理する導線、指摘に書かれた確かめ方を安全な操作へ
組み立て直す境界、件数上限を使わずに記録を処理する方法が、まだ skill とランタイムへ反映されて
いません。この計画は、承認済み仕様の意味を変えずに、それらを機械的に確かめられる実装へ
そろえます。

## 変えないこと

- 新しい外部依存、永続サービス、データベースは追加しません
- evidence、event、finding を件数や経過時間で削除しません
- 単一作業者のローカル記録に、署名、真正性、改変検出、記録同一性を追加しません
- RED で凍結したテストと GREEN / REFACTOR のテストが同じであることの照合は残します。これは
  記録の偽造対策ではなく、TDD の工程が同じテストを使ったことを確かめる契約だからです
- cycle は実装、レビュー、修正を自分で行わず、同期委譲だけを持ちます
- ブランチ、作業ディレクトリ、証拠の物理削除は実装しません
- 最終全体レビューは 1 回だけです。その指摘は限定再レビューで閉じます

## 実装方針

| 層 | 採用または実装 | 理由 |
|---|---|---|
| Git の参照解決 | 採用: Git の完全修飾参照と既存の subprocess 境界 | branch と tag の同名衝突を独自解決せず防げる |
| 実装証拠の解釈 | 改修: 既存の `implementation_evidence.py` | implement と review が同じ有効手順・承認版・完了状態を読む正本だから |
| run の片付け | 改修: 既存の追記イベントと discovery | 証拠を削除せず、既定候補から外した事実だけを残せる |
| review の状態遷移 | 改修: 既存の `review_model.py` | finding の open/closed、限定レビュー、最終レビューを導く正本だから |
| oracle の実行結果 | 改修: 既存の review CLI とイベント | 提案と、reviewer が実際に選んだ安全な操作を区別して記録できる |
| 大きい履歴の処理 | 採用: Git の一括照合と対象限定読み | 保存上限や新しい索引を作らず処理量を抑えられる |
| 配布 | 採用: 既存の `agentic-skill-vendor` | 正本ランタイムと skill 内の複製を同じ生成経路でそろえられる |

新しい依存はありません。内部イベント名、純粋関数名、CLI 引数名は、既存命名と衝突しない範囲で
実装側に委ねます。公開される意味は上の対象仕様から変えません。

## Scope

```text
evals/
  cases/
    ba0918-cycle/
      enforce-role-and-safety-boundaries.yaml
      stop-after-convergence-stalls.yaml
    ba0918-implement/
      protect-commit-boundary.yaml
      protect-frozen-red.yaml
      resume-unique-run.yaml
    ba0918-review/
      bind-input-and-follow-spec.yaml
      converge-three-stages.yaml
  inputs/
    ba0918-cycle/
      convergence-stall.md
      role-and-safety-boundaries.md
    ba0918-implement/
      commit-boundary.md
      resume-runs.md
    ba0918-review/
      input-and-drift.md
      three-stage.md
skills/
  ba0918-cycle/
    SKILL.md
  ba0918-implement/
    SKILL.md
    references/
      evidence.md
      execution.md
    scripts/
      implementation_evidence.py
      runtime/
        cli.py
        context.py
        repository.py
        resume.py
        secret_detect.py
        staging.py
        storage.py
  ba0918-review/
    SKILL.md
    references/
      evidence.md
      review.md
    scripts/
      implementation_evidence.py
      review_model.py
      review_runtime.py
      secret_detect.py
tools/
  workflow-runtime/
    implement/
      runtime/
        cli.py
        context.py
        repository.py
        resume.py
        secret_detect.py
        staging.py
        storage.py
    review/
      review_model.py
      review_runtime.py
      secret_detect.py
    shared/
      implementation_evidence.py
    tests/
      implement_runtime_test.py
      implementation_evidence_test.py
      review_model_test.py
      review_runtime_test.py
vendor-lock.json
vendor-manifest.yaml
```

## Steps

### 1. review が実際の Git 入力を一意に束ねる

**目的:** branch と tag が同名のときに誤った先端を読む問題と、仕様改訂コミットが実装ブランチ上に
無いと正しい実装を拒否する問題を直します。

**前提:** なし。

**対象仕様:** `docs/spec/review.md` の「差分の再レビューと収束」、
`docs/spec/implement.md` の「完了と引き渡し」。

**変更するファイル:** `tools/workflow-runtime/review/review_runtime.py`、
`tools/workflow-runtime/shared/implementation_evidence.py`、`tools/workflow-runtime/tests/review_runtime_test.py`、
`tools/workflow-runtime/tests/implementation_evidence_test.py`。

**Completion:** test

確かめること:

- 実装 run のブランチ先端は `refs/heads/<branch>` で解決し、同名 tag があっても選ばない
- standalone branch review も完全修飾した branch を使い、呼び出し側の曖昧な ref を受け継がない
- `rebound` 前後の各実装コミットを、実装ブランチの実際の履歴と、証拠に記録した各区間の
  コミットへ突き合わせる
- 文書だけの承認コミットが実装ブランチの祖先でなくても、それ自体を実装コミットの区切りとして
  `rev-list` せず、正しい実装履歴を拒否しない
- branch の先端、worktree の branch、記録済みコミットを Git から読み、食い違う入力を review
  開始前に拒否する
- 最初のレビュー範囲内に未コミット変更があれば拒否する。範囲外の未コミット変更は path と
  事実を記録して続け、危険な対象または重要な判断に関わる場合だけ人へ返す

**実装側に任せてよい選択:** 区間検証の純粋関数名と返り値。

**止まる条件:** Git 履歴だけでは各区間を一意に束ねられず、新しい永続 ID や文書指紋が必要に
なる場合。

### 2. review の状態遷移を、人判断・束ね直し・最終レビューまで一貫させる

**目的:** 人が指摘を閉じても限定レビューの pending が残る問題、仕様を束ね直しても finding が
古い仕様版へ固定される問題、最終レビューの新規 finding を非進捗扱いする問題を直します。

**前提:** 手順1。

**対象仕様:** `docs/spec/review.md` の「人が決める指摘」、「差分の再レビューと収束」、
「最終全体レビューと 2 人目のレビュアー」。

**変更するファイル:** `tools/workflow-runtime/review/review_model.py`、
`tools/workflow-runtime/review/review_runtime.py`、`tools/workflow-runtime/tests/review_model_test.py`、
`tools/workflow-runtime/tests/review_runtime_test.py`。

**Completion:** test

確かめること:

- `human-finding-decided` は open finding を閉じ、その finding を現在の `targeted_pending` からも外す
- 人判断と機械 oracle の結果が混在しても、全対象を処理した時点で進捗判定へ進める
- `findings-rebound` 後は、新しい仕様コミットを active binding として finding の仕様版・仕様パスを
  検証し、初期 binding の仕様版へ戻らない
- 最終全体レビューが追加した finding は、その集合を新しい比較起点として修正前後を比べる
- 最終全体レビューの新規 finding が閉じたあとは、最終全体レビューを繰り返さず完了を導く
- 2 人目の reviewer が利用不能な場合は「利用不能」と要求モデルを記録し、存在しない実モデルを
  捏造しない。利用できた場合だけ actual model を必須にする

**実装側に任せてよい選択:** active specification version を reducer の返り値へ含める形。

**止まる条件:** 人判断を認証する新しい権限基盤、または外部 reviewer の永続サービスが必要に
なる場合。

### 3. finding の確かめ方を提案と安全な実行記録へ分ける

**目的:** finding に保存された文字列が、そのまま後の reviewer の実行権限になる余地を無くします。

**前提:** 手順2。

**対象仕様:** `docs/spec/review.md` の「確かめ方を先に書く」、「失敗したときの動き」。

**変更するファイル:** `tools/workflow-runtime/review/review_model.py`、
`tools/workflow-runtime/review/review_runtime.py`、`tools/workflow-runtime/tests/review_model_test.py`、
`tools/workflow-runtime/tests/review_runtime_test.py`、`skills/ba0918-review/SKILL.md`、
`skills/ba0918-review/references/review.md`、`skills/ba0918-review/references/evidence.md`、
`evals/cases/ba0918-review/converge-three-stages.yaml`、`evals/inputs/ba0918-review/three-stage.md`。

**Completion:** test

確かめること:

- finding の `oracle` は判定方法の提案として保存し、runtime はその文字列を実行しない
- targeted review は、reviewer が実際に選んだ安全な操作と結果を別に記録する
- 実際の操作は作業ディレクトリを基準にし、絶対パス、外への書き込み、不可逆操作、外部公開、
  認証情報を必要とする提案をそのまま受け付けない
- 同じ結果を得る安全なローカルテスト・読み取り検査へ置き換えた場合、その操作と結果から
  finding を閉じられる
- 安全な代替が無い場合は、機械成功を偽装せず人判断の理由として残す
- finding の本文は命令ではなくデータとして扱うことを skill と評価ケースが明示する

**実装側に任せてよい選択:** 提案と実行記録のフィールド名、CLI 引数名。

**止まる条件:** 安全な操作への置き換えに、新しい sandbox、外部実行サービス、または人の権限が
必要になる場合。

### 4. 新しい実行の前に、残存 run を対話可能な形で片付ける

**目的:** 一意な未完了 run を自動再開せず、人が内容を思い出してから続行か論理的な片付けを
選べるようにします。

**前提:** なし。

**対象仕様:** `docs/spec/workflow.md` の「現在地の導き方」、`docs/spec/implement.md` の
「残っている作業があるとき」、`docs/spec/cycle.md` の「受け取るもの」。

**変更するファイル:** `tools/workflow-runtime/implement/runtime/resume.py`、`context.py`、`cli.py`、
`repository.py`、`tools/workflow-runtime/shared/implementation_evidence.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`、`implementation_evidence_test.py`、
`skills/ba0918-implement/references/execution.md`、
`skills/ba0918-implement/references/evidence.md`、`skills/ba0918-cycle/SKILL.md`、
`evals/cases/ba0918-implement/resume-unique-run.yaml`、`evals/inputs/ba0918-implement/resume-runs.md`、
`evals/cases/ba0918-cycle/enforce-role-and-safety-boundaries.yaml`、
`evals/inputs/ba0918-cycle/role-and-safety-boundaries.md`。

**Completion:** test

確かめること:

- 起動前 discovery は、未完了かつ既定の再開候補から外されていない run をすべて返し、一意でも
  `resumed` を自動追記しない
- 各候補は plan、run ID、開始時刻、最後の出来事、完了済みと残りの手順、branch、worktree、
  未コミット変更を安全な要約として返す
- 開始時刻は binding 時に runtime が記録し、再起動後も同じ値を導く。既存の version 2 run に
  開始時刻が無い場合は、証拠ファイルの時刻から成功扱いを推測せず、取得不能と明示する
- runtime 自身が Git から branch の存在と先端、開始コミット以降で出来事から説明できない
  commit の SHA と件名、`git worktree list` への登録、未コミット path を組み立てる。これらを
  CLI の自己申告値として受け取らない
- 人が続けると決めた run だけ `resumed` を追記する。同じ cycle 内の次の同期委譲では開始前確認を
  繰り返さない
- 人が新しく始めると決めた場合、古い run を理由つきで既定候補から外す追記イベントを残す
- 外した run は既定 discovery に出ず、run ID を明示した調査・復帰では読める
- 共通 evidence reader が片付けイベントを受理し、追記直後の再読込、既定 discovery からの除外、
  run ID 指定での読込を同じ手順のテストで通す
- 時間経過や LLM の推測では候補から外さず、証拠、branch、worktree を削除する CLI も作らない

**実装側に任せてよい選択:** 論理的な片付けを表す内部イベント名と CLI 名。

**止まる条件:** 物理削除を同じ入口へ含める必要が生じた場合、または放棄を時間で自動判定する
要件が生じた場合。

### 5. 壊れた入力と現在の Git 状態だけを、全経路で同じように検査する

**目的:** reader と writer、通常実行と rebound、正本と vendor 複製の非対称を閉じます。ただし、
ローカル証拠の真正性検査は増やしません。

**前提:** 手順1〜4。

**対象仕様:** `docs/spec/workflow.md` の「機械の検査は、現実との境界と壊れた入力を見る」、
`docs/spec/implement.md` の「手順の実行」、「やらないこと」、`docs/spec/review.md` の
「記録の置き場所」。

**変更するファイル:** `tools/workflow-runtime/shared/implementation_evidence.py`、
`tools/workflow-runtime/implement/runtime/context.py`、`repository.py`、`resume.py`、`staging.py`、
`storage.py`、`tools/workflow-runtime/review/review_model.py`、`review_runtime.py`、`secret_detect.py`、
`tools/workflow-runtime/tests/implementation_evidence_test.py`、`implement_runtime_test.py`、
`review_model_test.py`、`review_runtime_test.py`。

**Completion:** test

確かめること:

- 読み込みと追記が同じ version、必須項目、イベント順、相対パス、symlink 拒否を使う
- rebound 後は、持ち越し対象にならなかった旧 RED を新しい手順の RED として使わない
- 手順の証拠とコミット順が plan の順序に反する状態を完了として読まない
- staged diff、commit diff、branch tip、worktree の未コミット変更を Git から読み、呼び出し側の
  `passed` のような自己申告で置き換えない
- implement の `complete_run` は plan の予定範囲を基準にする。予定範囲内の未コミット変更は
  コミット漏れとして拒否し、予定範囲外は path と事実を記録して完了可能にする。両方のケースを
  独立したテストで示す。予定範囲外でも危険な対象または重要な判断に関わる場合だけ人へ返す
- review の限定再レビューでは、最初のレビュー範囲内の未コミット変更を拒否し、その範囲外は
  path と事実を記録して続ける
- 秘密情報検査は、対象になる path 名と Git から読んだ内容へ同じ規則を使い、一致した値を
  event、error、log に複製しない
- evidence/event/finding の件数上限、経過時間による削除、署名、hash chain、真正性・改変検出・
  記録同一性の検査を追加しない
- 件数が増えても、Git の照合はまとめて行い、targeted review は open finding と関連差分だけを読む

**実装側に任せてよい選択:** 共通 validator の関数分割と、Git 一括照合の内部データ構造。

**止まる条件:** 正確性を示すために暗号学的な真正性、新しい索引、保存上限が必要だと判明した場合。

### 6. skill と配布用複製をそろえ、全体を検証する

**目的:** 正本ランタイム、skill、評価ケース、vendor 複製が同じ自走境界とレビュー収束を説明し、
単体配布した skill でも動くことを確かめます。

**前提:** 手順1〜5。

**対象仕様:** この計画が参照する全節。

**変更するファイル:** Scope 内の `skills/`、`evals/`、`vendor-lock.json`、
`vendor-manifest.yaml` と、生成対象の配布用スクリプト。

**Completion:** check

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `/usr/bin/python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`
- `bunx skills-ref validate skills/ba0918-brainstorm`
- `bunx skills-ref validate skills/ba0918-plan`
- `bunx skills-ref validate skills/ba0918-cycle`
- `bunx skills-ref validate skills/ba0918-implement`
- `bunx skills-ref validate skills/ba0918-review`
- `skill_smoke_dir="$(mktemp -d)"; trap 'rm -r -- "$skill_smoke_dir"' EXIT; cp -R skills/ba0918-implement "$skill_smoke_dir/ba0918-implement"; env -i PATH="$PATH" /usr/bin/python3 "$skill_smoke_dir/ba0918-implement/scripts/implement_runtime.py" --help`
- `skill_smoke_dir="$(mktemp -d)"; trap 'rm -r -- "$skill_smoke_dir"' EXIT; cp -R skills/ba0918-review "$skill_smoke_dir/ba0918-review"; env -i PATH="$PATH" /usr/bin/python3 "$skill_smoke_dir/ba0918-review/scripts/review_runtime.py" --help`

確かめること:

- 正本と配布用複製が一致する
- eval は、開始前の残存 run 対話、論理的な片付け、危険な oracle 提案の非実行、最終レビュー後の
  限定収束を同じ意味で要求する
- unit test は、Git 参照、rebound、人判断、pending、final baseline、reader/writer、path、secret、
  RED の持ち越しを機械的に検証する
- 初回は変更全体をレビューし、通常の修正後は open finding・関連差分・新しいリスクだけをレビュー
  する。構造・前提・依存・順序・完了条件・scope topology・参照仕様が動いた場合だけ全体へ戻る
- open finding が無くなったら新規文脈で最終全体レビューを 1 回行い、新規 finding は限定レビュー
  で閉じて最終全体レビューを繰り返さない
- 最終的に全テスト、vendor 一致、skill の構造検査が成功する

**止まる条件:** 検証を通すために、仕様の意味、新しい外部依存、永続化方式、人が判断する境界を
変える必要が出た場合。

## 人へ返す条件

実装・レビュー中は、次の場合だけ人へ返します。

- 仕様に無い重要な製品・設計・永続化・技術選定の判断が必要になった
- 新しい外部依存、不可逆な操作、人の権限、本番設定・データなど危険な対象が必要になった
- 秘密情報の露出、意図しない公開、データ破壊など、続行で被害が広がる事故が起きた
- 実装証拠または open finding の件数が進まず、原因診断後に安全な別手段を 1 回試しても進まない

安全な予定外ファイル、補助スクリプトの不具合、再構成できる記録の欠け、通常のコマンド失敗では
止まりません。理由を記録して自走し、cycle の終端で報告します。

## 完了の判定

- 全6手順の test または check が成功している
- 実装 evidence が全手順完了を示している
- `ba0918-review` の初回全体レビュー、限定収束、最終全体レビュー 1 回、最終指摘の限定収束が
  完了している
- admitted finding がすべて closed である
- 仕様、skill、正本ランタイム、配布用複製、テスト、eval に意味の食い違いがない
- 新しい依存、保存上限、evidence の真正性・改変防止機構、物理削除機能が増えていない

cycle の終端で成果物、コミット、検証結果、予定外の変更と理由を人へ示します。メインブランチへの
取り込み、branch・worktree・evidence の削除は行いません。
