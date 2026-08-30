# investigate 手順書

## Goal

読むだけで原因を調べる skill `ba0918-investigate` を、仕様書どおりに 1 つのブランチで作る。
人が受け取るのは、`skills/ba0918-investigate/` と、それに合わせて直した `PROJECT.md`、review の起動語、回帰の scenario 2 本である。

## Specification

`docs/spec/investigate.md` が唯一の仕様書である。
各手順は、この仕様書の節を見出し名で指す。
この手順書に写しているのは、検査コマンドに要る値（行数の上限、起動語、報告の固定語）だけである。
その節を読んでから手順を始める。
上位に理念（`docs/principles.md`）と用語集（`CONTEXT.md`）があり、言葉の意味はそちらに従う。

## Approach and why

成果物はすべて文書（英語の skill 本文、Markdown、YAML、JSON）で、コードは無い。
したがって完了の示し方はテストではなく、作った物と検査である。
TDD の経路は通らない。
skill 本文の意味（仕様書の節を写しているか、作らない物を含まないか）は機械では判定できない。
それは cycle の review が仕様書と突き合わせて確かめるので、手順の検査は形式に限る。

作る順は、skill 本文 → `PROJECT.md` → review の起動語と lock → scenario とする。
skill 本文が先なのは、他の 3 つがそれを前提にするからである。
review の起動語と lock を 1 つの手順にまとめるのは、片方だけを commit すると lock が一時的に嘘になるからである。
scenario を最後にするのは、skill 本文の確定した文言に合わせて期待を書くためである。

## Scope of change

変えてよいのは次の範囲だけである。

- `skills/ba0918-investigate/`（新規）
- `PROJECT.md`
- `skills/ba0918-review/SKILL.md` の frontmatter にある description の 1 行
- `regression-lock.json` の `ba0918-review` のエントリ
- `evals/cases/ba0918-investigate/`（新規）と `evals/inputs/ba0918-investigate/`（新規）

`docs/spec/workflow.md`、`CONTEXT.md`、他の skill の本文と参照資料は変えない。

## Step order and prerequisites

手順 1 → 2 → 3 → 4 の順に進める。
手順 2 以降はすべて手順 1 の完了を前提にする。
ブランチと worktree はこのリポジトリに立てる（cycle を起動する前にメインセッションが作る）。
手順 3 と 4 は `~/.claude/skills/ba0918-skill-regression/scripts/` が使えることを前提にする。
使うのは `lock.py` と `fixture_setup.py` である。

各手順の検査コマンドは、その手順の commit の前に走らせる。
commit の後に走らせる物は、その手順に明記する。

## Verification map

| 仕様書の節 | 確かめる手順 |
|---|---|
| 責務、進め方、事故のとき | 手順 1（本文に写す。review が突き合わせる） |
| 読むだけの保証、報告、推奨する次の行動 | 手順 1（本文に写す）、手順 4（scenario の期待にする） |
| 起動する言葉と診断との境界 | 手順 1（description の語）、手順 3（review の description の語） |
| 作る物: skill 本文 | 手順 1 |
| 作る物: `PROJECT.md` の 3 か所 | 手順 2 |
| 作る物: review の description と lock エントリ | 手順 3 |
| 作る物: scenario 2 本と入力 | 手順 4 |
| 作らない物 | 手順 1（本文に無いこと。review が突き合わせる）、手順 4（investigate の lock エントリを置かないこと） |

## Left to the implementer

- `references/` を作るかどうか。SKILL.md だけで足りるなら作らない
- 英語の言い回しと SKILL.md の内部構成
- description の英語の起動語の書き方。ただし `verify`、`validate`、`confirm the implementation` は入れない
- scenario の id（`iv-001`、`iv-002` を推奨）、入力ファイルの名前、英語表現

## Stop conditions

止まるのは理念の「人を止める 4 つの場面」だけである。
この手順書で起こりうる形を当てはめると次のとおりである。
返す先は cycle であり、意味の判断は cycle が人へ渡して brainstorm に戻る。

- 仕様書の要求をどれも落とさずに SKILL.md と参照資料の合計を 163 行に収められない。要求を削るのは承認済みの内容を変える判断なので、ここで決めない（理念の「承認済みの内容から動いた」）
- `skills-ref validate` が、仕様書が求める形を受け付けない（同上）
- scenario の期待を書くのに、仕様書に無い振る舞いを決める必要がある（理念の「意味が足りない」）
- `lock.py --update` がエラーになり、原因を診断して方法を 1 回変えても直らない（理念の「診断して方法を変えても進捗が無い」）。`regression-lock.json` を手で編集することは方法の変更に含めない

## Test command

コードが無いのでテストコマンドは無い。
各手順の検査コマンドを、書かれた順に走らせる。
合否は終了コードではなく、各手順に書いた条件で判定する。
`rg` は一致が無いと終了コード 1 を返し、`lock.py --check` は未検証の skill があると終了コード 1 を返す。

## Out of scope

- `CONTEXT.md`（仕様書と一緒に承認とコミットが済んでいる）
- `docs/spec/workflow.md` と他の skill の本文
- scenario を実走すること。人が頼んだときだけ別に行う
- 旧リポジトリ（`~/develop/claude-skills/`）の掃除
- iterate skill

## Step 1 — `skills/ba0918-investigate/` の skill 本文

Purpose: 仕様書の内容を実行者向けの英語の指示に写し、1 つの skill にする。
Specification: `docs/spec/investigate.md#責務`、`#読むだけの保証`、`#進め方`、`#報告`、`#事故のとき`、`#起動する言葉と診断との境界`、`#作らない物`。上限と自己完結の縛りは冒頭の段落。
Prerequisites: 無し。既存の skill の形は `skills/ba0918-review/SKILL.md` を先例にする。
May change: `skills/ba0918-investigate/` の下だけ。
Done when: 次の 6 つが揃っている。

- frontmatter の `name` が `ba0918-investigate` である
- description は `description:` で始まる 1 行に書く（先例と同じ）
- description に仕様書の日本語の起動語 4 つがすべてあり、診断が受け持つ語（日本語 3 語と `verify`、`validate`、`confirm the implementation`）は無い。本文の境界の節が「起動しない語」としてそれらを挙げるのは可
- 本文が仕様書の節をすべて写し、作らない物に挙がった振る舞いを含まない。これは cycle の review が仕様書と突き合わせて判定する
- 旧 claude-skills のコマンド（iterate、issue-create、plan-create）への言及が無い
- 仕様書や他の文書をパスで参照していない

Shown by: artifact — `skills/ba0918-investigate/SKILL.md`（と、作るなら `references/`）。形式の検査は次のとおり。

```text
bunx skills-ref validate skills/ba0918-investigate
find skills/ba0918-investigate -name '*.md' -exec cat {} + | wc -l
for w in 調べて 原因を調査 なぜ 影響範囲; do sed -n '/^description:/p' skills/ba0918-investigate/SKILL.md | rg -q "$w" && echo "ok $w"; done
sed -n '/^description:/p' skills/ba0918-investigate/SKILL.md | rg -i '検証|動作確認|実装確認|verif|validat|confirm the implementation'
rg -n 'iterate|issue-create|plan-create|docs/|CONTEXT\.md|PROJECT\.md' skills/ba0918-investigate
```

合格の条件は順に次のとおりである。

1. エラー無し
2. 1 以上 163 以下
3. `ok` の行が 4 つ出る
4. 何も出ない
5. 何も出ない

Left to the implementer: `references/` の有無、英語の言い回し、節の順。
Stop and hand back if: 仕様書の要求を落とさないと 163 行に収まらない。

## Step 2 — `PROJECT.md` の 3 か所

Purpose: 入口の文書が skill 6 つの実態と、新しい仕様書の正本としての位置を示すようにする。
Specification: `docs/spec/investigate.md#作る物`（`PROJECT.md` の項目）。
Prerequisites: 手順 1。
May change: `PROJECT.md` だけ。
Done when: 次の 2 つが揃っている。

- 冒頭の数、正本の表、縛りの文言の 3 か所が仕様書の項目どおりに変わり、他の行は変わっていない
- 正本の表に足した行が、review の description に足す起動語の根拠もこの仕様書であることを述べている

Shown by: check — `git add` の前に次を順に走らせる。

```text
rg -n '読むだけの調査' PROJECT.md
rg -n 'docs/spec/investigate.md' PROJECT.md
rg -n '5 つの責務' PROJECT.md
git diff PROJECT.md
```

合格の条件は順に次のとおりである。

1. 冒頭の行が出る
2. 正本の表の行が出る
3. 何も出ない
4. 差分が、冒頭の 1 行、表の 1 行の追加、縛りの 1 行だけである

Left to the implementer: 表の行の言い回し。
Stop and hand back if: 無し。

## Step 3 — review の起動語と lock の受け入れ

Purpose: 「動作確認して」などを診断が受け取れるように review の description に語を足し、lock をそれに合わせる。
Specification: `docs/spec/investigate.md#起動する言葉と診断との境界`。
`#作る物` の review の description と `regression-lock.json` の項目。
Prerequisites: 手順 1。`python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py` が動く。
May change: `skills/ba0918-review/SKILL.md` の description の 1 行。
`regression-lock.json` の `ba0918-review` のエントリ。
Done when: 次の 2 つが揃い、1 つの commit に入っている。

- description の日本語キーワードに「検証 動作確認 実装確認」がある
- lock の `ba0918-review` が新しいハッシュで `accepted-without-run` になっている

Shown by: check — 次を順に走らせる。lock の更新と commit も、この列の中で行う。

```text
rg -n '検証 動作確認 実装確認' skills/ba0918-review/SKILL.md
bunx skills-ref validate skills/ba0918-review
python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py --update ba0918-review --accept \
  --note "description only: trigger words added for diagnosis; scenarios call the skill explicitly, so results are unaffected" .
python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py --check .
git add skills/ba0918-review/SKILL.md regression-lock.json
git commit
git show --stat HEAD
```

合格の条件は順に次のとおりである。

1. description の行が出る
2. エラー無し
3. エラー無し
4. 出力に `ba0918-review` を含まない
5. （commit）
6. （commit）
7. 最後の commit がこの 2 ファイルだけを含む

Left to the implementer: 無し。
Stop and hand back if: `lock.py --update` のエラーが、診断して方法を 1 回変えても直らない。`regression-lock.json` を手で直さない。

## Step 4 — 回帰の scenario 2 本と入力

Purpose: 旧 fixtures の 2 本を、仕様書の対応表と報告の形に合わせて回帰の scenario にする。
Specification: `docs/spec/investigate.md#作る物` の scenario の項目と、`#作らない物` の lock エントリの項目。
期待の元は `#読むだけの保証`、`#報告`、`#推奨する次の行動`。
Prerequisites: 手順 1。形の先例は `evals/cases/ba0918-review/rv-001.yaml`、入力の置き方は `evals/inputs/ba0918-review/`。旧 fixtures は `/home/mizumi/develop/claude-skills/skills/investigate/fixtures.json` の `iv-001` と `iv-002`。
May change: `evals/cases/ba0918-investigate/` と `evals/inputs/ba0918-investigate/` だけ。`regression-lock.json` は触らない。
Done when: 次がすべて揃っている。

- scenario が 2 本あり、`skill` が `ba0918-investigate`、`exercises` が `skills/ba0918-investigate/SKILL.md` を指す
- `source` は既存の形（`acceptance:<日付>`）にし、旧 fixtures の値（`empirical-tuning:...`）を写さない。実走していないので、実測を主張する値にしない
- `isolation` は既定の `worktree` にする。旧 fixtures の `none` を写さない
- 旧 fixtures がプロンプトに書いていた事実（ファイルの中身、テストの有無）は、内容を変えずに `evals/inputs/ba0918-investigate/` の実ファイルに写す。scenario は `files` と `git: init: true` / `commit: true` / `message: baseline` で、それを baseline commit にする。調べる対象が追跡されたファイルとして無いと、編集ゼロを成果物で判定できない
- プロンプトは報告の出力先を書かない。報告は実行者の応答で判定する
- 1 本目（旧 iv-001）の期待: 直接の原因と根本の原因が特定され、5 節に実行していない修正案が並び、`no fix needed` を含まない
- 2 本目（旧 iv-002）の期待: 5 節が `no fix needed` で始まり、6 節が `no further action needed` か任意の将来改善だけを出す
- 両方の期待: 応答に 6 節の見出しがあり、確信度に根拠が付き、baseline commit からの差が無い（`git status` が clean のまま）
- 旧 claude-skills のコマンド（iterate、issue-create、plan-create）への言及が無い

Shown by: check — 次を順に走らせる。

```text
python3 ~/.claude/skills/ba0918-skill-regression/scripts/fixture_setup.py --validate evals/cases/ba0918-investigate/*.yaml
rg -n '^skill: ba0918-investigate' evals/cases/ba0918-investigate
rg -n 'skills/ba0918-investigate/SKILL.md' evals/cases/ba0918-investigate
rg -n 'iterate|issue-create|plan-create|empirical-tuning|isolation: none' evals/cases/ba0918-investigate evals/inputs/ba0918-investigate
ls -R evals/inputs/ba0918-investigate
python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py --check .
```

合格の条件は順に次のとおりである。

1. エラー無し
2. 2 ファイルから出る
3. 2 ファイルから出る
4. 何も出ない
5. 各 scenario の `files` に挙げたパスがすべて存在する
6. `ba0918-investigate` を未検証として挙げ、終了コードは 1 になる。これで合格である

6 つ目は仕様書の作らない物どおりの状態であり、直さない。

Left to the implementer: scenario の id、入力ファイルの名前、英語表現。
Stop and hand back if: 仕様書に無い振る舞いを決めないと期待が書けない。

## Commits

1 手順につき 1 commit を目安にする。
手順 3 の 2 ファイルは必ず同じ commit に入れる。
commit メッセージに手順番号や工程名を書かない。
