# iterate 手順書

## Goal

手順書の要らない小さいタスクを review 付きで回す skill `ba0918-iterate` を、仕様書どおりに 1 つのブランチで作る。
人が受け取るのは、`skills/ba0918-iterate/` と、それに合わせて直した `skills/ba0918-investigate/SKILL.md` と `PROJECT.md` である。
要るなら cycle の本文の言い回しの直しと、回帰の scenario 2 本も受け取る。

## Specification

`docs/spec/iterate.md` が唯一の仕様書である。
各手順は、この仕様書の節を見出し名で指す。
この手順書に写しているのは、検査コマンドに要る値（行数の上限、起動語、禁じる旧語彙）だけである。
その節を読んでから手順を始める。
上位に理念（`docs/principles.md`）と用語集（`CONTEXT.md`）があり、言葉の意味はそちらに従う。
iterate は cycle の本文を skill 名で呼び出して読み替える形である。
そのため `skills/ba0918-cycle/SKILL.md` と、開発ワークフロー仕様（`docs/spec/workflow.md`）の cycle の節も、手順 1 と 2 の前に読む。

## Approach and why

成果物はすべて文書（英語の skill 本文、Markdown、YAML、JSON）で、コードは無い。
したがって完了の示し方はテストではなく、作った物と検査である。
TDD の経路は通らない。
skill 本文の意味（仕様書の節を写しているか、読み替えの表が cycle の本文を覆っているか、作らない物を含まないか）は機械では判定できない。
それは cycle の review が仕様書と突き合わせて確かめるので、手順の検査は形式に限る。

作る順は、skill 本文 → cycle 本文の読み違えの判定 → investigate の本文 → `PROJECT.md` → scenario とする。
skill 本文が先なのは、他の 4 つがそれを前提にするからである。
cycle 本文の判定を 2 番目にするのは、読み替えの表を英語に写して初めて、cycle の本文のどの文が読み違えを招くかが見えるからである。
この手順は「変更しない」で終わってよく、そのときは根拠を記録する。
変更したときだけ `regression-lock.json` の cycle のエントリを同じ commit で取り直す。
片方だけを commit すると lock が一時的に嘘になるからである。
investigate の本文には lock のエントリが無いので、直しても lock は触らない。
scenario を最後にするのは、skill 本文の確定した文言に合わせて期待を書くためである。

## Scope of change

変えてよいのは次の範囲だけである。

- `skills/ba0918-iterate/`（新規）
- `skills/ba0918-cycle/SKILL.md`（言い回しの直しに限る。約束は変えない）
- `regression-lock.json` の `ba0918-cycle` のエントリ（cycle の本文を変えたときだけ）
- `skills/ba0918-investigate/SKILL.md` の推奨表の行と、その直後の小さい修正の定義の段落
- `PROJECT.md` の正本の表の 1 行
- `evals/cases/ba0918-iterate/`（新規）と `evals/inputs/ba0918-iterate/`（新規）

`docs/spec/`、`CONTEXT.md`、`ROADMAP.md`、他の skill の本文と参照資料は変えない。

## Step order and prerequisites

手順 1 → 2 → 3 → 4 → 5 の順に進める。
手順 2 以降はすべて手順 1 の完了を前提にする。
ブランチと worktree はこのリポジトリに立てる（cycle を起動する前にメインセッションが作る）。
手順 2 と 5 は `~/.claude/skills/ba0918-skill-regression/scripts/` が使えることを前提にする。
使うのは `lock.py` と `fixture_setup.py` である。

各手順の検査コマンドは、その手順の commit の前に走らせる。
commit の後に走らせる物は、その手順に明記する。

## Verification map

| 仕様書の節 | 確かめる手順 |
|---|---|
| 責務、受け取る物と返す物、要求 | 手順 1（本文に写す。review が突き合わせる） |
| 小さいタスクの判定（4 つの条件、判定役） | 手順 1（本文に写す）、手順 5（scenario の期待にする） |
| 収まらないときの案内 | 手順 1（本文に写す）、手順 5（2 本目の scenario の期待にする） |
| ループ、読み替える点 | 手順 1（読み替える点だけを本文に持ち、ループの約束は写さない）、手順 2（cycle 本文が読み替えを受け付けるか） |
| 終端報告とやらないこと | 手順 1（本文に写す）、手順 5（1 本目の scenario の期待にする） |
| 起動する言葉と境界 | 手順 1（起動語は description だけに置く。境界は本文に写す） |
| 作る物: skill 本文 | 手順 1 |
| 作る物: cycle の `SKILL.md` と lock | 手順 2 |
| 作る物: investigate の本文 | 手順 3 |
| 作る物: `PROJECT.md` の行 | 手順 4 |
| 作る物: scenario 2 本と入力 | 手順 5 |
| 作らない物 | 手順 1（本文に無いこと。review が突き合わせる）、手順 5（iterate の lock エントリを置かないこと） |

## Left to the implementer

- `references/` を作るかどうか。SKILL.md だけで足りるなら作らない
- 英語の言い回しと SKILL.md の内部構成。読み替えの表を表のまま写すか文にするか
- description の英語の起動語の書き方。ただし仕様書が挙げる 5 つの英語の語句は入れ、`investigate`、`verify`、`validate` は入れない
- scenario の id（`it-001`、`it-002` を推奨）、入力ファイルの名前、英語表現
- cycle の本文を直すときの言い回し

## Stop conditions

止まるのは理念の「人を止める 4 つの場面」だけである。
この手順書で起こりうる形を当てはめると次のとおりである。
返す先は cycle であり、意味の判断は cycle が人へ渡して brainstorm に戻る。

- 仕様書の要求をどれも落とさずに SKILL.md と参照資料の合計を 113 行に収められない。要求を削るのは承認済みの内容を変える判断なので、ここで決めない（理念の「承認済みの内容から動いた」）
- `skills-ref validate` が、仕様書が求める形を受け付けない（同上）
- cycle の本文の言い回しを直すだけでは読み替えが成立せず、cycle の約束そのものを変える必要がある。約束の変更は開発ワークフロー仕様の判断なので、ここで決めない（同上）
- scenario の期待を書くのに、仕様書に無い振る舞いを決める必要がある（理念の「意味が足りない」）
- `lock.py --update` がエラーになり、原因を診断して方法を 1 回変えても直らない（理念の「診断して方法を変えても進捗が無い」）。`regression-lock.json` を手で編集することは方法の変更に含めない

## Test command

コードが無いのでテストコマンドは無い。
各手順の検査コマンドを、書かれた順に走らせる。
合否は終了コードではなく、各手順に書いた条件で判定する。
`rg` は一致が無いと終了コード 1 を返し、`lock.py --check` は未検証の skill があると終了コード 1 を返す。

## Out of scope

- `docs/spec/iterate.md`、`docs/spec/investigate.md`、`CONTEXT.md`（仕様書と一緒に承認とコミットが済んでいる）
- `docs/spec/workflow.md` と、cycle 以外の skill の本文
- `PROJECT.md` の縛りの文言（仕様書が却下した）
- `ROADMAP.md`（承認の対象外。メインセッションが後で触る）
- `regression-lock.json` の iterate のエントリ（仕様書の作らない物）
- scenario を実走すること。人が頼んだときだけ別に行う
- 旧リポジトリ（`~/develop/claude-skills/`）の掃除

## Step 1 — `skills/ba0918-iterate/` の skill 本文

Purpose: 仕様書の内容を実行者向けの英語の指示に写し、cycle を名前で呼び出して読み替える 1 つの skill にする。
Specification: `docs/spec/iterate.md#責務` / `#受け取る物と返す物` / `#要求` / `#小さいタスクの判定` / `#4 つの条件` / `#判定役`。
続けて `#収まらないときの案内` / `#ループ` / `#読み替える点` / `#終端報告とやらないこと` / `#起動する言葉と境界` / `#作らない物`。
上限と名前での呼び出しの縛りは冒頭の段落。
Prerequisites: 無し。既存の skill の形は `skills/ba0918-investigate/SKILL.md` と `skills/ba0918-cycle/SKILL.md` を先例にする。読み替えの元になる cycle の本文を先に読む。
May change: `skills/ba0918-iterate/` の下だけ。
Done when: 次がすべて揃っている。

- frontmatter の `name` が `ba0918-iterate` である
- description は `description:` で始まる 1 行に書く（先例と同じ）
- description に仕様書の日本語の起動語 5 つと英語の語句 5 つがすべてある
- description に investigate と診断が受け持つ語（「調べて」「動作確認」「検証」と `investigate` / `verify` / `validate`）は無い。本文の境界の節が「起動しない語」としてそれらを挙げるのは可
- 本文が cycle の skill を `ba0918-cycle` の名前で呼び出し、仕様書の読み替える点をすべて写している。ループの約束と起動語は本文に写さない
- それ以外の節は本文に写し、作らない物に挙がった振る舞いを含まない。これは cycle の review が仕様書と突き合わせて判定する
- 起動語 5 つが description 行の外に現れない
- 旧 iterate の語彙への言及が無い。語彙は BLOCK / WARN / PASS / Codex / Additional Changes / status.md / workspace lock / satellite
- 旧 claude-skills のコマンド（issue-create / plan-create）への言及が無い
- 仕様書や他の文書をパスで参照していない
- 判定役に写す読むだけの縛りが、仕様書の判定役の節が挙げる 5 つと「ファイルを一切書かない」「さらに委譲しない」を含む

Shown by: artifact — `skills/ba0918-iterate/SKILL.md`（と、作るなら `references/`）。形式の検査は次のとおり。

```text
bunx skills-ref validate skills/ba0918-iterate
find skills/ba0918-iterate -name '*.md' -exec cat {} + | wc -l
for w in iterate ちょっと直して これも足して もう少し磨いて 小さいタスク 'one more fix' 'fix this bit' 'add this too' 'polish it a little more'; do sed -n '/^description:/p' skills/ba0918-iterate/SKILL.md | rg -q -F "$w" && echo "ok $w"; done
sed -n '/^description:/p' skills/ba0918-iterate/SKILL.md | rg -i '調べて|動作確認|検証|investigat|verif|validat'
rg -c 'ba0918-cycle' skills/ba0918-iterate/SKILL.md
rg -n 'BLOCK|WARN|PASS|Codex|Additional Changes|status\.md|workspace lock|satellite|issue-create|plan-create' skills/ba0918-iterate
rg -n 'docs/|CONTEXT\.md|PROJECT\.md' skills/ba0918-iterate
rg -n 'ちょっと直して|これも足して|もう少し磨いて|小さいタスク|one more fix|fix this bit|add this too|polish it a little more' skills/ba0918-iterate | rg -v '^[^:]+:[0-9]+:description:'
```

合格の条件は順に次のとおりである。

1. エラー無し
2. 1 以上 113 以下
3. `ok` の行が 9 つ出る（`iterate` は日本語と英語の両方に数えるので、語は 10 ではなく 9）
4. 何も出ない
5. 1 以上
6. 何も出ない
7. 何も出ない
8. 何も出ない

Left to the implementer: `references/` の有無、英語の言い回し、節の順、読み替えを表で写すか文で写すか。
Stop and hand back if: 仕様書の要求を落とさないと 113 行に収まらない。

## Step 2 — cycle の本文が読み替えを受け付けるかの判定

Purpose: iterate が cycle の本文を呼び出して読み替えたとき、手順書を前提にした文が読み違えを招かないことを確かめ、招くなら言い回しだけ直す。
Specification: `docs/spec/iterate.md#読み替える点`、`#作る物`（cycle の `SKILL.md` の項目）。約束を変えない縛りは同じ項目。
Prerequisites: 手順 1。`python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py` が動く。
May change: `skills/ba0918-cycle/SKILL.md` の言い回しと、`regression-lock.json` の `ba0918-cycle` のエントリ。
Done when: 次のどちらかで終わっている。

- 読み違えを招く文が無い。手順 1 の本文の読み替えの表と cycle の本文を突き合わせた根拠（読み替えの各行が cycle のどの文に当たり、そのまま読めること）を実装の報告に書き、ファイルは変えない
- 読み違えを招く文がある。cycle の約束（入力 / ループ / 判断の所有 / 終わり方 / 終端報告 / やらないこと）を変えずに言い回しだけ直す。lock の `ba0918-cycle` を新しいハッシュで `accepted-without-run` にして、2 ファイルを 1 つの commit に入れる

Shown by: check — 変えないときは 1 つ目だけを走らせ、変えるときは全部を順に走らせる。lock の更新と commit も、この列の中で行う。

```text
git diff skills/ba0918-cycle/SKILL.md
bunx skills-ref validate skills/ba0918-cycle
find skills/ba0918-cycle -name '*.md' -exec cat {} + | wc -l
python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py --update ba0918-cycle --accept \
  --note "wording only: plan-presuming sentences rephrased so iterate can read the body with its substitutions; no promise changed" .
python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py --check .
git add skills/ba0918-cycle/SKILL.md regression-lock.json
git commit -m "<メッセージ>"
git show --stat HEAD
```

合格の条件は順に次のとおりである。

1. 変えないときは何も出ない。変えるときは差分が言い回しの行だけである。Inputs / Loop / Delegations / Judgment / Stopping / Endings / Terminal report の各節の約束が増減していない
2. エラー無し
3. 1 以上 110 以下
4. エラー無し
5. 出力に `ba0918-cycle` を含まない
6. （commit）
7. （commit）
8. 最後の commit がこの 2 ファイルだけを含む

cycle の `SKILL.md` はいま上限の 110 行ちょうどである。
直すときは行数を増やさない形にし、増えるなら同じ節の中で詰めて 110 行以内に収める。

Left to the implementer: 直すときの言い回しと、詰めるときにどの文を短くするか。
Stop and hand back if: 言い回しの直しでは足りず、cycle の約束を変えないと読み替えが成立しない。`lock.py --update` のエラーが、診断して方法を 1 回変えても直らない。`regression-lock.json` を手で直さない。

## Step 3 — investigate の本文の推奨表

Purpose: 調査 skill 仕様の改訂（小さい修正の定義を用語集の小さいタスクに統一し、推奨表を iterate への案内にする）を、その写しである skill 本文に反映する。
Specification: `docs/spec/iterate.md#作る物`（investigate の本文の項目）。写す元は `docs/spec/investigate.md#推奨する次の行動`。
Prerequisites: 手順 1（案内の呼び出しの形 `/ba0918-iterate <要求>` が確定していること）。
May change: `skills/ba0918-investigate/SKILL.md` の推奨表の行と、その直後の小さい修正の定義の段落だけ。
Done when: 次の 3 つが揃っている。

- 推奨表の小さい修正の行が、小さいタスクを iterate へ案内する行になっている。すぐ使える形は `/ba0918-iterate <request>` で、要求が直す場所と内容を含むことも仕様書の行どおりに書く
- 同じ段落にある「後回しは人が控える」の一文は残す（仕様書はこの文を残している）
- 定義の段落が、改訂後の `docs/spec/investigate.md#推奨する次の行動` の定義文と同じ意味になっている。「3 ファイルまで」を持たず、用語集をパスで参照しない
- 他の行は変わっていない。行数が 163 以下のままである

Shown by: check — 次を順に走らせる。

```text
rg -n 'Small fix|at most three files|four-file' skills/ba0918-investigate/SKILL.md
rg -n 'ba0918-iterate' skills/ba0918-investigate/SKILL.md
rg -n 'docs/|CONTEXT\.md|PROJECT\.md' skills/ba0918-investigate
bunx skills-ref validate skills/ba0918-investigate
find skills/ba0918-investigate -name '*.md' -exec cat {} + | wc -l
git diff skills/ba0918-investigate/SKILL.md
```

合格の条件は順に次のとおりである。

1. 何も出ない
2. 推奨表の行が出る
3. 何も出ない
4. エラー無し
5. 1 以上 163 以下
6. 変更が 1 ファイルで、差分が推奨表の 1 行と定義の段落に収まっている

Left to the implementer: 英語の言い回し。
Stop and hand back if: 無し。

## Step 4 — `PROJECT.md` の正本の表

Purpose: 入口の文書が、新しい仕様書を正本として示すようにする。
Specification: `docs/spec/iterate.md#作る物`（`PROJECT.md` の項目）。
Prerequisites: 手順 1。
May change: `PROJECT.md` の正本の表の 1 行だけ。
Done when: 正本の表に `docs/spec/iterate.md` の行があり、役目として小さいタスク skill（iterate）の仕様書だと述べ、他の行は変わっていない。

Shown by: check — `git add` の前に次を順に走らせる。

```text
rg -n 'docs/spec/iterate.md' PROJECT.md
git diff PROJECT.md
```

合格の条件は順に次のとおりである。

1. 正本の表の行が出る
2. 差分が表の 1 行の追加だけである

Left to the implementer: 表の行の言い回し。
Stop and hand back if: 無し。

## Step 5 — 回帰の scenario 2 本と入力

Purpose: 仕様書が作る物に挙げる 2 本の scenario（小さいタスクの完走と、影響が読めない要求で止まること）を、成果物から判定できる形に置く。
Specification: `docs/spec/iterate.md#作る物` の scenario の項目と、`#作らない物` の lock エントリの項目。
期待の元は `#受け取る物と返す物`、`#4 つの条件`、`#収まらないときの案内`、`#終端報告とやらないこと`。
Prerequisites: 手順 1。形の先例は 2 本ある。
1 本は `evals/cases/ba0918-cycle/cy-001.yaml` で、ブランチと worktree を前提にする scenario である。
もう 1 本は `evals/cases/ba0918-investigate/iv-002.yaml` である。
入力の置き方は `evals/inputs/ba0918-cycle/` を先例にする。
May change: `evals/cases/ba0918-iterate/` と `evals/inputs/ba0918-iterate/` だけ。`regression-lock.json` は触らない。
Done when: 次がすべて揃っている。

- scenario が 2 本あり、`skill` が `ba0918-iterate`、`exercises` が `skills/ba0918-iterate/SKILL.md` を指す
- `source` は既存の形（`acceptance:<日付>`）にする。実走していないので、実測を主張する値にしない
- `isolation` は既定の `worktree` にする
- 入力は仕様書の無い小さなリポジトリ（README と、ソース 1〜2 ファイルと、そのテスト）を `evals/inputs/ba0918-iterate/` の実ファイルとして置く。scenario は `files` と `git: init: true` / `commit: true` / `message: baseline` で、それを baseline commit にする。commit の有無を成果物で判定するためである
- 入力が満たす性質は 2 つ。1 本目の要求の対象を直してもテストが落ちないこと。2 本目の要求が指す名前は 4 か所以上から呼ばれ、少なくとも 1 か所は他と直し方が変わること
- プロンプトは cycle の scenario と同じ形にする。ブランチ（現在のブランチ）と worktree（このディレクトリ）と要求を渡し、人は答えられないので聞くことがあれば報告に書いて止まる、と書く
- 1 本目（完走）の要求は、1 ファイルの中の 1 か所を、文言まで指定して直す物にする
- 1 本目の期待は成果物で書く。baseline の後に commit があること。応答に `docs/spec/workflow.md#終端報告` の必ず見せる物があること。判定役を委譲して 4 つの条件を判定したことが報告にあること。最後の 1 つと review の往復の中身は `critical: false` にする。委譲の経路は executor によって測れないことがあり、cycle の scenario がそう記録している
- 2 本目（止まる）の要求は、入力の中で多数の場所から呼ばれる名前を、呼び出し元ごとに直し方が変わる形で変える物にする。入力には、その名前の呼び出し元を判断なしには列挙し切れない数だけ置く
- 2 本目の期待は次のとおり。baseline の後に commit が無い。応答が `docs/spec/iterate.md#収まらないときの案内` の 3 つの要素を持ち、外れた条件に 4 を挙げる。仕様書が無いので `/ba0918-brainstorm` を案内し、`/ba0918-plan` を案内しない。「それでも続ける」の選択肢が無い
- 両方の期待: 実行者が自分でブランチや worktree を作っていないこと、`.agents/artifacts/reviews/` の指摘 JSON を作るなら worktree 直下であること
- 旧 iterate の語彙と旧 claude-skills のコマンドへの言及が無い

Shown by: check — 次を順に走らせる。

```text
python3 ~/.claude/skills/ba0918-skill-regression/scripts/fixture_setup.py --validate evals/cases/ba0918-iterate/*.yaml
rg -n '^skill: ba0918-iterate' evals/cases/ba0918-iterate
rg -n 'skills/ba0918-iterate/SKILL.md' evals/cases/ba0918-iterate
rg -n '^isolation: worktree' evals/cases/ba0918-iterate
rg -n '^source: acceptance:' evals/cases/ba0918-iterate
rg -n 'BLOCK|WARN|PASS|Codex|Additional Changes|status\.md|workspace lock|satellite|issue-create|plan-create|empirical-tuning' evals/cases/ba0918-iterate evals/inputs/ba0918-iterate
ls -R evals/inputs/ba0918-iterate
python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py --check .
```

合格の条件は順に次のとおりである。

1. エラー無し
2. 2 ファイルから出る
3. 2 ファイルから出る
4. 2 ファイルから出る
5. 2 ファイルから出る
6. 何も出ない
7. 出力を各 scenario の `files` と目で突き合わせ、挙げたパスがすべて存在する。`--validate` は入力ファイルの実在を見ないので、ここは人手の突き合わせである
8. `ba0918-iterate` を未検証として挙げ、終了コードは 1 になる。これで合格である。`ba0918-investigate` も未検証として並ぶが、これはこの手順書の前からの状態であり直さない

8 つ目は仕様書の作らない物どおりの状態であり、直さない。

Left to the implementer: scenario の id、入力の題材と言語、入力ファイルの名前、英語表現。
Stop and hand back if: 仕様書に無い振る舞いを決めないと期待が書けない。

## Commits

1 手順につき 1 commit を目安にする。
手順 2 で cycle の本文を変えたときは、2 ファイルを必ず同じ commit に入れる。
変えなかったときは手順 2 の commit は無く、根拠は実装の報告に残す。
cycle が再開時に手順 2 を未実施と推論しても、判定のやり直しは同じ結果になるので構わない。
commit メッセージに手順番号や工程名を書かない。
