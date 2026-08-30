# dedupe のコア実装

Goal: `python3 -m dedupe [FILE]` が、行の重複を取り除いて標準出力に書く。
Specification: docs/spec/dedupe.md
Test command: `python3 -m unittest discover -s tests`

## Step 1 — 重複を取り除く純粋関数

Purpose: 行の並びから重複を取り除いた並びを返す。Specification: docs/spec/dedupe.md#重複の定義と残し方
Done when: `dedupe_lines(["a", "b", "a"])` が `["a", "b"]` を返す。
Shown by: test — tests/test_core.py

## Step 2 — CLI

Purpose: ファイル引数か標準入力から読み、重複を除いて標準出力へ書く。Specification: docs/spec/dedupe.md#入力, docs/spec/dedupe.md#出力
Done when: `printf 'a\nb\na\n' | python3 -m dedupe` が `a\nb\n` を出す。
Shown by: test — tests/test_cli.py
