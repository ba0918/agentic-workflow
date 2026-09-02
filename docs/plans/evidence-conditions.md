# evidence-conditions 実装の手順書

## Goal

開発ワークフロー仕様の改訂を 5 つの skill の本文と参照資料に写し、配布物と記録を揃える。
改訂の中身は、確かめ方が証拠として数えられる条件、cycle の機械的な検査と新しい終わり方、review の両方向の突き合わせ、行数上限の扱いである。

## Specification

`docs/spec/workflow.md`（コミット済み、9fc3e63 以降）。
この手順書は仕様書の節を参照し、本文を写さない。
各 step の Done when は、仕様書の節の規則を全部写していることを前提に、この手順書だけが決めること（置き場、見出し語、写さない物、記録）を書く。
実装者は各 step の前に、参照された節を必ず読む。
行数上限の扱いは `docs/spec/workflow.md` の冒頭（「行数の上限は」の段落）に従う。

## Approach and why

review → cycle → implement → plan → brainstorm の順に本文を直し、最後に正本の英語 2 段落を写す。
review を先にするのは、cycle が reviewer と修正役に貼る物を review の節名とファイル名で指すからである。
写しを最後の独立した step にするのは、写しに添える agentic-rules のリリース版がまだ無く、その待ちで他の step を止めないためである。
写しの置き場は先に決めておく。
review は新しい参照資料 `skills/ba0918-review/references/oracle-evidence.md` である。
plan は `references/step-template.md` の末尾である。
brainstorm は `SKILL.md` の「Writing the specification」の節である。
どの写しも見出し `Evidence conditions` の下に置き、他の step はその見出し語で写しを指す。
review を別ファイルにするのは、cycle が修正役に貼る第 1 段落をファイル名で取れるようにするためである。
CHANGELOG は skill を変える commit と同じ commit に書く（`PROJECT.md`「配布と版」）。
regression-lock は本文を変えた skill ごとに、実走せずに取り直す。
scenario の実走はしない（仕様書「仕様書に書く前の見直し」の末尾。人が明示していない）。
skill 本文が仕様書の節を写しているかは、機械では確かめず、cycle の review が仕様書と突き合わせて判定する。
各 step の Shown by は形式の検査と行数と CHANGELOG の存在だけを機械で見る。
ブランチと worktree は cycle を起動する前にメインセッションが作る。この手順書の step には含めない。

## Scope of change

- `skills/ba0918-review/SKILL.md` と `skills/ba0918-review/references/finding-schema.md`
- `skills/ba0918-review/references/oracle-evidence.md`（新設）
- `skills/ba0918-cycle/SKILL.md`
- `skills/ba0918-implement/SKILL.md`、`skills/ba0918-implement/references/completion.md`
- `skills/ba0918-plan/SKILL.md`、`skills/ba0918-plan/references/step-template.md`
- `skills/ba0918-brainstorm/SKILL.md`
- `CHANGELOG.md`、`ROADMAP.md`、`regression-lock.json`

この外は変えない。
とくに `docs/spec/*.md` と `CONTEXT.md` は触らない。
`skills/ba0918-iterate/`、`skills/ba0918-investigate/`、`skills/ba0918-using-workflow/`、`evals/` も触らない。
iterate は cycle の本文を名前で読むので、cycle を変えれば追従し、本文を直す必要は無い。

## Step order and prerequisites

Step 1 → Step 2 の順は固定（Step 2 が Step 1 の節名とファイル名を指す）。
Step 3、4、5 は Step 1 の後なら順不同。
Step 6 は Step 1、4、5 の後で、agentic-rules のリリースを待つ。
Step 7 は Step 1〜5 の後で、Step 6 が済んでいればその後。
Step 6 がリリース待ちで差し戻されたときは、Step 7 を Step 1〜5 の分だけ済ませて終端へ進む。
リリースが出た後の「さらに回す」で Step 6 と Step 7 をやり直す。
それまでの間、cycle・plan・brainstorm の本文はまだ無い写しを見出し語で指した状態になる。

## Verification map

- 仕様書「確かめ方が証拠として数えられる条件」→ Step 6（写し）と、Step 1・4・5（条件を使う指示）
- 仕様書「review」の「別の文脈で行う」「profile と観点」「指摘 1 件の項目」「確かめ方を先に書く」→ Step 1
- 仕様書「cycle」の「判断は cycle が持つ」「終わり方」「再開」「受け渡し」→ Step 2
- 仕様書「implement」の「コミット」→ Step 3
- 仕様書「plan」の「手順書の形」→ Step 4
- 仕様書「brainstorm」の「用語とシナリオを質問にする」「仕様書に書く前の見直し」→ Step 5
- 仕様書 冒頭の行数上限の扱い → Step 1〜6 の Done when と、cycle の review の判定
- 仕様書「根拠」→ 本文に写さない（実行者がその場で要る指示ではない）

## Left to the implementer（手順書全体）

- 英語の言い回しと行の詰め方。既存の文を詰めて吸収するか、行を足すか
- CHANGELOG・ROADMAP の文面（内容は仕様書の該当節に従う）
- 写しに添える出典 1 行の書式（仕様書「委任」）

## Stop conditions（手順書全体）

理念の 4 条件に加えて、仕様書に無い振る舞いを本文へ足したくなったら止めて返す。
仕様書の日本語と正本の英語で条件の意味が食い違っていると分かったら、本文を書かずに止めて返す（仕様書「確かめ方が証拠として数えられる条件」の末尾）。

## Test command

`bunx skills-ref@0.1.5 validate skills/ba0918-<name>` で形式を検査する。
行数は `awk 'END{print NR}' <file>` で数える。
skill 本文は `docs/` の外なので textlint の対象外である。
CHANGELOG の `Unreleased` の中身は `awk '/## \[Unreleased\]/,/## \[0.3.0\]/' CHANGELOG.md` で切り出す。
regression-lock の script は、このリポジトリではなく skill-regression skill の側にある。
パスは `~/.claude/skills/ba0918-skill-regression/scripts/lock.py` で、`python3 <そのパス> --check .` で状態を見る。
実走せずに取り直すときは `python3 <そのパス> --update <skill 名> --accept --note "<1 行>" .` を使う。
`--accept` を付けずに `--update` すると「実走して通った」と記録されるので、付け忘れは反例である。

## Step 1 — review skill

Purpose: reviewer に課す規則を、両方向の突き合わせと新しい確かめ方の門を含む形にし、呼ぶ側が貼る物を節で指せるようにする。
Specification: `docs/spec/workflow.md#別の文脈で行う`、`#profile と観点`、`#指摘 1 件の項目`、`#確かめ方を先に書く`、`#確かめ方が証拠として数えられる条件`。
Prerequisites: 無し。
May change: `skills/ba0918-review/SKILL.md` と `skills/ba0918-review/references/finding-schema.md`。
`CHANGELOG.md`。
Done when: 本文が上の 4 節の規則を全部写している。
とくに「reviewer に課す規則」は、仕様書「別の文脈で行う」が挙げる 3 つを指していて、1 つも欠けていない。
3 つとは、指摘 1 件の項目と確かめ方を先に書く節と、両方向の突き合わせの段落である。
条件は、Step 6 で置く `references/oracle-evidence.md` の見出し `Evidence conditions` で指し、この step では英語の写しを置かない。
条件 3 と 4 が参照する規範の読み替え（仕様書が無ければ利用者向けの公開文書、動作環境はその規範の宣言）は、review が単独で呼ばれても効くよう本文に書く。
finding-schema の severity の行に、欠陥を述べない指摘は cycle が `warn` に直す旨がある。
CHANGELOG の `Unreleased` に review の **BREAKING** の項目がある。
validate が通る。
この step で増えた行は、実行者がその場で要る指示だけで、仕様書の上の節に辿れる。
Shown by: artifact — `skills/ba0918-review/SKILL.md` と `references/finding-schema.md`。
形式の検査は `bunx skills-ref@0.1.5 validate skills/ba0918-review`。
行数は `awk 'END{print NR}' skills/ba0918-review/SKILL.md skills/ba0918-review/references/*.md` で控える。
CHANGELOG は `Unreleased` を切り出して `rg 'ba0918-review'` が 1 行以上を返す。
Left to the implementer: 「reviewer に課す規則」を 1 つの節にまとめるか、既存の節を名指しするか。
Stop and hand back if: 無し。

## Step 2 — cycle skill

Purpose: cycle が対応の最終決定を機械的に検査し、指摘が減らずに入れ替わる状態で止まり、reviewer と修正役に貼る物を揃える。
Specification: `docs/spec/workflow.md#判断は cycle が持つ`、`#終わり方`、`#再開`、`#受け渡し`、`#終端報告`。
Prerequisites: Step 1。
May change: `skills/ba0918-cycle/SKILL.md`、`CHANGELOG.md`。
Done when: 本文が上の 5 節の規則を全部写している。
とくに次の 4 つがある。
対応の最終決定の検査の順（`info`、欠陥を述べない指摘、欠陥を述べる指摘の新規テスト要求、`security`）。
終わり方 3 の新しい条件と、その数え方（差分レビューだけ、最終決定の後の数）、再開でのリセットと「さらに回す」での継続。
修正役に貼る物。
それは implement の契約と `skills/ba0918-review/references/oracle-evidence.md` の第 1 段落である。
失敗するテストも条件を満たす物だけ書くことと、削除の指摘の完了の証拠も貼る。
終端報告に、仕様書に無い規則や節を「仕様書に無い」として挙げること。
review には Step 1 の「reviewer に課す規則」を貼る。
最初のレビューの前に読む review skill のファイルの一覧に `references/oracle-evidence.md` が入っている。
Step 6 の前はそのファイルがまだ無いが、本文はファイル名で指すにとどめ、cycle の本文へ英語を写さない。
CHANGELOG の `Unreleased` に cycle の **BREAKING** の項目がある。
validate が通る。
この step で増えた行は、実行者がその場で要る指示だけで、仕様書の上の節に辿れる。
Shown by: artifact — `skills/ba0918-cycle/SKILL.md`。
形式の検査は `bunx skills-ref@0.1.5 validate skills/ba0918-cycle`。
行数は `awk 'END{print NR}' skills/ba0918-cycle/SKILL.md` で控える。
CHANGELOG は `Unreleased` を切り出して `rg 'ba0918-cycle'` が 1 行以上を返す。
Left to the implementer: 既存の「Judgment stays here」と「Endings」のどこに差し込むか。
Stop and hand back if: 無し。

## Step 3 — implement skill

Purpose: 検証の検証を勝手に作らないことと、削除の指摘の完了の示し方を実装者の契約に入れる。
Specification: `docs/spec/workflow.md#コミット`（implement の節）。
Prerequisites: Step 1。
May change: `skills/ba0918-implement/SKILL.md` と `skills/ba0918-implement/references/completion.md`。
`CHANGELOG.md`。
Done when: 本文が上の節の 2 つの規則（検証の検証を作らない、削除の指摘の完了の証拠）を写している。
CHANGELOG の `Unreleased` に implement の **BREAKING** の項目がある。
validate が通る。
この step で増えた行は、実行者がその場で要る指示だけで、仕様書の上の節に辿れる。
Shown by: artifact — `skills/ba0918-implement/SKILL.md` と `references/completion.md`。
形式の検査は `bunx skills-ref@0.1.5 validate skills/ba0918-implement`。
行数は `awk 'END{print NR}' skills/ba0918-implement/SKILL.md` で控える。
同じコマンドを `references/completion.md` にも当てる。
CHANGELOG は `Unreleased` を切り出して `rg 'ba0918-implement'` が 1 行以上を返す。
Left to the implementer: SKILL.md と completion.md のどちらに置くか。
Stop and hand back if: 無し。

## Step 4 — plan skill

Purpose: 手順書が名指しするテストを条件で絞り、条項ごとのテストと成立済みへのテストを禁じる。
Specification: `docs/spec/workflow.md#手順書の形`（plan の節）、`#確かめ方が証拠として数えられる条件`。
Prerequisites: Step 1。
May change: `skills/ba0918-plan/SKILL.md`、`skills/ba0918-plan/references/step-template.md`、`CHANGELOG.md`。
Done when: step-template の Shown by の説明が、仕様書「手順書の形」の示し方の規則を全部写している。
規則とは、名指しするテストの条件、成立済みへのテスト、条件の数との対応、brainstorm へ返す場合である。
条件は、Step 6 で同じファイルの末尾に置く見出し `Evidence conditions` で指し、この step では英語の写しを置かない。
CHANGELOG の `Unreleased` に plan の **BREAKING** の項目がある。
validate が通る。
この step で増えた行は、実行者がその場で要る指示だけで、仕様書の上の節に辿れる。
Shown by: artifact — `skills/ba0918-plan/SKILL.md` と `references/step-template.md`。
形式の検査は `bunx skills-ref@0.1.5 validate skills/ba0918-plan`。
行数は `awk 'END{print NR}' skills/ba0918-plan/SKILL.md skills/ba0918-plan/references/*.md` で控える。
CHANGELOG は `Unreleased` を切り出して `rg 'ba0918-plan'` が 1 行以上を返す。
Left to the implementer: 文言。
Stop and hand back if: 無し。

## Step 5 — brainstorm skill

Purpose: 本体に関係ない要件の扱いをラウンドで問い、要求ごとに確かめ方が条件を満たすかを見る。
Specification: `docs/spec/workflow.md#用語とシナリオを質問にする`、`#仕様書に書く前の見直し`。
Prerequisites: Step 1。
May change: `skills/ba0918-brainstorm/SKILL.md`、`CHANGELOG.md`。
Done when: 本文が上の 2 節の新しい規則（本体に関係ない要件の質問、要求ごとの確かめ方の判定と処遇、落とした要求の却下の記録）を写している。
条件は、Step 6 で「Writing the specification」の節に置く見出し `Evidence conditions` で指し、この step では英語の写しを置かない。
CHANGELOG の `Unreleased` に brainstorm の **BREAKING** の項目がある。
validate が通る。
この step で増えた行は、実行者がその場で要る指示だけで、仕様書の上の節に辿れる。
Shown by: artifact — `skills/ba0918-brainstorm/SKILL.md`。
形式の検査は `bunx skills-ref@0.1.5 validate skills/ba0918-brainstorm`。
行数は `awk 'END{print NR}' skills/ba0918-brainstorm/SKILL.md` で控える。
同じコマンドを `references/records.md` にも当てる。
CHANGELOG は `Unreleased` を切り出して `rg 'ba0918-brainstorm'` が 1 行以上を返す。
Left to the implementer: 文言と、2 つの規則を置く節。
Stop and hand back if: 無し。

## Step 6 — 正本の写し

Purpose: 条件の英語 2 段落を review・plan・brainstorm の skill に写し、出典の 1 行を添える。
Specification: `docs/spec/workflow.md#確かめ方が証拠として数えられる条件`、`#受け渡し`。
Prerequisites: Step 1、4、5。
agentic-rules のリリースが出ていて、そのリリースの `contracts/oracle-evidence.md` が `~/develop/agentic-rules` で読めること。
リリースとは、その `contracts/oracle-evidence.md` を含む commit に付いた tag である。
`git -C ~/develop/agentic-rules describe --tags --exact-match HEAD` が tag 名を返せばリリースがあり、返さなければ無い。
出典の 1 行に添える版は、その tag 名から取る。
May change: `skills/ba0918-review/references/oracle-evidence.md`（新設）。
`skills/ba0918-plan/references/step-template.md`。
`skills/ba0918-brainstorm/SKILL.md` と `CHANGELOG.md`。
Done when: 3 つの置き場（Approach の段落のとおり）のそれぞれに、見出し `Evidence conditions` がある。
その下に正本の 2 段落が一字一句同じ形である。
その直後に、規則名 `ba0918-verification` と写した時点の agentic-rules のリリース版を含む 1 行がある。
写しの前後に背景説明を付けない。
仕様書の 4 条件の日本語と正本の英語の意味が一致している。
CHANGELOG の `Unreleased` の review・plan・brainstorm の項目に、写しを持つことが書かれている。
validate が通る。
この step で増えた行は、写しと出典の 1 行と見出しだけである。
Shown by: artifact — 上の 3 ファイル。
形式の検査は 3 skill それぞれの `bunx skills-ref@0.1.5 validate`。
一致の検査は次のコマンドで、`True` を返す。

```sh
python3 -c 'import sys; src=open(sys.argv[1]).read(); body=src[src.index("An oracle"):].strip(); print(all(body in open(f).read() for f in sys.argv[2:]))' \
  ~/develop/agentic-rules/contracts/oracle-evidence.md \
  skills/ba0918-review/references/oracle-evidence.md \
  skills/ba0918-plan/references/step-template.md \
  skills/ba0918-brainstorm/SKILL.md
```

`rg -l 'ba0918-verification' skills/` が review、plan、brainstorm の 3 skill のファイルだけを返す。
Left to the implementer: 出典 1 行の書式（仕様書「委任」）。
Stop and hand back if: agentic-rules のリリースが無い、または正本の本文が仕様書の 4 条件の日本語と意味が違う。
意味が違うとは、条件の数が違うこと、あるいは禁止の範囲（足さない・残さない・要求しない）が違うことである。
例や言い回しが足されているだけなら意味は同じで、返さない。
どちらも本文を書かずに理由を添えて返す。

## Step 7 — ROADMAP と regression-lock

Purpose: 済んだ作業を ROADMAP に控え、本文を変えた skill の lock を取り直す。
Specification: 無し。この step は仕様書の要求ではなく、`PROJECT.md`「検査」と、regression-lock が本文の変更ごとに取り直しを求める約束に基づく。
Prerequisites: Step 1〜5。Step 6 が済んでいればその後。
May change: `ROADMAP.md`、`regression-lock.json`。
Done when: ROADMAP の「済み」に、この改訂の要点と日付（2026-09-02 以降）がある。
要点とは、条件、cycle の検査と終わり方、両方向の突き合わせ、写しと版である。
Step 6 が差し戻しで済んでいないときは、写しが未了であることも書く。
本文を変えた 5 skill と、cycle を名前で読む iterate の lock を、Test command の `--accept` 付きの呼び出しで取り直す。
`--note` には、実走していないことと、scenario がこの改訂で変えた規則に触れないことを 1 行で書く。
`--check` が、この手順書で触った skill について stale を報告しない。
`ba0918-using-workflow` の `unverified` は着手前からあり、この手順書の範囲外なので残ってよい。
Shown by: check — 次の 2 つを走らせる。
`python3 ~/.claude/skills/ba0918-skill-regression/scripts/lock.py --check .` の出力に、触った 6 skill の行が無い。
`rg -n '2026-09-0[2-9]|2026-09-[1-3][0-9]' ROADMAP.md` が済みの行を返す。
Left to the implementer: ROADMAP の文面と `--note` の文面。
Stop and hand back if: `--check` が `contract-change` を報告し、その理由をこの手順書の変更で説明できないとき。

## Out of scope

- scenario の追加や実走
- iterate・investigate・using-workflow の本文の変更
- `ba0918-using-workflow` の lock の `unverified` の解消
- リリース（版の bump、tag）。`/release` で別に行う
- 仕様書と用語集の変更
