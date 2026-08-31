# using-workflow 実装の手順書

## Goal

新しい依頼をどの skill から入れるかを決める skill（ba0918-using-workflow）を、配布物と文書ごと 1 ブランチで作る。

## Specification

`docs/spec/using-workflow.md`（コミット済み）。
この手順書は仕様書の節を参照し、本文を写さない。
実装者は各 step の前に、参照された節を必ず読む。

## Approach and why

skill 本体を最初に作り、それを参照する文書（PROJECT.md、README、plugin manifest、CHANGELOG、ROADMAP）を後から更新する。
文書は skill の存在と description の文言に依存するので、この順が手戻りを最小にする。
scenario は最後に書く。
実走はしない（仕様書「作る物」の末尾）。
ブランチと worktree は cycle が立てる。この手順書の step には含めない。

## Scope of change

- `skills/ba0918-using-workflow/SKILL.md`（新設）
- `.claude/skills/ba0918-using-workflow`（symlink 新設）
- `PROJECT.md`
- `README.md`
- `.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json`
- `CHANGELOG.md`
- `ROADMAP.md`
- `evals/cases/ba0918-using-workflow/` と `evals/inputs/ba0918-using-workflow/`（新設）

この外は変えない。
とくに `docs/spec/investigate.md`、既存 skill、`regression-lock.json`、`evals/dependencies.yml` は触らない（仕様書「作らない物」）。

## Step order and prerequisites

Step 1 が先で、Step 2 がその直後である。
Step 2 の CHANGELOG は、skill を足す変更と同じ commit に入れる（PROJECT.md の「その変更を入れる commit で書く」）。
Step 3〜5 は Step 2 の後なら順不同。Step 6 は Step 1 の後ならいつでもよい。

## Verification map

- 仕様書「責務」「入口の規則」→ Step 1（本文）と Step 6（scenario）
- 仕様書「例外」→ Step 1
- 仕様書「常駐と発火」→ Step 1（description と本文の書き方）と Step 4（README の節）
- 仕様書 冒頭（行数上限 60、SKILL.md 単体）→ Step 1
- 仕様書「作る物」→ Step 2〜6
- 仕様書「作らない物」のうち hook の同梱と `references/` → Step 1 の Done when で防ぐ。残りは全 step の May change の外に出ないことで防ぐ

## Left to the implementer（手順書全体）

- SKILL.md の英語の言い回しと行の詰め方
- README・CHANGELOG・ROADMAP の文面（内容は仕様書の該当節に従う）
- README 内の節の置き場所。導入文の skill の数え方の言い回し（8 本すべてが現れること）

## Stop conditions（手順書全体）

理念の 4 条件に加えて、仕様書に無い振る舞いを本文へ足したくなったら止めて返す。

## Test command

`bun run lint:docs`（`docs/` の textlint）と `bunx skills-ref@0.1.5 validate skills/ba0918-using-workflow`。
ルート直下の Markdown（README、CHANGELOG、ROADMAP、PROJECT.md）は textlint の対象外なので、Shown by の check で確かめる。

## Step 1 — skill 本体と開発用 symlink

Purpose: 配布物の本体である SKILL.md を作る。
Specification: `docs/spec/using-workflow.md#責務`、`#入口の規則`、`#例外`、`#常駐と発火`、冒頭の行数上限。
Prerequisites: 無し。
May change: `skills/ba0918-using-workflow/`、`.claude/skills/ba0918-using-workflow`。
Done when: SKILL.md が英語で、仕様書の 4 節の内容（入口の表と対象外の境界と例外と常駐前提の書き方）を写している。
ただし「例外」節の最終文（入口の規則へ行を足す維持の決まり）は、仕様書自身の定めにより本文へ写さない。
skill 本文から仕様書・用語集・他文書をパスで参照しない（PROJECT.md の縛り）。他 skill には skill 名で言及する。
frontmatter の description が明示起動の語を持つ。
`skills/ba0918-using-workflow/` の中身が SKILL.md の 1 ファイルだけで、hook と `references/` を置かない。
ファイル全体（frontmatter 込み）が 60 行以内で、validate が通る。
symlink が既存の 7 本と同じ相対形式で `skills/ba0918-using-workflow` を指す。
Shown by: check — 次の 4 つを走らせる。
`bunx skills-ref@0.1.5 validate skills/ba0918-using-workflow` が通る。
`awk 'END{print NR}' skills/ba0918-using-workflow/SKILL.md` が 60 以下を返す。
`ls skills/ba0918-using-workflow/` が SKILL.md だけを出す。
`ls -l .claude/skills/ba0918-using-workflow` が symlink を示す。
Left to the implementer: 英語の言い回し、表を表組みで書くか列挙で書くか。
Stop and hand back if: 仕様書の内容を写すと 60 行に収まらないとき。黙って削らず、黙って超えず、返す。

## Step 2 — CHANGELOG

Purpose: 次のリリースで利用者に届く変更を記録する。
Specification: `docs/spec/using-workflow.md#作る物`（entry の存在）、`#責務`（文面の元）。
Prerequisites: Step 1。skill を足す変更と同じ commit に入れる。
May change: `CHANGELOG.md`。
Done when: `Unreleased` の `Added` に、skill 名と、それが利用者に何をもたらすかを会話無しで読める 1 項目がある。
Shown by: check — `rg -n 'using-workflow' CHANGELOG.md`。
Left to the implementer: 文面。
Stop and hand back if: 無し。

## Step 3 — PROJECT.md の正本の表

Purpose: 仕様書を正本の表に登録する。
Specification: `docs/spec/using-workflow.md#作る物`。
Prerequisites: Step 2。
May change: `PROJECT.md`。
Done when: 正本の表に `docs/spec/using-workflow.md` の行があり、役目の説明が付いている。
Shown by: check — `rg -n 'using-workflow' PROJECT.md`。
Left to the implementer: 行の文面。
Stop and hand back if: 表の形式が変わっていて行を足すだけで済まないとき。

## Step 4 — README と plugin manifest

Purpose: 利用者向けの案内と配布メタデータを新しい skill を含む形にする。
Specification: `docs/spec/using-workflow.md#常駐と発火`、`#作る物`。
Prerequisites: Step 2。
May change: `README.md`、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`。
Done when: README に「常駐のさせ方」の節（英語）がある。
節は AGENTS.md へのポインタ行の英語の同等文を主として案内し、本文のインライン展開を代替として 1〜2 行で添えている。
skill の数え上げと Skills の表が 8 skill すべてを含む。表の skill 名は既存どおり `ba0918-` 付きで書く。
plugin.json の description と keywords、marketplace.json の description が新しい skill を含む。
manifest 内の表記は既存の慣行どおり接頭辞無し（`using-workflow`）とする。
Shown by: check — 次の 2 つを走らせる。
`rg -l 'using-workflow' README.md .claude-plugin/*.json` が 3 ファイルを返す。
`jq -r '.keywords[]' .claude-plugin/plugin.json` に `using-workflow` がある。
Left to the implementer: 節の位置と英語の文面。数え上げの言い回し。
Stop and hand back if: 無し。

## Step 5 — ROADMAP の 3 件

Purpose: 見送った判断と main 取り込み後の作業を、再開条件ごと控える。
Specification: `docs/spec/using-workflow.md#作る物`（ROADMAP の 3 項目）。
Prerequisites: Step 2。
May change: `ROADMAP.md`。
Done when: 検討中に setup-workflow の行（対話式であること、3 方式、推奨、再開条件）がある。
検討中に表の整合の機械化の行（2 案、動かす条件）がある。
「次」の節に dogfood の控えがある。
控えの中身は、main 取り込み後に `AGENTS.md` へポインタ行を足すことと、読み込み率の計測はやるかそのとき決めることの 2 つである。
Shown by: check — `rg -n 'setup-workflow|ポインタ行' ROADMAP.md` が両方の語で一致を返す。
Left to the implementer: 文面と、節の中での行の順序。
Stop and hand back if: 無し。

## Step 6 — scenario 2 本

Purpose: skill の約束を skill-regression の scenario に写す。
Specification: `docs/spec/using-workflow.md#作る物`（scenario の 2 観点）、`#責務`、`#入口の規則`。
Prerequisites: Step 1。
May change: `evals/cases/ba0918-using-workflow/`、`evals/inputs/ba0918-using-workflow/`。
Done when: 既存の scenario（`evals/cases/ba0918-iterate/it-001.yaml` など）と同じキー構成の YAML が 2 本ある。
1 本は、作る・変える依頼が表のとおりの入口に案内されることを expectations に持つ。
もう 1 本は、質問が対象外と判定されそのまま応えられることを expectations に持つ。
発火は prompt での skill 名の名指しとする（description 発火が成立しないことは仕様書の前提であり、scenario が測るのは判定の正しさである）。
メタ値は次のとおり: `source: spec:20260901`（実走記録ではなく仕様書由来）、`executor_tier: economy`、`isolation: worktree`。
入力の fixture は最小限で、`exercises` は新しい SKILL.md を指す。
Shown by: check — 次の 2 つを走らせる。
`ls evals/cases/ba0918-using-workflow/` が YAML を 2 本出す。
`rg -l '^expectations:' evals/cases/ba0918-using-workflow/*.yaml` が 2 本とも返す。
Left to the implementer: fixture の題材と id の付番。
Stop and hand back if: scenario の形式が既存 YAML の観察から一意に定まらないとき。

## Out of scope

- scenario の実走と `regression-lock.json` のエントリ
- `evals/dependencies.yml` の宣言。using-workflow は他 skill の本文を名前で読み込む指示を持たないため、宣言する依存が無い
- このリポジトリの `AGENTS.md` へのポインタ行の追加（main 取り込み後の作業として ROADMAP に控える）
- 読み込み率の計測と setup-workflow の実装
