# plan_artifact の縮小 — 索引を捨て、機械が読む 2 箇所だけを残す

**Plan ID:** `20260826170000`
**Plan revision:** `4`

**Target specifications:**

- `docs/spec/plan.md`
  - content identity: `sha256:f40b949396541eeabcae226abd6898405cbddb20f0012a9f30c754113857f014`
  - sections: `何をするステップか`, `機械が決まった書き方で読む箇所は 2 つだけ`, `草稿と承認`, `手順書の改訂`, `未完了の手順書をどう知るか`, `複数の手順書があるとき`, `skill の構成`
- `docs/spec/implement.md`
  - content identity: `sha256:cb39f6f05a2296528d7491454833deb6b17a00f5f8643425a862b31eda17b916`
  - sections: `どの手順書を実行するか`, `手順書の読み方`

`plan.md` は、補助スクリプトが持つ仕事を 3 つに限っています。草稿の保存、正本への反映、
そして機械が決まった書き方で読む 2 箇所（参照する仕様書と変更してよい範囲）の読み取り。
未完了の手順書の索引は作らないこと、「いま対象」の印を持たないことも決めています。

いまの `plan_artifact.py` は 728 行あり、この 3 つの他に、手順の構文解析、完了の示し方の
検査、検査コマンドの抽出、人が判断する場面の JSON 検証、そして `open-plans.json` という
索引の読み書きを持っています。この手順書は、そこに書かれた振る舞いをコードに移すだけで、
新しい意味を決めません。

## 版 4 で直したこと

手順 6 の検査コマンドが `tools/workflow-runtime/implement/` を走査対象に含んでいて、
絶対に通らない状態でした。消したい名前のうち 2 つが、implement 側で別の役目のまま
生きているためです。

- `COMPLETION_KINDS` は `repository.py` にあり、AI が宣言した完了の示し方が、この
  runtime が扱える 4 種類のどれかであることを見ています。手順書の本文を読む処理では
  ありません
- `HUMAN_GATE_TIMINGS` は `gates.py` にあり、人が判断する場面をどの境界で見るかの
  順序を持っています。こちらも宣言を扱う側です

検査対象を `tools/workflow-runtime/plan/` と、この計画が触る試験 2 本に絞りました。
これは手順書 A の版 2 で直したのと同じ種類の書き損じです。

**作る物、禁止、人が判断する場面は版 1 のままです。**

## 版 3 で直したこと

手順 8 の変更してよいファイルに `skills/ba0918-implement/scripts/` がありませんでした。
`bunx agentic-skill-vendor gen` は登録された全 skill の複製を作り直します。この計画は
手順 1〜3 で implement の正本を変えているので、その複製もこの手順で書き換わります。

**作る物、禁止、人が判断する場面は版 1 のままです。**

## 版 2 で直したこと

版 1 は、手順 2 を読み込んで初めて分かる欠陥を持っていました。**作る物、禁止、人が判断
する場面は版 1 のままです。**直したのは、変更してよいファイルの取りこぼしだけです。

- 手順 2 の変更してよいファイルに `repository.py` がありませんでした。束ねの記録
  （`binding.json`）を組み立てているのはこのモジュールで、起点のコミットとの照合結果を
  事実として書く場所もここです。「Scope」には最初から挙がっていました
- 手順 2 の変更してよいファイルに `cli.py` がありませんでした。束ね直しの相手を索引では
  なくパスで探すと、その手順書の版を AI が宣言して渡す必要があります。`resolve` と
  `bootstrap` は手順 1 で `--plan-revision` を得ましたが、`rebind` は同じ引数を
  持っていません
- 索引を読んでいる呼び出し元を数え直しました。`resume.py` に 4 箇所、`context.py` に
  1 箇所あります。この 2 つは手順 3 以降のどの手順にも挙がっていないので、索引を消す
  手順 4 までにそれらを外せるのは手順 2 だけです

## この計画で採る方針

**足してから消します。**索引を使わずに手順書を特定できることをテストで示してから、索引を
消します。逆順にすると、消している途中で手順書を特定できない状態が生まれます。

**索引の代わりは git です。**手順書がコミットされているかどうかを、承認の記録として使います。
承認とコミットは同じ操作なので（`plan.md` の「未完了の手順書をどう知るか」）、git は書く手順を
飛ばせません。索引は、公開の操作で書かれて完了の操作では触られない、ずれる余地そのものです。

**ただし、それを束ねる条件にはしません。**手順書は実行中に直ります。漏れや書き損じが
見つかったらその場で直して続ける、と決めたので（壁打ちの記録の A45・A47）、「承認したときと
1 バイトも違わないこと」を前提にすると、直した瞬間に前提が壊れます。束ねるときは手元の
ファイルの指紋で束ね、起点のコミットと一致したかどうかは事実として記録に書きます。
実行中に手順書が変わったときの扱い（設計判断の変更なら人に返し、それ以外は記録して続ける）は
仕様書の改訂を待つので、この手順書では触りません。

**手順書の ID と版は AI が宣言します。**`plan.md` は「手順書の ID と版は、本文を読んで
理解します」と決めています。手順・完了の示し方・人が判断する場面が実行の束ねで宣言される
のと同じ形で受け取ります。

**版が 1 つずつ増えることは、機械では確かめません。**索引が消えると前の版の番号を持つ物が
無くなります。番号の連続は文書が自分の中で辻褄を合わせているだけで、外の世界について
何も言っていません（`workflow.md` の「機械の検査は、外の世界を見るものに限る」）。人が
草稿を読むときに見ます。

**草稿の仕組みは残します。**一時の置き場、指紋の照合、指紋を明示しないと古い草稿を
置き換えない保護は、`plan.md` の「草稿と承認」が生きています。縮めるのは、正本にするときに
何を検査するかだけです。

## Scope

```text
tools/workflow-runtime/
  plan/
    plan_artifact.py
  implement/
    runtime/
      cli.py
      context.py
      planning.py
      repository.py
      resume.py
  tests/
    plan_artifact_test.py
    implement_runtime_test.py
skills/ba0918-plan/
  SKILL.md
  references/
    creation.md
    lifecycle.md
    readability.md
  scripts
vendor-lock.json
```

`plan_artifact.py` の縮小は implement 側に届きます。手順書を特定する経路を持つのは
`planning.py`、`context.py`、`resume.py`、`cli.py` で、束ねの記録を書くのは
`repository.py` です。plan だけを触って終わる作業ではありません。

## Steps

### 1. 手順書の ID と版を、AI の宣言として受け取る

**目的:** `plan.md` の「機械が決まった書き方で読む箇所は 2 つだけ」に合わせる。手順書の ID と
版は本文を読んで理解するものなので、機械が索引や見出しから取らない。

**前提:** なし。

**変更してよいファイル:** `tools/workflow-runtime/implement/runtime/planning.py`、
`tools/workflow-runtime/implement/runtime/cli.py`、
`tools/workflow-runtime/implement/runtime/repository.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** test

確かめること:

- 手順書のパスと、AI が宣言した ID・版で実行を束ねられる
- 束ねの記録に入る ID・版・指紋が、宣言と手元のファイルから決まる
- 索引に無い手順書でも束ねられる
- 参照する仕様書の指紋の照合と、変更してよい範囲の読み取りは、これまでどおり働く

**実装側に任せてよい選択:** 宣言の渡し方（手順の宣言と同じ引数にまとめるか、別に取るか）。

**止まる条件:** 手順書の本文から ID や版を機械が取り出したくなったら止まる。それは
`plan.md` が本文読みと決めた箇所。

### 2. 承認の記録を、索引から git へ移す

**目的:** `plan.md` の「未完了の手順書をどう知るか」に合わせる。承認とコミットが同じ操作
なので、コミットされていることがそのまま承認の記録になる。

索引は「この指紋の物が正本」と書いた別のファイルで、書いた時点の話しか持たない。git は
その手順書がいつ承認され、その後どう直ったかを両方持つ。

**前提:** 手順 1。

**変更してよいファイル:** `tools/workflow-runtime/implement/runtime/planning.py`、
`tools/workflow-runtime/implement/runtime/context.py`、
`tools/workflow-runtime/implement/runtime/resume.py`、
`tools/workflow-runtime/implement/runtime/repository.py`、
`tools/workflow-runtime/implement/runtime/cli.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** test

確かめること:

- 束ねの記録に入る指紋は、束ねた時点の手元のファイルのもの
- 束ねの記録に、その手順書が起点のコミットに存在したか、存在したなら同じ中身だったかが
  事実として入る
- 起点のコミットと違っていても、束ねること自体は止まらない
- 束ね直しの相手を探すときも、索引ではなくパスと git を見る

**実装側に任せてよい選択:** git に問う方法。記録に書く形。

**止まる条件:** この事実を止まる条件にしたくなったら止まる。手順書は実行中に直るので、
一致を前提にすると直した瞬間に破綻する。実行中の不一致をどう扱うかは、仕様書の改訂待ち
（壁打ちの記録の A47）で、この手順書の範囲ではない。

### 3. 実行する手順書の候補を、作業ツリーから導く

**目的:** `plan.md` の「未完了の手順書をどう知るか」「複数の手順書があるとき」と、
`implement.md` の「どの手順書を実行するか」に合わせる。作業ツリーにある手順書が、そのまま
未完了の一覧。

**前提:** 手順 2。

**変更してよいファイル:** `tools/workflow-runtime/implement/runtime/planning.py`、
`tools/workflow-runtime/implement/runtime/cli.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** test

確かめること:

- パスを指定しないとき、作業ツリーの手順書の置き場に 1 つだけあればそれを選ぶ
- 複数あるときは選ばずに、候補を挙げて人に聞く形で返る
- 1 つも無いときは、候補が無いこととして返る
- 「いま対象」の印を読まない

**実装側に任せてよい選択:** 候補を返す形。

**止まる条件:** 更新日時や名前の順で 1 つに絞りたくなったら止まる。`implement.md` が
禁じている。

### 4. 索引を消す

**目的:** `plan.md` の「索引は作りません」に合わせる。索引は、手順書を公開する操作で書かれ、
実行が完了する操作では触られない。書く手順を飛ばしても作業は進むので、飛ばされる。

「いま対象」と「保留」の印、版が 1 つずつ増えることの検査も、索引と一緒に無くなる。前者は
`plan.md` が持たないと決めている。後者は文書が自分の中で辻褄を合わせる検査で、外の世界に
ついて何も言っていない。

**前提:** 手順 3。

**変更してよいファイル:** `tools/workflow-runtime/plan/plan_artifact.py`、
`tools/workflow-runtime/tests/plan_artifact_test.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** check

**Checks:**

- `test -z "$(rg -l 'open-plans|INDEX_NAME|_empty_index|_validate_index|_load_index|_encode_index|InvalidOpenPlanIndex|CurrentPlanConflict' tools/workflow-runtime/plan/ tools/workflow-runtime/implement/ tools/workflow-runtime/tests/plan_artifact_test.py tools/workflow-runtime/tests/implement_runtime_test.py)"`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 正本の一覧をどこかに書き出したくなったら止まる。それは名前を変えた索引。

### 5. 正本にするときの検査を、2 箇所に絞る

**目的:** `plan.md` の「機械が決まった書き方で読む箇所は 2 つだけ」と「草稿と承認」に
合わせる。草稿の保存と正本への反映で確かめるのは、参照する仕様書と変更してよい範囲、
そして挙げられた仕様書が実在してその指紋であることだけにする。

**前提:** 手順 4。

**変更してよいファイル:** `tools/workflow-runtime/plan/plan_artifact.py`、
`tools/workflow-runtime/tests/plan_artifact_test.py`。

**Completion:** check

**Checks:**

- `rg -q 'read_plan_scope' tools/workflow-runtime/plan/plan_artifact.py`
- `rg -q 'verify_target_specifications' tools/workflow-runtime/plan/plan_artifact.py`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 草稿の指紋の照合や、指紋を明示しない置き換えの拒否を消したくなったら止まる。
それは「草稿と承認」が求めている。

### 6. 手順の構文解析を消す

**目的:** 手順 5 と同じ。手順の見出し、完了の示し方、検査コマンド、人が判断する場面を
構文として読む処理は、もう誰も呼んでいない。

**前提:** 手順 5。

**変更してよいファイル:** `tools/workflow-runtime/plan/plan_artifact.py`、
`tools/workflow-runtime/tests/plan_artifact_test.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** check

**Checks:**

- `test -z "$(rg -l 'read_plan_steps|read_plan_human_gates|_step_check_commands|InvalidHumanGateDeclaration|COMPLETION_KINDS|CHECK_COMMAND|HUMAN_GATE_TIMINGS|HUMAN_GATE_RESULTS' tools/workflow-runtime/plan/ tools/workflow-runtime/tests/plan_artifact_test.py tools/workflow-runtime/tests/implement_runtime_test.py)"`
- `rg -q 'read_plan_header' tools/workflow-runtime/plan/plan_artifact.py`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 消そうとした処理を、まだ誰かが呼んでいると分かったら止まる。呼び出し元を
先に手順 1〜3 で外しているはずなので、残っていれば取りこぼしがある。

### 7. plan skill の文書を新しい形に合わせる

**目的:** `plan.md` の全体に合わせる。SKILL.md と補足 3 本を、索引の無い形と、機械が読む
2 箇所だけの形に書き直す。

**前提:** 手順 6。

**変更してよいファイル:** `skills/ba0918-plan/SKILL.md`、
`skills/ba0918-plan/references/` の 3 本。

**Completion:** artifact

確かめること:

- 索引、「いま対象」、「保留」に触れた記述が残っていない
- 手順書の ID と版を AI が宣言することが書かれている
- 承認の記録がコミットであることが書かれている
- 機械が読む 2 箇所と、本文として読む物の線が、仕様書と同じ
- `bunx skills-ref validate skills/ba0918-plan` が通る

**止まる条件:** 仕様書に書いていない振る舞いを文書に書きたくなったら止まる。

### 8. 配布の複製を作り直す

**目的:** 正本を直したあと、配布される skill の複製を同期する。

**前提:** 手順 7。

**変更してよいファイル:** `skills/ba0918-plan/scripts/`、
`skills/ba0918-implement/scripts/`、`vendor-lock.json`。

**Completion:** check

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 複製を手で直したくなったら止まる。複製は `gen` が作る物。

## 進め方の前提

このプロダクトのワークフロー（`ba0918-brainstorm` / `plan` / `implement` / `review` /
`cycle`）は、Phase 14 が終わるまで使えません。作り替えている対象そのものだからです。
**この手順書の実行では、それらの skill を起動しません。**

代わりに使うのは規則の skill です。`ba0918-tdd`、`ba0918-commit`、`ba0918-design`、
`ba0918-placement`、`ba0918-secrets`、`ba0918-readability`。

証拠は残しません。git のコミットが記録です。手順ごとに 1 コミット以上を作り、
コミットメッセージに理由を書きます。

検査コマンドの対象は、この手順書が触る範囲に絞ってあります。`tools/workflow-runtime/`
全体を見ると、review が同じ名前を持つ別の機構を抱えているせいで通りません。
