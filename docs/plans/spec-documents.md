# spec-documents 実装の手順書

## Goal

仕様書を責務ごとに分けて事実を 1 か所に置く約束と、仕様書のパスを複数受け渡す形を、brainstorm、plan、cycle、iterate の skill 本文に写す。
あわせて `PROJECT.md`、`CHANGELOG.md`、`regression-lock.json` を揃える。

## Specification

コミット済みの次の仕様書（`992fdac` 以降）。
この手順書は仕様書の見出しをリンクで参照し、本文を写さない。
実装者は各 step の前に、参照された見出しを必ず読む。

- [仕様書の分け方 仕様](../spec/spec-documents.md)（新設。約束の本体）
- [開発ワークフロー仕様](../spec/workflow.md)（brainstorm、plan、cycle の節の受け渡しを直した）
- [小さいタスク skill 仕様](../spec/iterate.md)（仕様書のパスを複数にした）
- [入口 skill 仕様](../spec/using-workflow.md)、[調査 skill 仕様](../spec/investigate.md)（冒頭のリンクと行数の呼び名だけを直した）

行数の目安の扱いは、[開発ワークフロー仕様](../spec/workflow.md)の冒頭（「行数の目安は」の段落）に従う。

## Approach and why

brainstorm → plan → cycle → iterate の順に本文を直し、最後に `PROJECT.md` と回帰の lock を揃える。
brainstorm を先にするのは、変更の中心で行数が最も増え、目安の判断が要るからである。
plan と cycle は、brainstorm が返す「変えた仕様書のパスの一覧」を受け取る側なので、その後に直す。
iterate は cycle の本文を名前で読み、表で読み替える。
cycle の言い回しが決まってから、読み替えの表を合わせる。

brainstorm の本文は、今の時点で SKILL.md と参照資料の合計が 158 行あり、目安の 135 を既に超えている。
今回の約束を足すとさらに増える。
分け方の約束は、仕様書を書く時点で読めば足りる。
なので本文には読む時点と要点だけを置き、細部は新しい参照資料 `skills/ba0918-brainstorm/references/spec-documents.md` に置く。
これは「本文は実行者がその場で要る指示だけ」という縛りに沿う。
それでも目安を超えるのは、責務（仕様書を書くこと）が変わらず、足した行が書く時点で要るからである。
その必要性は cycle の review が判定する。

skill 本文から仕様書のパスを参照しない（`PROJECT.md`「縛り」）。
約束は skill の中に英語で写す。
出力先の `docs/spec/` のように、出力先と実行時の入力を示すパスは例外である。

`using-workflow` と `investigate` の skill 本文には、仕様書のパスを 1 本と決めている箇所が見つかっていない。
using-workflow は「with its path」、investigate は `/ba0918-plan <specification path>` と書いている。
仕様書の側でも、これらの行は今回変えていない。
なので本文は直さず、Step 4 で直さなくてよいことを確かめるだけにする。

CHANGELOG は、skill を変える commit と同じ commit に書く（`PROJECT.md`「配布と版」）。
skill の指示の意味が変わるので、brainstorm、plan、cycle、iterate の項目には **BREAKING** を付ける。
回帰の scenario は実走しない（人が明示していない）。
lock は本文を変えた skill ごとに、実走せずに取り直す。
既存の scenario（bs-001、bs-002、cy-001 など）は、途中経過のファイル名と `docs/spec/` の下の 1 本の仕様書で書かれている。
今回の変更はどちらも壊さない（1 本だけの仕様書も、題材の名前が仕様書の名前と同じ場合も、変わらず許される）。

ブランチと worktree は、cycle を起動する前にメインセッションが作る。
この手順書の step には含めない。

## Scope of change

- `skills/ba0918-brainstorm/SKILL.md`、`skills/ba0918-brainstorm/references/records.md`
- `skills/ba0918-brainstorm/references/spec-documents.md`（新設）
- `skills/ba0918-plan/SKILL.md`、`skills/ba0918-plan/references/step-template.md`
- `skills/ba0918-cycle/SKILL.md`
- `skills/ba0918-iterate/SKILL.md`
- `PROJECT.md`、`CHANGELOG.md`、`regression-lock.json`

この外は変えない。
とくに `docs/spec/*.md` と `CONTEXT.md` は触らない。
次も触らない。

- `skills/ba0918-review/`、`skills/ba0918-implement/`
- `skills/ba0918-using-workflow/`、`skills/ba0918-investigate/`
- `evals/`

## Step order and prerequisites

Step 1 → Step 2 → Step 3 → Step 4 の順は固定。
Step 2 と Step 3 は、Step 1 が決めた「変えた仕様書のパスの一覧」の英語の言い回しを使う。
Step 4 は、Step 3 の cycle の言い回しに読み替えの表を合わせる。
Step 5 は Step 1〜4 の後。
lock の hash は本文の最終形から取るからである。

## Verification map

- [責務ごとに 1 本](../spec/spec-documents.md#責務ごとに-1-本)、[1 つの事実は 1 か所](../spec/spec-documents.md#1-つの事実は-1-か所)、[参照はリンクで書く](../spec/spec-documents.md#参照はリンクで書く)、[分ける目安](../spec/spec-documents.md#分ける目安)、[分けたときの形](../spec/spec-documents.md#分けたときの形) → Step 1
- 開発ワークフロー仕様の brainstorm の節（受け取る物と返す物、[記録](../spec/workflow.md#記録)、[仕様書に書く前の見直し](../spec/workflow.md#仕様書に書く前の見直し)、[仕上げ](../spec/workflow.md#仕上げ)） → Step 1
- 開発ワークフロー仕様の [plan](../spec/workflow.md#plan) の節（受け取る物、[手順書の形](../spec/workflow.md#手順書の形)） → Step 2
- 開発ワークフロー仕様の [cycle](../spec/workflow.md#cycle) の節（手順書から読む仕様書と、review に渡す突き合わせ相手） → Step 3
- [小さいタスク skill 仕様](../spec/iterate.md)の [受け取る物と返す物](../spec/iterate.md#受け取る物と返す物) → Step 4
- [仕様書の分け方 仕様](../spec/spec-documents.md#作る物)の「作る物」 → Step 1〜3 と Step 5。using-workflow と investigate の分は Step 4 の確認
- 各仕様書の冒頭の行数の目安 → Step 1〜4 の Shown by（行数の報告）と、cycle の review の判定

## Left to the implementer（手順書全体）

- 英語の言い回しと行の詰め方。ただし「limit」「cap」「must not exceed」「at most」のように、行数を超えてはいけない数として読ませる語は使わない（[分ける目安](../spec/spec-documents.md#分ける目安)）
- 新しい参照資料の中の節の並べ方
- CHANGELOG の文面（内容は仕様書の該当節に従う）
- lock の note の文面

## Stop conditions（手順書全体）

理念の 4 条件に加えて、次のときは止めて返す。

- 仕様書に無い振る舞いを本文へ足したくなった
- 仕様書どうしが食い違っていて、どちらを写すか決められない
- 本文から仕様書のパスを参照しないと、約束を書けない

## Test command

コードを変えないので、テストは走らせない。
各 step の確かめ方は検査のコマンドである。

## Out of scope

- `docs/spec/workflow.md` 自体を責務ごとに分けること（別の作業）
- 既存の仕様書に残る、リンクでない参照を直すこと
- 回帰の scenario の実走と、scenario の追加

## Step 1 — brainstorm が仕様書を責務で分け、リンクで参照する

Purpose: brainstorm の本文に、分け方の約束と、書く前の見直しと、仕上げのレビューに渡す範囲を写す。
Specification: [責務ごとに 1 本](../spec/spec-documents.md#責務ごとに-1-本)、[1 つの事実は 1 か所](../spec/spec-documents.md#1-つの事実は-1-か所)、[参照はリンクで書く](../spec/spec-documents.md#参照はリンクで書く)、[分ける目安](../spec/spec-documents.md#分ける目安)、[分けたときの形](../spec/spec-documents.md#分けたときの形)、[brainstorm](../spec/workflow.md#brainstorm)、[記録](../spec/workflow.md#記録)、[仕様書に書く前の見直し](../spec/workflow.md#仕様書に書く前の見直し)、[仕上げ](../spec/workflow.md#仕上げ)。
Prerequisites: なし。
May change: 次のファイル。

- `skills/ba0918-brainstorm/SKILL.md`
- `skills/ba0918-brainstorm/references/records.md`
- `skills/ba0918-brainstorm/references/spec-documents.md`（新設）
- `CHANGELOG.md`

Done when:

- 本文の Inputs and outputs が、改訂の入力は既存の仕様書のパス（分けてあれば索引のパス）で、出力は承認されてコミットされた仕様書と、変えた仕様書のパスの一覧だと述べている。1 回で複数の仕様書を変えてよいことも述べている
- 途中経過のファイル名が、題材の名前（分けた範囲の改訂なら索引の名前）になっている。本文と `records.md` の両方で
- Writing the specification が、書く前に新しい参照資料を読むことと、変えた見出しへリンクしている仕様書をテキスト検索で拾って読み直すことを述べている。読み直しは仕上げのレビューの有無に関係なく毎回行う
- 新しい参照資料に、次の各項目に対応する文がある（[仕様書の分け方 仕様](../spec/spec-documents.md)のうち brainstorm が実行する物）。
  1. 責務で足すか新しく作るかを決める。ディレクトリの形とファイル名はプロジェクトに合わせる
  2. 書く前に同じ事実を検索し、あればリンクする
  3. 参照はリンクで書く。分けたときは古い参照を張り直す。既存の文書のリンクでない参照はまとめて直さない
  4. 見出しの改名や文書の移動をしたら、古いリンクを検索して直す
  5. 目安 300 行（根拠の無い仮置き）と、超えたときの確かめ方、切り出す範囲、人に見せる判断点。既に大きい仕様書をまとめて整理し直さない
  6. 分けたら索引を置き、索引は本文を持たない
  7. 却下・未決定・委任は関わる責務の仕様書に置く
  8. 用語集は既定では 1 本にし、意味が割れたときだけ分ける
- Finishing の敵対的レビューが、reviewer に渡す仕様書を、変えた仕様書と、それとリンクで直接つながる仕様書（1 段、リンクする側とされる側の両方）に限っている
- 本文と参照資料に `docs/spec/` の下の仕様書へのパスが無い（出力先を示す物は除く）
- 同じ事実を探す先を、iterate の本文と同じく「プロジェクトの指示が示す仕様書の置き場」と書いている
- `CHANGELOG.md` の `## [Unreleased]` の下に `### Changed` があり、`ba0918-brainstorm` の **BREAKING** の項目がある。以後の step の項目も同じ `### Changed` に足す

Shown by: check — 次を順に走らせる。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-brainstorm` が成功する
2. `cat skills/ba0918-brainstorm/SKILL.md skills/ba0918-brainstorm/references/*.md | wc -l` の値を報告する。目安 135 を超えたら、足した行が仕様書を書く時点で要ることを報告に書く
3. `rg -n "docs/spec/" skills/ba0918-brainstorm` の一致が、出力先を示す Out の行だけである
4. `rg -n -i "limit|cap\b|must not exceed|at most" skills/ba0918-brainstorm` の一致が、行数の目安を指していない

Left to the implementer: 本文と参照資料のあいだで、どの文をどちらに置くか。ただし、書く前に参照資料を読むという指示は本文に置く。
Stop and hand back if: 目安の超過を詰めて収めるために、既存の指示の意味を削る必要が出た。

## Step 2 — plan が複数の仕様書をリンクで参照する

Purpose: plan が変えた仕様書のパスを複数受け取り、リンク先を 1 段まで読み、手順書でリンクと見出しで参照するようにする。
Specification: [plan](../spec/workflow.md#plan)、[手順書の形](../spec/workflow.md#手順書の形)。
Prerequisites: Step 1。
May change: `skills/ba0918-plan/SKILL.md`、`skills/ba0918-plan/references/step-template.md`、`CHANGELOG.md`。

Done when:

- 本文の In が、コミット済みの仕様書のパスを複数受け取れることと、索引からは辿らないことを述べている。
  受け取った仕様書のリンク先を 1 段まで読んでよく、手順が基づく物はリンク先も含めて手順書に挙げることも述べている
- 本文の What a plan is が、仕様書をリンクと見出しで参照すると述べている
- `step-template.md` の Specification の欄と、手順書全体の Specification の節が、1 本の仕様書を前提にしていない。
  「the one governing path」を持たない
- `step-template.md` の Specification の欄の書式が、仕様書の見出しへの Markdown のリンクになっている
- frontmatter の description が、承認された仕様書（複数でよい）から手順書を作ると読める
- `CHANGELOG.md` の `Unreleased` に、`ba0918-plan` の **BREAKING** の項目がある

Shown by: check — 次を順に走らせる。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-plan` が成功する
2. `cat skills/ba0918-plan/SKILL.md skills/ba0918-plan/references/*.md | wc -l` の値を報告する（目安 156）。目安を超えたら、足した行がその場で要ることを報告に書く

Left to the implementer: なし。
Stop and hand back if: なし。

## Step 3 — cycle が手順書の挙げた仕様書だけを突き合わせ相手に渡す

Purpose: cycle が手順書から仕様書のパスを複数読み、review の突き合わせ相手にそれだけを渡すようにする。
Specification: [cycle](../spec/workflow.md#cycle)。
Prerequisites: Step 2。
May change: `skills/ba0918-cycle/SKILL.md`、`CHANGELOG.md`。

Done when:

- 本文が、手順書が挙げた仕様書のパス（複数でよい）だけを読み、review の突き合わせ相手としてもそれだけを渡し、索引や関係ない仕様書は渡さないと述べている。今の 31 行目、51 行目、54 行目の「specification path」が対象である
- `CHANGELOG.md` の `Unreleased` に、`ba0918-cycle` の **BREAKING** の項目がある

Shown by: check — 次を順に走らせる。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-cycle` が成功する
2. `wc -l skills/ba0918-cycle/SKILL.md` の値を報告する（目安 110。今は既に 142 行）。目安を超えたら、足した行がその場で要ることを報告に書く

Left to the implementer: なし。
Stop and hand back if: なし。

## Step 4 — iterate が複数の仕様書を扱う

Purpose: iterate の入力と判定と読み替えの表を、仕様書のパスが複数ありうる形に合わせる。
仕様書の「作る物」のうち using-workflow と investigate については、直す箇所が無いことの確認で足りると、この手順書が判断した。
Specification: [受け取る物と返す物](../spec/iterate.md#受け取る物と返す物)、[判定役](../spec/iterate.md#判定役)、[作る物](../spec/spec-documents.md#作る物)。
Prerequisites: Step 3。
May change: `skills/ba0918-iterate/SKILL.md`、`CHANGELOG.md`。

Done when:

- 本文の任意の入力が、突き合わせる仕様書のパスは複数でよく、索引は渡さないと述べている
- 判定する側が仕様書を探すとき、変更する場所を扱う物を全部見つけ、索引は数えないと述べている
- 読み替えの表の左列のうち cycle の本文を引用する行（今の 83 行目と 89 行目）が、Step 3 で書き換えた後の cycle の語と一致している
- using-workflow と investigate の本文に、受け取る入力を仕様書 1 本と宣言している文が無いことを確かめ、報告に書いている。
  案内の表や入口の表の呼び出し例のプレースホルダ（`/ba0918-plan <specification path>` など）は、これに当たらない。
  iterate の本文と仕様書も同じ書き方のまま認めているからである
- `CHANGELOG.md` の `Unreleased` に、`ba0918-iterate` の **BREAKING** の項目がある

Shown by: check — 次を順に走らせる。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-iterate` が成功する
2. `wc -l skills/ba0918-iterate/SKILL.md` の値を報告する（目安 113。今は既に 118 行）。目安を超えたら、足した行がその場で要ることを報告に書く
3. `rg -n -i "specification path" skills/ba0918-using-workflow skills/ba0918-investigate` の一致を報告に貼る

Left to the implementer: なし。
Stop and hand back if: using-workflow か investigate の本文に、受け取る入力を仕様書 1 本と宣言している文があった。直すかは仕様の判断になる。

## Step 5 — 正本の表と回帰の lock を揃える

Purpose: `PROJECT.md` の正本の表に新しい仕様書を載せ、行数の書き方を目安に揃え、本文を変えた skill の lock を取り直す。
Specification: [作る物](../spec/spec-documents.md#作る物)。
Prerequisites: Step 1〜4。
May change: `PROJECT.md`、`regression-lock.json`。

Done when:

- `PROJECT.md` の正本の表に `docs/spec/spec-documents.md` の行があり、役目を 1 文で述べている
- `PROJECT.md` の縛りの行数の段落が「目安」と呼び、「上限」「超えてはいけない」を使わない
- `regression-lock.json` で、ba0918-brainstorm、ba0918-plan、ba0918-cycle、ba0918-iterate の hash が今の本文と一致している
- Step 1〜4 のファイルを後から変えたとき（レビューの後の修正を含む）は、最後の変更の後にこの step の lock の取り直しをやり直している

Shown by: check — 次を順に走らせる。

以下の `LOCK` は `~/.claude/skills/ba0918-skill-regression/scripts/lock.py` を指す。

1. brainstorm、plan、cycle、iterate のそれぞれについて、lock を実走なしで取り直す。
   コマンドは `python3 LOCK --update <skill> --accept --note "<理由>" .` である。
   note には、実走しない理由と、既存の scenario の期待が今回の変更に触れないことを書く
2. `python3 LOCK --check . | rg -v '^\[unverified\] ba0918-using-workflow'` の出力が空である。
   `--check` 自体は、既存の ba0918-using-workflow の unverified が残るので終了コード 1 を返す。それは期待どおりである
3. `rg -n "spec-documents" PROJECT.md` が正本の表の行に一致する
4. `rg -n "上限|超えてはいけない" PROJECT.md` に、行数を指す一致が無い

Left to the implementer: なし。
Stop and hand back if: `lock.py` が見つからないか、`--accept` で取り直せない。
