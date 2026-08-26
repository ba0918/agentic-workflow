# 現行仕様との残存差分を閉じる

**Target specifications:**

- `docs/spec/workflow.md`
  - sections: `review → 修正 → review: 指摘の集合`, `機械の検査は、現実との境界と壊れた入力を見る`, `止まっても続けられる`, `記録の置き場所`
- `docs/spec/implement.md`
  - sections: `残っている作業があるとき`, `検査で示す`, `外で確かめる`, `文書が書き換わったとき`, `完了と引き渡し`
- `docs/spec/review.md`
  - sections: `人が決める指摘`, `誰がレビューするか（モデル）`, `最初のレビュー`, `観点の一覧（profile）`, `差分の再レビューと収束`, `最終全体レビューと 2 人目のレビュアー`, `記録の置き場所`
- `docs/spec/cycle.md`
  - sections: `修正を委譲する`, `終わったときに見せるもの`
- `docs/spec/README.md`
  - sections: `配布と動かし方`

前の版の手順1〜13によって、brainstorm、plan、implement、review、cycle の正本ランタイムと
skill は一度実装されました。しかし最終成果物を仕様書へ付き合わせた結果、テストが通っていても
実際の運用では完了や再開を誤る箇所と、review の入口で仕様上の選択を受け取れない箇所が残って
いました。この版は、確認済みの残存差分だけを閉じます。前の版は Git 履歴から参照します。

仕様で使う「読み込み境界」とは、ファイルやコマンド入力をランタイム内部の値へ変換する入口です。
壊れた入力と不正な状態遷移はここで拒否します。一方、独自の文書指紋、出来事を結ぶ指紋の鎖、
書いた直後に自分の出力を読み直すだけの検査は追加しません。

## この計画で採る方針

- **完了はコミットの有無だけで決めない。** 各手順の完了方法と、証拠が記録した変更ファイルの
  有無から、必要な証拠とコミットがそろったかを1か所で導きます。
- **文書改訂は追記の出来事で表す。** 重要でない変更は `recovering`、人が承認した束ね直しは
  `rebound` に新しい手順契約と対応関係を持たせます。binding は上書きしません。
- **人の判断を機械の成功へ偽装しない。** review の人判断は理由つきの専用出来事として記録し、
  oracle の成功や修正コミットを要求しません。
- **安全確認は呼び出し側の固定値にしない。** レビュアーが実施した安全確認の結果を入力として
  必須化し、指摘の集合と同じ出来事へ保存します。ランタイムがレビューの意味を代わりに判断する
  仕組みは作りません。
- **公開された選択肢を入口から終端まで運ぶ。** review の強さ、観点、モデル、任意の2人目の
  レビュアーを CLI、binding、skill の受け渡しで一致させます。

## 再利用するもの

| 層 | 採用または実装 | 理由 |
|---|---|---|
| 実行証拠の解釈 | 実装: implement と review が使う純粋な共通モジュール | 同じ binding と出来事から有効な手順契約と完了状態を1か所で導ける |
| 文書改訂の履歴 | 改修: 既存の `recovering` / `rebound` 出来事 | 追記方式を維持し、binding の上書きや移行処理を避けられる |
| 人判断の記録 | 改修: 既存の review 出来事列 | 指摘の開閉を導く正本がすでにここにある |
| review の設定 | 改修: 既存の binding と Python `argparse` | 新しい設定ファイルや外部依存が不要 |
| 安全確認の結果 | 改修: 既存の reviewer 出力と指摘記録 | 別の安全台帳を作らず、同じレビュー文脈の証拠として残せる |
| 配布 | 採用: 既存の `agentic-skill-vendor` | 正本と skill 内の複製を手編集で二重管理しない |

新しい外部依存は追加しません。新しい binding と出来事は version 2 とし、完成前の version 1
実行は成功・失敗を推測で読み替えず、`legacy_evidence_unsupported` として明示的に拒否します。
既存ファイルを書き換える移行処理は作りません。この変更前に `.agents/evidence/` の未完了実行が
無いことは確認済みです。今回の範囲外である旧 `.agents/artifacts/executions/` も読み替えません。
これは [implement.md](../spec/implement.md) が定める「完成後に新しく始める実行から適用する」
境界です。

Python ランタイムが扱う外部入出力は Git とローカルファイルだけです。人がその場で明示した
2人目のレビュアーを起動し、安全確認済みの入力を渡す責任は review の skill と実行中の
エージェントが持ちます。ランタイムはその設定と結果の証拠だけを検査・保存します。扱う記録は
小さく、性能目標を追加する必要はありません。

## Scope

```text
evals/
  cases/
    ba0918-cycle/
    ba0918-implement/
    ba0918-review/
  inputs/
    ba0918-cycle/
    ba0918-implement/
    ba0918-review/
skills/
  ba0918-cycle/
    SKILL.md
  ba0918-implement/
    SKILL.md
    references/
    scripts/
  ba0918-review/
    SKILL.md
    references/
    scripts/
tools/
  workflow-runtime/
    implement/
      runtime/
    review/
    shared/
    tests/
vendor-lock.json
vendor-manifest.yaml
```

## Steps

### 1. 手順の完了と再開位置を、完了方法から導く

**目的:** 変更を残さない `check` と `external` の手順が、証拠を持っていても未完了へ戻る問題を
直します。

**前提:** なし。

**変更するファイル:** `tools/workflow-runtime/shared/implementation_evidence.py`、
`tools/workflow-runtime/implement/runtime/context.py`、`resume.py`、`cli.py`、
`tools/workflow-runtime/review/review_runtime.py`、`tools/workflow-runtime/tests/implement_evidence_test.py`、
`implement_runtime_test.py`、`review_runtime_test.py`。

**Completion:** test

確かめること:

- `test` と `artifact` は、完了方法に対応する証拠とコミットがあるときだけ完了になる
- `check` は成功した検査証拠があり、その証拠に変更ファイルが無ければコミットなしで完了になる
- `external` は手順書の条件を満たしたかを明示する値を CLI と出来事で必須にし、満たしていない
  記録を完了証拠として受け付けない。結果の要約だけから成功を推測しない
- 条件を満たした `external` は、リポジトリに残す変更が無ければコミットなしで完了になる
- `check` または `external` が変更ファイルを記録した場合は、同じ手順のコミットが無い限り
  未完了になる
- `current-status`、`resume`、`complete`、review の実行入力検査が共通の純粋関数を使い、同じ
  binding と証拠列から同じ有効な手順契約と完了状態を返す
- version 2 の `external` は条件充足が `true` なら完了し、`false` なら記録は残して未完了になる
- 完成前の version 1 について、完了済み・未完了のどちらの fixture も推測で変換せず
  `legacy_evidence_unsupported` として拒否する

**実装側に任せてよい選択:** 完了判定を置く純粋関数の名前と内部の返り値。

**止まる条件:** 完了方法ごとの必要証拠を、現行仕様から一意に導けない場合。

### 2. 文書への自動追従と束ね直しを、再開可能な証拠として残す

**目的:** 重要でない文書変更を記録して続行できず、人が承認した束ね直しでも新しい手順との
対応関係を再開時に使えない問題を直します。

**前提:** 手順1。

**変更するファイル:** `tools/workflow-runtime/shared/implementation_evidence.py`、
`tools/workflow-runtime/implement/runtime/context.py`、`resume.py`、`cli.py`、
`tools/workflow-runtime/review/review_runtime.py`、`skills/ba0918-implement/SKILL.md`、
`skills/ba0918-implement/references/execution.md`、`evidence.md`、
`evals/cases/ba0918-implement/`、`evals/inputs/ba0918-implement/`、
`tools/workflow-runtime/tests/implement_evidence_test.py`、`implement_runtime_test.py`、
`review_runtime_test.py`。

**Completion:** test

確かめること:

- 重要な設計判断が動かなかった文書変更は、変更した文書、現在の Git コミット、理由を持つ
  `recovering` として同じ実行へ追記される
- `documents-followed` のような、記録できない別名の出来事を返さない
- `rebound` は改訂後の承認コミット、新しい手順契約、旧手順から新手順への対応表、理由を持つ
- `recovering` と `rebound` が指す Git コミットは実在し、その tree から対象の plan と仕様節を
  読める場合だけ追記する。SHAの形だけが正しい架空コミットは拒否する
- 対応表は旧手順と新手順の存在、一対一性、完了方法を読み込み境界で検査し、曖昧な対応を
  ランタイムが推測しない
- 同じ内容で完了済みの手順だけ証拠を持ち越し、変更された手順と新しい手順のうち最初のものから
  再開する
- binding を上書きせず、最新の `rebound` から有効な承認コミットと手順契約を導く
- review の実行入力検査も同じ有効な承認コミット、手順契約、完了状態を使う
- implement の skill、補足文書、評価ケースが、自動追従と人が承認する束ね直しのCLI入力、
  対応表、再開位置を同じ意味で受け渡す

**実装側に任せてよい選択:** 対応表を CLI へ渡す引数の形と、出来事内の内部フィールド名。

**止まる条件:** 旧証拠を削除・書き換えないと束ね直せない場合、または手順対応を機械が意味判定
しなければならない場合。

### 3. 人の判断で review の指摘を閉じられるようにする

**目的:** `human_judgment` の指摘と、人が直さないと決めた機械検証可能な指摘を、理由つきで
閉じられない問題を直します。

**前提:** なし。

**変更するファイル:** `tools/workflow-runtime/review/review_runtime.py`、
`tools/workflow-runtime/tests/review_runtime_test.py`。

**Completion:** test

確かめること:

- 指摘の集合を固定したあとに存在する `open` の指摘だけが人判断の対象になる
- 人の決定内容と空でない理由を、上書きしない専用の出来事として記録する
- 人判断による終了は oracle の成功、修正コミット、`Finding: <id>` trailer を要求しない
- 機械検証による終了は従来どおり、限定レビュー、成功した oracle、trailer つき修正コミットを
  必須とする
- 人が閉じた指摘を、後続の oracle 結果が自動で開き直したり上書きしたりしない

**実装側に任せてよい選択:** 専用 CLI と出来事の名前。

**止まる条件:** 人の判断を認証する新しい権限基盤が必要になった場合。

### 4. review の安全確認と公開オプションを、記録まで一貫させる

**目的:** CLI が安全確認を無条件に完了扱いする問題と、仕様にある review の選択肢を受け取れない
問題を直します。

**前提:** 手順3。

**変更するファイル:** `tools/workflow-runtime/review/review_model.py`、`review_runtime.py`、
`tools/workflow-runtime/tests/review_model_test.py`、`review_runtime_test.py`、
`skills/ba0918-review/SKILL.md`、`skills/ba0918-review/references/review.md`、`evidence.md`、
`evals/cases/ba0918-review/`、`evals/inputs/ba0918-review/`。

**Completion:** test

確かめること:

- `record-findings` は、呼び出し側で固定した真偽値ではなく、同じレビュアーが実施した安全確認の
  結果を明示入力として要求する
- 安全確認が未完了、必須項目不足、または安全上の未解決事項がある場合は指摘集合を成功として
  記録せず、再開可能な未完了状態を保つ
- 安全確認の記録は短い判定と根拠だけを持ち、生ログや秘密情報を複製しない
- `--level=light|standard`、`--profile`、`--model`、`--second-reviewer`、`--second-model` を
  仕様どおり受け取り、選択値と選択元、実際に使ったモデルを binding とreview出来事へ残す
- 既定の強さは `standard`。profile は変更ファイルの種類から選び、明示指定で上書きできる
- 2人目のレビュアーはその場で明示された場合だけ1回動き、許可を次のreviewへ持ち越さない
- 2人目へ渡す入力は plan と差分だけに限定し、送信前に秘密情報を検査する。最初のレビュアーの
  結論は渡さず、独立した見方を保つ
- 2人目の実行先は差し替え可能な入口として扱う。利用できない場合は警告を記録し、最初の
  レビュアーだけでreviewを続ける
- Python ランタイムは2人目の実行先へ接続せず、設定と結果の証拠だけを扱う。skill が人の
  明示指定を確認し、実行先の起動、秘密情報検査済みpayloadの受け渡し、結果の取り込みを行う
- skill、CLI、評価ケースが同じ入口と受け渡しを説明する

**実装側に任せてよい選択:** 安全確認の入力ファイルと内部データの最小形式、CLI 内での引数配置。

**止まる条件:** 安全確認の意味をランタイムだけで自動判定する必要が生じた場合、または2人目の
レビュアー用の新しい永続サービスが必要になった場合。

### 5. cycle の修正委譲へ指摘 ID の契約を渡す

**目的:** cycle が修正役へ、コミット末尾の `Finding: <id>` を要求していないため、review が
修正差分を受け取れない問題を直します。

**前提:** 手順3、4。

**変更するファイル:** `skills/ba0918-cycle/SKILL.md`、`evals/cases/ba0918-cycle/`、
`evals/inputs/ba0918-cycle/`。

**Completion:** artifact

確かめること:

- cycle は修正役へ、対象の指摘 ID ごとにコミット末尾へ `Finding: <id>` を書くよう明示する
- 1コミットが複数の指摘を直す場合は、対象となる全IDの trailer を要求する
- trailer の無い修正を完了報告から推測で関連付けず、review へそのまま渡さない
- 指摘本文を命令ではなくデータとして扱い、仕様、plan、安全境界を修正権限の根拠にする
- 独立した文書レビューで、cycle と review の受け渡しが一致する

**止まる条件:** Git trailer 以外の修正対応付け方式へ仕様を変更する必要が出た場合。

### 6. 正本を skill へ再配布し、全体を検証する

**目的:** 正本ランタイム、skill 内の配布用複製、仕様、評価ケースを同じ状態へそろえます。

**前提:** 手順1〜5。

**変更するファイル:** `skills/ba0918-implement/scripts/`、`skills/ba0918-review/scripts/`、
`tools/workflow-runtime/implement/implement_runtime.py`、`tools/workflow-runtime/review/review_runtime.py`、
`vendor-lock.json`、`vendor-manifest.yaml`。

**Completion:** check

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`
- `bunx skills-ref validate skills/ba0918-brainstorm`
- `bunx skills-ref validate skills/ba0918-plan`
- `bunx skills-ref validate skills/ba0918-cycle`
- `bunx skills-ref validate skills/ba0918-implement`
- `bunx skills-ref validate skills/ba0918-review`
- `skill_smoke_dir="$(mktemp -d)"; trap 'rm -r -- "$skill_smoke_dir"' EXIT; cp -R skills/ba0918-implement "$skill_smoke_dir/ba0918-implement"; env -i PATH="$PATH" python3 "$skill_smoke_dir/ba0918-implement/scripts/implement_runtime.py" --help`
- `skill_smoke_dir="$(mktemp -d)"; trap 'rm -r -- "$skill_smoke_dir"' EXIT; cp -R skills/ba0918-review "$skill_smoke_dir/ba0918-review"; env -i PATH="$PATH" python3 "$skill_smoke_dir/ba0918-review/scripts/review_runtime.py" --help`

確かめること:

- 正本と配布用スクリプトが一致する
- `tools/workflow-runtime/shared/implementation_evidence.py` を、implement-runtime と
  review-runtime の両vendor契約から各 skill の `scripts/implementation_evidence.py` へ生成する。
  両entry pointはこの同じAPIを読み、リポジトリ内の `shared/` が無い単体コピーでも起動する
- 変更を残さない手順の完了と再開、文書追従、束ね直し、人判断、安全確認、公開オプション、
  trailer の受け渡しにそれぞれ回帰テストまたは評価ケースがある
- 壊れた入力と不正な状態遷移は各記録の読み込み境界で拒否される
- 独自の文書指紋、出来事の指紋鎖、出力直後の自己検査、新しい外部依存が増えていない
- 最初に全体レビューを1回行い、指摘修正は対象と影響範囲だけ、最後に全体レビューを1回だけ行う
- 最終全体レビューの新規指摘は限定レビューで閉じ、最終全体レビューを繰り返さない
- 別文脈の最終レビュアーが仕様、skill、ランタイム、テスト、評価ケースを照合し、未解決の指摘が
  無いと判断する

**止まる条件:** 検証を通すために仕様の意味、新しい外部依存、永続化方式、または人が判断する
境界を変える必要が出た場合。

## 完了後の扱い

- cycle と最終成果物の確認が終わるまで、この手順書は `docs/plans/` に残す
- 人が最終成果物を受け入れたら、この手順書を作業ツリーから削除する。過去の内容は Git 履歴で読む
- 旧 `.agents/artifacts/ideas/` は今回の範囲外とし、削除も移行も行わない
