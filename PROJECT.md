# agentic-workflow

開発を進めるための skill（`skills/ba0918-*/`）を配る skill 集。
フレームワークではない。
`skills/ba0918-*/` を `~/.claude/skills/` に置くだけで動き、実行環境や状態ストアや script を持たない。

## 正本

| 文書 | 役目 |
|---|---|
| `docs/principles.md` | 利用者が自分の言葉で書いた理念。最上位 |
| `docs/spec/workflow.md` | 開発ワークフローの約束を人向けに書いた仕様書。ワークフローの skill 本文はこれを写した物 |
| `docs/spec/investigate.md` | 調査 skill（investigate）の約束を人向けに書いた仕様書。review の description に足した起動語（検証、動作確認、実装確認）の根拠もこの文書 |
| `docs/spec/iterate.md` | 小さいタスク skill（iterate）の約束を人向けに書いた仕様書。仕様書も手順書も要らない小さいタスクを review 付きで回す入口で、cycle の本文を読み替えて使う |
| `CONTEXT.md` | 用語集。二通りに読める言葉の定義と、使わない言い換え |
| `skills/ba0918-<name>/` | skill 本文（`SKILL.md`）と参照資料（`references/`）。LLM 向けの英語 |

食い違ったら、理念 > 仕様書 > skill 本文の順に従う。

## 縛り

- skill の責務を越える物は、実利用で必要だった実績が無ければ持たない
- 記録するのは git に痕跡が残らない情報だけ。進捗は git log から読む。編集ロックを作らない
- skill 本文と参照資料は減る方向が基本。行数の上限は各仕様書の冒頭にある
- skill 本文から仕様書や他の文書をパスで参照しない（出力先と実行時の入力は例外）
- commit メッセージに工程名や指摘の ID を書かない

## 検査

- `bun install` のあと `bun run lint:docs`（`docs/` の Markdown に textlint）。pre-commit（lefthook）と Claude Code の Stop hook からも同じ物を呼ぶ
- `bunx skills-ref@0.1.5 validate skills/ba0918-<name>` で skill の形式を検査する
- CI（`.github/workflows/ci.yml`）は push と pull request のたびに同じ検査を走らせ、加えて版の宣言 3 つの一致を検査する
- `.textlintrc.json` の `preferInBody` は「である」。`CONTEXT.md` は定義行に句点を付けない形式なので `.textlintignore` で外している

## 配布と版

- 配る物は `skills/` の中身だけ。配布経路（Claude Code、Codex CLI、OpenCode、APM、`gh skill` / `npx skills`）と入れ方は `README.md` にある
- 版の正本は `.claude-plugin/plugin.json` の `version`。`.claude-plugin/marketplace.json` の `plugins[0].version` と `package.json` の `version` はそれに従う写しで、CI が一致を検査する
- 利用者から見える変更（skill の指示が変わる、skill が増える、入れ方が変わる）は `CHANGELOG.md` の `Unreleased` に、その変更を入れる commit で書く。skill の指示の意味が変わる変更は **BREAKING** を付けて分ける
- 公開は `/release`（`.claude/commands/release.md`）で行う。版を決め、`Unreleased` を版の見出しに昇格し、検査を通し、人の承認の後に commit して `main` に push する。tag は手元で打たない
- release workflow（`.github/workflows/release.yml`）は `main` への push で動く。`CHANGELOG.md` に版の見出しがある commit だけを公開対象と判定する。CI の検査を通した後でその commit に tag を打ち、見出しの節をそのまま release note にした GitHub release を作る
- 公開した tag は動かさない。公開後の直しは次の版で出す

## 置き場

人が承認した文書は `docs/`、LLM が書いた記録は `.agents/`（git 管理外）。
`docs/plans/` にある手順書が、進行中の作業を表す。

## 開発中の skill の読ませ方

このリポジトリで作業するときは、`.claude/skills/` にある symlink（`skills/ba0918-*` を向く）で開発中の skill を読む。
同じ名前の skill を `~/.claude/skills/` に置かない。Claude Code は個人スコープをプロジェクトスコープより優先するので、置くと開発版が読まれなくなる。
他のプロジェクトで使うときは、そのプロジェクトで `apm install ba0918/agentic-workflow` を打って配布版を入れる。
