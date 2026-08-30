# dedupe の空入力の扱い

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

Purpose: 行の並びから重複を取り除いた並びを返す関数を作る。Specification: docs/spec/dedupe.md#重複の定義と残し方
Prerequisites: 無し。
May change: dedupe/core.py, tests/test_core.py
Done when: `dedupe_lines(["a", "b", "a"])` が `["a", "b"]` を返す。
Shown by: test — tests/test_core.py。
Left to the implementer: 内部で使うデータ構造。
Stop and hand back if: 無し。

## Step 2 — 空の入力

Purpose: 入力が 0 バイトのときの振る舞いを、仕様の「入力」節に従って実装する。Specification: docs/spec/dedupe.md#入力
Prerequisites: Step 1。
May change: dedupe/core.py, tests/test_core.py
Done when: 仕様の「入力」節が定める空入力の結果（出力と終了コード）をテストが確かめている。
Shown by: test — tests/test_core.py。
Left to the implementer: 無し。
Stop and hand back if: 仕様の「入力」節が空入力の振る舞いを定めていないとき。
