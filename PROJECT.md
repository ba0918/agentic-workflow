# agentic-workflow

開発を進めるための 5 つの skill（brainstorm、plan、cycle、implement、review）を配る skill 集。
フレームワークではない。
`skills/ba0918-*/` を `~/.claude/skills/` に置くだけで動き、実行環境や状態ストアや script を持たない。

## 正本

| 文書 | 役目 |
|---|---|
| `docs/principles.md` | 利用者が自分の言葉で書いた理念。最上位 |
| `docs/spec/workflow.md` | 5 つの skill の約束を人向けに書いた仕様書。skill 本文はこれを写した物 |
| `CONTEXT.md` | 用語集。二通りに読める言葉の定義と、使わない言い換え |
| `skills/ba0918-<name>/` | skill 本文（`SKILL.md`）と参照資料（`references/`）。LLM 向けの英語 |

食い違ったら、理念 > 仕様書 > skill 本文の順に従う。

## 縛り

- 5 つの責務を越える物は、実利用で必要だった実績が無ければ持たない
- 記録するのは git に痕跡が残らない情報だけ。進捗は git log から読む。編集ロックを作らない
- skill 本文と参照資料は減る方向が基本。行数の上限は仕様書の冒頭にある
- skill 本文から仕様書や他の文書をパスで参照しない（出力先と実行時の入力は例外）
- commit メッセージに工程名や指摘の ID を書かない

## 検査

- `bun install` のあと `bun run lint:docs`（`docs/` の Markdown に textlint）。pre-commit（lefthook）と Claude Code の Stop hook からも同じ物を呼ぶ
- `bunx skills-ref validate skills/ba0918-<name>` で skill の形式を検査する
- `.textlintrc.json` の `preferInBody` は「である」。`CONTEXT.md` は定義行に句点を付けない形式なので `.textlintignore` で外している

## 置き場

人が承認した文書は `docs/`、LLM が書いた記録は `.agents/`（git 管理外）。
`docs/plans/` にある手順書が、進行中の作業を表す。
