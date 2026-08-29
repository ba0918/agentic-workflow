# runtimeから文字列照合の行為者ゲートを外す

## What & Why

仕様は、補助スクリプト（runtime）がコマンドや変更内容の文字列を照合して AI や人の行為を制限しない、と決めました（`docs/spec/workflow.md`「文字列照合で行為者を縛らない」）。現在の runtime には、その決定に反する検査が 3 か所残っています。

1. review が指摘の確かめ方を実行した記録（操作の文字列）を、固定の許可一覧、絶対パスと `..`、シェルの記号、シェル構文の解釈で拒否する検査（`review_support/validation.py` の `review_execution` と `review_operation_allowed`）
2. implement がコミット前の変更内容と再開時のコミット件名を、秘密らしい文字列の正規表現で拒否または伏せ字にする検査（`implement/runtime/secret_detect.py`、`safety.py` の `content_safety`、`resume.py`）。review の記録文字列にも同じ検出器が掛かっています
3. brainstorm の途中経過の保存が、別の正規表現で秘密らしい値を拒否する検査（`brainstorm/state.py` の `SECRET`）

この plan は、これらを削除し、runtime が記録に対して行う検査を形式（空でない、NUL 文字を含まない、長さが上限内）だけにします。skill の本文と補助文書も同じ意味へ追従させます。

## Goals

- 固定の一覧に無い操作（このリポジトリの品質ゲートを含む）と、絶対パス・`..`・シェルの記号・閉じていない引用符を含む操作を、review の記録としてそのまま受け付けます
- 秘密らしい文字列を理由にした拒否と伏せ字を、implement、review、brainstorm から無くします。コミット前検査は、パス名を見る危険な対象の検査だけになります
- 記録の形式検査（空、NUL 文字、長さ上限）は残し、review の操作記録にも NUL 文字の拒否を揃えます
- 配布用の複製と skill の本文が正本と一致した状態で終えます

## Non-goals

- パス名（ファイル名）を見る危険な対象の検査（`.env`、一時ファイル、ログ、生成物、`path_safety.py` と `staging.py`）は変更しません。仕様がこれを例外として残しています
- 指摘の ID の作り方、evidence の version 2 形式、保存場所、公開 facade の関数名と引数は変更しません
- review profile にある「Allowed oracles」（指摘に書く確かめ方の種類）は、記録する操作の許可一覧ではないので触りません
- `docs/spec/quality-tooling.md`「runtimeリファクタリング」の「137件」は、完了済みのリファクタリング単位を述べた文なので書き換えません
- 秘密検出を LLM 検査や専用検出器で置き換える実装は行いません。仕様が、責任を行為者と外部の規則、専用検出器は plan の Checks へ、と定めています
- `implement/runtime/gitio.py` の `run_git_bytes` の定義は、呼び出し元が無くなっても残します。ただし `safety.py` 側の未使用になる import と、`content_safety` 専用の private helper（`_diff_content`、`_untracked_content`）は削除します。品質ゲートが未使用 import を拒否するからです
- `skills/ba0918-review/SKILL.md` は変更しません。該当箇所はすでにレビュアーの行動規範として書かれており、runtime の検査とは読めません

## Design

### Reuse decisions

| Layer | Adopt / build | Reason |
|---|---|---|
| 記録の形式検査 | adopt | `review_support/validation.py` の `bounded_text` と `_safe_string` に、空・長さ上限・NUL 文字の検査がすでにあります。秘密検出の呼び出しを外し、`bounded_text` に NUL 文字の検査を加えるだけです |
| コミット前のパス検査 | adopt | `safety.py` の `assess_safety` と `staging.py` が既にパス名の検査を担います。変更内容を読む `content_safety` は秘密検出のためだけに存在するので、丸ごと削除します |
| 配布用の複製 | adopt | `agentic-skill-vendor` の `gen` と `verify` で正本から生成します。手編集しません |

### 削除する物と残す物

`review_execution` は、操作の文字列を `bounded_text` に通し、`working_directory: "."`、終了コード、要約と共に記録する関数になります。`review_operation_allowed`、`shlex` による解釈、絶対パスとシェル記号の判定、失敗コード `review_operation_unsafe` は消えます。形式に反する操作の失敗コードは、他の記録文字列と同じ `bounded_text_invalid` になります。

`secret_detect.py` は削除し、`vendor-manifest.yaml` の 2 つの対応行（implement と review への複製）も外します。`content_safety` と、それを呼ぶ `evidence.py` の 2 か所、`completion.py` の 1 か所、失敗コード `secret_content` を削除します。`resume.py` は件名をそのまま返します。

`brainstorm/state.py` の `SECRET` と、それを使う `save_progress` の分岐を削除します。`UnsafeProgress` は、保存先がリポジトリの外を指す場合などの既存用途で残ります。

削除に伴い、拒否を確かめていたテストは「受け付ける」ことを確かめるテストへ置き換えます。テストの追加は、仕様の反例（受け付けるべき物が拒否される）を検出する物に限ります。

**Verification coverage:**

- `docs/spec/workflow.md` / `文字列照合で行為者を縛らない` -> `1:test`
- `docs/spec/review.md` / `走らせた操作をそのまま記録する` -> `1:test`
- `docs/spec/workflow.md` / `文字列照合で行為者を縛らない` -> `2:test`
- `docs/spec/implement.md` / `コミット` -> `2:test`
- `docs/spec/implement.md` / `何を見せるか` -> `2:test`
- `docs/spec/workflow.md` / `文字列照合で行為者を縛らない` -> `3:test`
- `docs/spec/brainstorm.md` / `どこに保存するか` -> `3:test`
- `docs/spec/review.md` / `走らせた操作をそのまま記録する` -> `4:artifact`
- `docs/spec/workflow.md` / `文字列照合で行為者を縛らない` -> `4:artifact`
- `docs/spec/quality-tooling.md` / `Pythonの検査対象` -> `5:check`

## Scope

```text
tools/
  workflow-runtime/
    brainstorm/
      state.py
    implement/
      runtime/
        completion.py
        evidence.py
        resume.py
        safety.py
        secret_detect.py
    review/
      review_support/
        validation.py
    tests/
      brainstorm_state_test.py
      implement_evidence_test.py
      implement_runtime_test.py
      review_findings_test.py
      review_runtime_test.py
skills/
  ba0918-brainstorm/
    references/
      state.md
    scripts/
      state.py
  ba0918-implement/
    SKILL.md
    references/
      evidence.md
    scripts/
      runtime/
        completion.py
        evidence.py
        resume.py
        safety.py
        secret_detect.py
  ba0918-review/
    references/
      evidence.md
      review.md
    scripts/
      review_support/
        validation.py
      runtime/
        secret_detect.py
evals/
  cases/
    ba0918-implement/
      protect-commit-boundary.yaml
    ba0918-review/
      bind-input-and-follow-spec.yaml
vendor-manifest.yaml
vendor-lock.json
```

`secret_detect.py` は正本（`tools/workflow-runtime/implement/runtime/`）を Step 2 で削除し、`vendor-manifest.yaml` から対応行を外します。2 つの配布用複製（`skills/ba0918-implement/scripts/runtime/`、`skills/ba0918-review/scripts/runtime/`）は手で消さず、Step 5 の `bunx agentic-skill-vendor gen` が片付けます。

## Step 1: reviewの操作記録から内容の照合を外す

基づく仕様節: `docs/spec/review.md`「走らせた操作をそのまま記録する」、`docs/spec/workflow.md`「文字列照合で行為者を縛らない」。前提: なし。この Step を最初に置くのは、review の `validation.py` が implement の `secret_detect` を読み込んでいるため、Step 2 で正本を削除する前にその読み込みを外す必要があるからです。

`review_execution` から固定の一覧との照合、絶対パスと `..` の判定、シェル記号の判定、`shlex` による解釈を削除し、`review_operation_allowed` を消します。`bounded_text` と `_safe_string` から秘密検出の呼び出しを外し、`bounded_text` に NUL 文字の拒否を加えます。implement の `secret_detect` を読み込むための `sys.path` 操作も不要になるので消します。

先に書く失敗テストは次の反例を検出します。

- `python3 tools/quality/quality_gate.py`、`make test && rg foo`、`python3 /abs/test.py`、`python3 ../tools/check.py`、閉じていない引用符を含む操作が、閉じた結果（`close_finding`）としても失敗した結果（`record_targeted_result`）としても、そのまま記録される
- `API_TOKEN=...` の形の文字列を含む要約、指摘の観察、2 人目のレビュアーの要約、人の判断理由が、そのまま保存される
- 空の操作、NUL 文字を含む操作、長さの上限を超える操作は `bounded_text_invalid` で拒否される

既存の「拒否する」テスト（`test_targeted_result_rejects_destructive_git_shell_and_interpreter_operations`、`test_review_operations_reject_side_effect_options_and_keep_read_only_checks`、`test_review_operations_exclude_sed_and_retain_read_only_alternatives`、`test_targeted_review_execution_rejects_a_destructive_command`）は、仕様と逆の振る舞いを求めるので削除します。

次の 4 件は削除せず、拒否に依存する assertion だけを外します。残りの判定（記録された操作の形、指摘に書かれた確かめ方の提案が書き換わらないこと、actual model の記録、`finding_binding_invalid` の拒否、拒否時にファイルを増やさないこと）は仕様の要求なので維持します。

- `test_targeted_result_records_reviewer_operation_and_rejects_unsafe_proposals`（`review_operation_unsafe` の assertion だけ外す。操作の形と oracle が不変であることの assertion は残す）
- `test_bounded_review_text_rejects_secrets_and_stage_records_actual_model`
- `test_finding_text_and_binding_fields_are_validated_before_any_write`
- `test_second_review_and_human_decision_do_not_persist_secret_shaped_text`

Stop condition: `review_execution` の記録の形（`operation`、`working_directory`、`exit_code`、`summary`）を変えないと削除できない場合は、形を変えずに停止します。

## Step 2: implementのコミット前検査と再開表示から秘密検出を外す

基づく仕様節: `docs/spec/implement.md`「コミット」「何を見せるか」、`docs/spec/workflow.md`「文字列照合で行為者を縛らない」。前提: Step 1 が完了していること（review が `secret_detect` を読み込まなくなっていること）。

`secret_detect.py` を削除し、`safety.py` の `content_safety` と、`evidence.py`（ステージの記録とコミットの記録）、`completion.py`（予定範囲の外の未コミット変更）でそれを呼ぶ箇所を削除します。失敗コード `secret_content` は無くなります。`resume.py` は件名をそのまま返し、伏せ字の分岐を消します。`vendor-manifest.yaml` から `secret_detect.py` の 2 行を外します。

先に書く失敗テストは次の反例を検出します。

- `password = "example-password-123"` のような文字列を含む変更が、ステージの記録、コミットの記録、予定範囲の外の未コミット変更の検査で拒否されない
- PEM 形式の秘密鍵の先頭行（`BEGIN` と `PRIVATE KEY` を含むヘッダ）を含む変更も同様に
  拒否されない
- 再開時に見せる説明できないコミットの件名が、`token=...` の形でもそのまま返る

既存の秘密検出テスト（`implement_evidence_test.py` の `test_secret_shaped_content_is_rejected_without_exposing_its_value`、`test_secret_detector_covers_credentials_and_private_key_headers`、`test_secret_content_in_commit_object_is_rejected_without_value_exposure`、`implement_runtime_test.py` の `test_content_safety_scans_new_diff_content_not_unchanged_fixture_values`）は削除し、`implement_evidence_test.py` 冒頭の `secret_detect` の import も外します。再開表示の伏せ字は現在テストされていないので、上の「件名がそのまま返る」テストが resume の最初の検証になります。パス名の検査（`.env.production` などの拒否、`test_safety_checks_apply_inside_and_outside_expected_paths`）を確かめるテストは残します。

Stop condition: `content_safety` を消すと Git から変更内容を読む処理が他の用途で必要になる場合は、その用途を明示して停止します。

## Step 3: brainstormの途中経過の保存から秘密検出を外す

基づく仕様節: `docs/spec/brainstorm.md`「どこに保存するか」、`docs/spec/workflow.md`「文字列照合で行為者を縛らない」。前提: なし（Step 1、2 と独立ですが、順序は plan のとおりにします）。

`brainstorm/state.py` の `SECRET` と、`save_progress` でそれを使う分岐を削除します。

先に書く失敗テストは次の反例を検出します。

- `password: example-value` や `sk-` で始まる文字列を含む項目を持つ状態が、保存され、そのまま読み戻せる
- 保存先がリポジトリの外を指す状態は、引き続き `UnsafeProgress` で拒否される

既存の CLI テスト `test_cli_preserves_secret_and_revision_conflict_rejections` は、revision conflict の拒否だけを確かめる形に直します。

Stop condition: 秘密検出の削除で `UnsafeProgress` の他の用途が失われる場合は停止します。

## Step 4: skill本文と補助文書を仕様へ追従させる

基づく仕様節: `docs/spec/review.md`「走らせた操作をそのまま記録する」、`docs/spec/workflow.md`「文字列照合で行為者を縛らない」。前提: Step 1〜3 が完了していること（文書は実装された振る舞いに合わせます）。

runtime の振る舞いを説明する次の文書を、仕様と Step 1〜3 の実装に合わせて直します。skill の本文と `references/`、eval の期待文は英語または既存の言語のまま書きます。鉤括弧の中は該当箇所を探すための英語の原文断片です。

- `skills/ba0918-review/references/review.md`: 操作を記録する段落（"Do not accept absolute paths, outside writes, irreversible commands, external publication, or credential-dependent operations."）を、レビュアーの規範として残しつつ、runtime がその文字列を照合して拒否すると読める表現を外す。2 人目のレビュアーへ渡す前に skill が secret scan を行う記述（"after a secret scan"）は仕様どおりなので残す
- `skills/ba0918-review/references/evidence.md`: "scan every nested string without returning matched values" を、形式検査（空、NUL 文字、長さ上限）だけを表す記述に直す
- `skills/ba0918-implement/SKILL.md`（"Scan the corresponding staged/commit content for credential assignments and private-key headers"）と `references/evidence.md`（"Safety reads both path names and file content from Git itself"）: 変更内容の秘密検出と伏せ字の記述を外し、パス名の検査だけを runtime の検査として残す。秘密を混入させない責任が実装者にあることを書く
- `skills/ba0918-brainstorm/references/state.md`: "Reject traversal, symlinks, malformed state, and sensitive content." から "sensitive content" を外す
- `evals/cases/ba0918-implement/protect-commit-boundary.yaml`: runtime が staged diff と commit の内容を読んで秘密らしい値を拒否する、という期待（`expected_output` と `expectations` の該当項目）を、パス名の検査と正当な Git 証拠の記録だけを期待する形に直す
- `evals/cases/ba0918-review/bind-input-and-follow-spec.yaml`: "finding全nested文字列をsecret scanし" の期待から secret scan を外す。2 人目のレビュアーへ渡す前の skill による secret scan の期待は仕様どおりなので変えない

独立レビューは、各文書が runtime に無い検査を約束していないこと、仕様の「文字列照合で行為者を縛らない」「走らせた操作をそのまま記録する」と矛盾しないこと、eval の期待が実装と一致することを判断します。

Stop condition: 文書の修正に、仕様に無い新しい規範（例: レビュアーに新しい義務を課す文）が必要になった場合は停止します。

## Step 5: 配布同期と全体検査を行う

基づく仕様節: `docs/spec/quality-tooling.md`「Pythonの検査対象」（`skills/*/scripts` は正本から生成した複製であり、一致検査で乖離を拒否する）。前提: Step 1〜4 が完了していること。

正本から配布用の複製を生成し、削除した正本の複製を `gen` が片付けたことを含めて、削除した複製が残っていないこと、runtime のテスト、品質ツールのテスト、全体の品質ゲートが通ることを確かめます。生成物を手編集しません。

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `bunx agentic-skill-vendor lint-selfcontain`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`
- `python3 -m unittest discover -s tools/quality/tests -p '*_test.py'`
- `python3 tools/quality/quality_gate.py --scope all`

Stop condition: 配布用の複製に、正本から生成できない手編集の差分が見つかった場合は停止します。
