# implement の減量 — 自己検証を落とし、状態の写しと委譲を足す

**Plan ID:** `20260826050000`
**Plan revision:** `2`

**Target specifications:**

- `docs/spec/implement.md`
  - content identity: `sha256:cb39f6f05a2296528d7491454833deb6b17a00f5f8643425a862b31eda17b916`
  - sections: `手順書の読み方`, `委譲されて動くとき`, `証拠の残し方`, `止まり方`, `会話が途切れたとき`, `skill の構成`
- `docs/spec/workflow.md`
  - content identity: `sha256:15b5c1dc8a9d595635b8e11cc926e51ec58a4a1c00edf92f361a02e03521e3ab`
  - sections: `機械の検査は、外の世界を見るものに限る`, `記録は、現実を変える操作と同じ操作の中で書く`, `状態の写し（current-status）`, `承認を儀式にしない`

`implement.md` は、機械の検査を外の世界に限ること、証拠から承認の照合に使わない指紋を
落とすこと、状態の写しを出来事の追記と同じ操作の中で書くこと、委譲されて動く形、
止まり方を 2 種類に割ることを求めています。`workflow.md` は、その検査の線引きと、状態の
写しに何を書き何を書かないかを定めています。この手順書は、そこに書かれた振る舞いを
コードに移すだけで、新しい意味を決めません。

## 版 2 で直したこと

版 1 は、実行して初めて分かる欠陥を持っていました。**作る物、禁止、人が判断する場面は
版 1 のままです。**直したのは、検査コマンドが見る範囲と、変更してよいファイルの
取りこぼしだけです。

- 手順 2・3 の検査コマンドが `tools/workflow-runtime/` 全体を見ていました。review は
  同じ名前の失敗コードを持つ別の記録機構で、この計画は review の記録機構を触りません。
  そのままでは、10 手順のどこまで進んでも検査が通りません。implement とその試験に
  絞りました
- 手順 3 が消す名前のうち `attempt_id_invalid` と `repository_identity_invalid` は、
  外の世界を見る検査の名前でもあります（実行 ID がパスとして安全か、git の共通
  ディレクトリが本当に主作業ディレクトリの `.git` か）。消すのは束ねの記録の形式検証
  だけなので、名前が消えたことを見る対象を `execution_model.py` に絞り、外の世界を
  見る 2 つが残っていることを別の行で確かめます
- 手順 1 の変更してよいファイルに `repository.py` と `deliverables.py` がありません
  でした。落とす欄を組み立てているのはこの 2 つです
- 手順 6 の変更してよいファイルに、手順の一覧を使うモジュールが 3 つ足りませんでした
- 手順 8 に、配布された複製の `execution_model.py` を消すことが入っていませんでした
- 手順 10 の変更してよいファイルに `skills/ba0918-review/scripts/` がありませんでした
- Scope に review の 2 ファイルがありませんでした。review は implement の最後の
  出来事の指紋を自分の記録に書き留めており、implement が指紋を保存しなくなると、
  そこだけが動かなくなります
- Scope の木で `scripts/` と末尾に `/` を付けて書いた行が、変更してよい範囲に
  1 つも寄与していませんでした。この木の読み方では、`/` で終わる行はその下に
  並ぶ行の親を表すだけで、それ自体は範囲になりません。子を並べない
  `skills/ba0918-implement/scripts/` は、手順 10 が書き込む場所であるのに範囲の外に
  ありました。`/` を外すと、そのパスとその下すべてが範囲になります

## この計画で採る方針

**足してから消します。**新しい形の証拠が書けることをテストで示してから、古い形式の検証を
消します。逆順にすると、消している途中で何も書けない状態が生まれ、テストが成り立ちません。

**消す手順は `check` で示します。**削除には先に書く失敗テストがありません。代わりに
「その検査を表す名前がコードから消えたこと」と「残りのテストが全部通ること」の 2 つを
検査コマンドにします。片方だけでは足りません。テストだけ消してコードを残す道と、コードを
消してテストを壊す道の両方を塞ぐためです。

**`execution_model.py` は解体します。**残る 156 行相当（外の世界を見る 6 関数）は、それを
使う側のモジュールへ移します。1 つのファイルに集める理由が、自己検証を持たなくなった時点で
無くなるためです。

## Scope

```text
tools/workflow-runtime/
  implement/
    execution_model.py
    implement_runtime.py
    runtime/
      cli.py
      context.py
      deliverables.py
      deps.py
      gates.py
      gitio.py
      planning.py
      repository.py
      resume.py
      staging.py
      storage.py
      tdd.py
      types.py
  review/
    review_runtime.py
  tests/
    implement_execution_model_test.py
    implement_runtime_test.py
    review_runtime_test.py
skills/ba0918-implement/
  SKILL.md
  references/
    artifacts.md
    evidence.md
    execution.md
    tdd.md
  scripts
skills/ba0918-review/
  scripts
vendor-lock.json
```

## Steps

### 1. 出来事から、承認の照合に使わない指紋を落とす

**目的:** 仕様書 `implement.md` の「何を書き、何を書かないか」に合わせる。指紋は承認した
内容と手元の内容を比べるためだけに持つ。

残すのは、手順書の指紋、仕様書の指紋、凍結したテストの指紋。落とすのは、出来事どうしを
つなぐ指紋、記録自身の指紋、リポジトリと作業ディレクトリの指紋。

**前提:** なし。

**変更してよいファイル:** `tools/workflow-runtime/implement/execution_model.py`、
`tools/workflow-runtime/implement/runtime/context.py`、
`tools/workflow-runtime/implement/runtime/repository.py`、
`tools/workflow-runtime/implement/runtime/deliverables.py`、
`tools/workflow-runtime/tests/implement_execution_model_test.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`、
`tools/workflow-runtime/review/review_runtime.py`、
`tools/workflow-runtime/tests/review_runtime_test.py`。

`repository.py` は作業場所の出来事を、`deliverables.py` は成果物の承認の対象を
組み立てており、どちらも落とす欄をそのまま参照しています。review は implement の
最後の出来事の指紋を読んでいるので、読んだ内容から自分で計算する形へ変えます。

**Completion:** test

確かめること:

- 指紋を持たない出来事が追記でき、読み戻せる
- 手順書と仕様書の指紋の照合は、これまでどおり働く
- 凍結したテストの指紋の照合も、これまでどおり働く
- 出来事の並びは連番から導け、前の出来事の指紋を持たなくても順序が決まる

**実装側に任せてよい選択:** 連番の表し方。読み戻しの実装。

**止まる条件:** 承認の照合に使う 3 つの指紋のどれかを落としたくなったら止まる。仕様書は
残すと決めている。

### 2. 出来事の形式検証を消す

**目的:** 仕様書 `workflow.md` の「機械の検査は、外の世界を見るものに限る」に合わせる。
出来事の JSON の形を自分で検査するのは、機構が自分で導入したデータ構造の自己検証。

**前提:** 手順 1。

**変更してよいファイル:** `tools/workflow-runtime/implement/execution_model.py`、
`tools/workflow-runtime/implement/runtime/context.py`、
`tools/workflow-runtime/tests/implement_execution_model_test.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** check

**Checks:**

- `test -z "$(rg -l 'event_field_invalid|event_fields_invalid|event_field_missing|event_type_invalid|event_version_invalid|event_sequence_invalid|event_identity_invalid|event_identity_collision|stale_event_chain' tools/workflow-runtime/implement/ tools/workflow-runtime/tests/implement_execution_model_test.py tools/workflow-runtime/tests/implement_runtime_test.py)"`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 消そうとした検査が、外の世界について何かを言っていると分かったら止まる。
仕様書の一覧（6 項目）と突き合わせて確かめる。

### 3. 束ねと oracle とテスト結果の形式検証を消す

**目的:** 手順 2 と同じ。束ねの記録、テストの定義、テスト結果の集計の、フィールドの形を
自分で検査するのをやめる。

oracle のうち「失敗の内容が何も言っていない物を弾く」検査（`oracle_failure_signature_invalid`）
は外の世界を見ているので残す。

**前提:** 手順 2。

**変更してよいファイル:** `tools/workflow-runtime/implement/execution_model.py`、
`tools/workflow-runtime/implement/runtime/tdd.py`、
`tools/workflow-runtime/implement/runtime/repository.py`、
`tools/workflow-runtime/tests/implement_execution_model_test.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** check

**Checks:**

- `test -z "$(rg -l 'oracle_field_invalid|oracle_fields_invalid|oracle_field_missing|human_gate_binding_invalid|plan_binding_invalid|spec_binding_invalid|binding_fields_invalid|binding_version_invalid|test_summary_invalid|executor_invalid|branch_invalid|worktree_invalid|base_head_invalid' tools/workflow-runtime/implement/ tools/workflow-runtime/tests/implement_execution_model_test.py tools/workflow-runtime/tests/implement_runtime_test.py)"`
- `test -z "$(rg -l 'attempt_id_invalid|repository_identity_invalid' tools/workflow-runtime/implement/execution_model.py)"`
- `rg -q 'oracle_failure_signature_invalid' tools/workflow-runtime/implement/`
- `rg -q 'attempt_id_invalid' tools/workflow-runtime/implement/runtime/repository.py`
- `rg -q 'repository_identity_invalid' tools/workflow-runtime/implement/runtime/gitio.py`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 手順 2 と同じ。

### 4. 状態の写しを、出来事の追記と同じ操作の中で書く

**目的:** 仕様書 `workflow.md` の「状態の写し（current-status）」と、`implement.md` の
「状態の写し」に合わせる。書く経路を分けないことで、古くなる道を塞ぐ。

**前提:** 手順 1。

**変更してよいファイル:** `tools/workflow-runtime/implement/runtime/context.py`、
`tools/workflow-runtime/implement/runtime/storage.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** test

確かめること:

- 出来事を 1 件追記すると、同じ操作の中で状態の写しが書き換わる
- 出来事を追記して状態の写しを書かない経路が存在しない
- 書かれるのは 4 項目だけ（手順書のパスと版 / 完了した手順 / 最後の出来事とその理由 /
  ブランチと作業ディレクトリ）
- 「次にすべきこと」に相当する項目が無い
- 実行が終わっても消えない

**実装側に任せてよい選択:** ファイルの書式（Markdown か JSON か）。

**止まる条件:** 状態の写しを別の操作で書きたくなったら止まる。それは仕様書が禁じている形。

### 5. 委譲の記録を足す

**目的:** 仕様書 `implement.md` の「委譲されて動くとき」に合わせる。誰に渡し、どこまでで
戻ったかを記録に残す。

**前提:** 手順 1。

**変更してよいファイル:** `tools/workflow-runtime/implement/runtime/context.py`、
`tools/workflow-runtime/implement/runtime/cli.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** test

確かめること:

- 委譲の開始（実行先とモデル）と、委譲された会話が戻ったことを、それぞれ 1 件の出来事として
  記録できる
- 委譲の記録は、証拠の並びの中に他の出来事と同じ形で入る
- 委譲の記録があってもなくても、状態の写しは正しく書かれる

**実装側に任せてよい選択:** 出来事の名前。

**止まる条件:** 委譲そのものを実行する処理をここに書きたくなったら止まる。委譲を起こすのは
cycle の仕事で、implement は記録するだけ。

### 6. 手順書を本文として読む

**目的:** 仕様書 `implement.md` の「手順書の読み方」に合わせる。決まった書き方で読むのは、
参照する仕様書と変更してよい範囲の 2 つだけにする。

手順、完了の示し方、人が判断する場面、手順書の ID と版は、AI が本文を読んで理解する。
読めない書き方で機械が止まることをやめる。

**前提:** 手順 4。

**変更してよいファイル:** `tools/workflow-runtime/implement/runtime/planning.py`、
`tools/workflow-runtime/implement/runtime/cli.py`、
`tools/workflow-runtime/implement/runtime/context.py`、
`tools/workflow-runtime/implement/runtime/deliverables.py`、
`tools/workflow-runtime/implement/runtime/staging.py`、
`tools/workflow-runtime/implement/runtime/tdd.py`、
`tools/workflow-runtime/implement/runtime/resume.py`、
`tools/workflow-runtime/implement/runtime/deps.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

手順書の本文を構文として読む処理は plan 側の `plan_artifact.py` にあり、この計画では
触りません。変えるのは implement がそれを呼ぶのをやめる側です。手順の一覧を使って
いるのは `planning.py` のほか `deliverables.py`、`staging.py`、`tdd.py`、`resume.py`、
`cli.py` で、手順の見出しを正規表現で探しているのは `context.py` です。

**Completion:** test

確かめること:

- 参照する仕様書の指紋の照合が、これまでどおり働く
- 変更してよい範囲の照合が、これまでどおり働く
- 手順の見出しや完了の示し方の書き方が違っていても、実行は止まらない
- 手順の完了に必要な証拠の判定は、AI が渡した完了の示し方を入力として働く

**実装側に任せてよい選択:** 完了の示し方を AI から受け取る渡し方。

**止まる条件:** 手順書の本文を機械が解析したくなったら止まる。それは減らそうとしている物。

### 7. 停止点を 3 分類に絞る

**目的:** 仕様書 `implement.md` の「止まり方」と `workflow.md` の「承認を儀式にしない」に
合わせる。耐久的な停止を書くのは、人に返す場合だけにする。

人に返すのは、手順書に無い判断、承認した内容との食い違い、成果物の却下、許可や証拠が
得られない、同じ手順で 3 回立て直して進めない、の 5 つ。それ以外は記録を残して自分で
立て直す。

**前提:** 手順 3、手順 6。

**変更してよいファイル:** `tools/workflow-runtime/implement/runtime/` の各モジュール、
`tools/workflow-runtime/tests/implement_runtime_test.py`。

**Completion:** test

確かめること:

- 凍結したテストとの食い違いで、耐久的な停止が書かれない
- 範囲外のファイルをステージしようとしたとき、その操作は拒否されるが実行は止まらない
- 手順書に無い判断が要るときは、耐久的な停止が書かれて人に返る
- 承認した内容と食い違うときは、耐久的な停止が書かれて人に返る
- 立て直した回数が記録に残り、3 回で人に返る

**実装側に任せてよい選択:** 立て直しの回数の数え方。

**止まる条件:** 仕様書の 5 つ以外を人に返したくなったら止まる。

### 8. 残った検証を使う側へ移し、`execution_model.py` を無くす

**目的:** 仕様書 `implement.md` の「skill の構成」に合わせる。自己検証を持たなくなった
時点で、検証だけを集めたモジュールを置く理由が無くなる。

残るのは外の世界を見る 6 つ。承認内容との照合、書き込み範囲、パスの安全、人の判断、
秘密情報の検出、テストの失敗が具体的か。それぞれを使う側のモジュールへ移す。

**前提:** 手順 7。

**変更してよいファイル:** `tools/workflow-runtime/implement/` 以下すべて、
`tools/workflow-runtime/tests/implement_execution_model_test.py`、
`tools/workflow-runtime/tests/implement_runtime_test.py`、`vendor-manifest.yaml`、
`skills/ba0918-implement/scripts/execution_model.py`。

配布された複製も同時に消します。正本が無くなったのに複製が残ると、`vendor-manifest.yaml`
から消した行が指していたファイルだけが取り残されます。

**Completion:** check

**Checks:**

- `test ! -f tools/workflow-runtime/implement/execution_model.py`
- `test ! -f skills/ba0918-implement/scripts/execution_model.py`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 移し先が決まらない検査が出たら止まる。それは外の世界を見ていない可能性が
ある。

### 9. skill の文書を新しい形に合わせる

**目的:** 仕様書 `implement.md` の全体に合わせる。SKILL.md と補足 4 本を、減量後の
振る舞いに書き直す。

**前提:** 手順 8。

**変更してよいファイル:** `skills/ba0918-implement/SKILL.md`、
`skills/ba0918-implement/references/` の 4 本。

**Completion:** artifact

確かめること:

- 消えたコマンドと消えた検査が、文書のどこにも残っていない
- 状態の写しと委譲の記録の扱いが書かれている
- 止まり方の 2 種類が、仕様書と同じ線で書かれている
- `bunx skills-ref validate skills/ba0918-implement` が通る

**止まる条件:** 仕様書に書いていない振る舞いを文書に書きたくなったら止まる。

### 10. 配布の複製を作り直す

**目的:** 正本を直したあと、配布される skill の複製を同期する。

**前提:** 手順 9。

**変更してよいファイル:** `skills/ba0918-implement/scripts/`、
`skills/ba0918-review/scripts/`、`vendor-lock.json`。

`gen` は登録された全 skill の複製を作り直します。review の正本も手順 1 で変えているので、
その複製もここで揃います。

**Completion:** check

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`

**止まる条件:** 複製を手で直したくなったら止まる。複製は `gen` が作る物。

## 進め方の前提

このプロダクトのワークフロー（`ba0918-brainstorm` / `plan` / `implement` / `review` /
`cycle`）は、この作業が終わるまで使えません。作り替えている対象そのものだからです。
**この手順書の実行では、それらの skill を起動しません。**

代わりに使うのは規則の skill です。`ba0918-tdd`（テストを先に失敗させる）、
`ba0918-commit`（1 関心事 1 コミット、staging を個別に行う）、`ba0918-design`、
`ba0918-placement`、`ba0918-secrets`。

証拠は残しません。git のコミットが記録です。手順ごとに 1 コミット以上を作り、
コミットメッセージに理由を書きます。
