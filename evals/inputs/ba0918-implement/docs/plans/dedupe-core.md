# dedupe のコア実装

Goal: `python3 -m dedupe [FILE]` が、行の重複を取り除いて標準出力に書く。
Specification: docs/spec/dedupe.md
Approach and why: 純粋関数 `dedupe_lines` を先に作り、CLI はそれを呼ぶだけにする。ロジックを単体で検証できるようにするため。
Scope of change: dedepe/ 配下と tests/ 配下だけ。
Step order and prerequisites: Step 1 の関数が Step 2 の CLI の前提。
Verification map: Step 1 が「重複の定義と残し方」、Step 2 が「入力」「出力」「終了コード」を確かめる。
Left to the implementer: 関数の内部構造と名前。テストの分け方。
Stop conditions: 仕様に無い振る舞いを決める必要が出たら止めて brainstorm へ返す。
Test command: `python3 -m unittest discover -s tests`
Out of scope: in-place 編集、複数ファイル、正規化。

## Step 1 — 重複を取り除く純粋関数

Purpose: 行の並びから重複を取り除いた並びを返す関数を作る。Specification: docs/spec/dedupe.md#重複の定義と残し方, docs/spec/dedupe.md#用語
Prerequisites: 無し。
May change: dedupe/core.py, tests/test_core.py
Done when: `dedupe_lines(["a", "b", "a"])` が `["a", "b"]` を返し、順序が保たれ、`"a"` と `"A"` が別の行として扱われる。
Shown by: test — tests/test_core.py に振る舞いごとのテスト。
Left to the implementer: 内部で使うデータ構造。
Stop and hand back if: 仕様に無い入力の種類（バイト列か文字列か以外）を決める必要が出たとき。

## Step 2 — CLI

Purpose: ファイル引数か標準入力から読み、重複を除いて標準出力へ書く。Specification: docs/spec/dedupe.md#入力, docs/spec/dedupe.md#出力, docs/spec/dedupe.md#終了コード
Prerequisites: Step 1。
May change: dedupe/__main__.py, dedupe/cli.py, tests/test_cli.py
Done when: `printf 'a\nb\na\n' | python3 -m dedupe` が `a\nb\n` を出して 0 で終わり、存在しないファイルを渡すと標準エラーに理由が出て 1 で終わる。
Shown by: test — tests/test_cli.py で subprocess を使って確かめる。
Left to the implementer: エラーメッセージの文言（仕様の委任のとおり）。
Stop and hand back if: 仕様の「入力」節に無い振る舞いを決める必要が出たとき。
