# ROADMAP

## 済み

- 仕様書 1 本（`docs/spec/workflow.md`）、理念（`docs/principles.md`）、用語集（`CONTEXT.md`）
- skill 5 つ（`skills/ba0918-*/`）。Claude の reviewer 2 体と Codex による敵対レビューを 2 往復
- textlint の直呼び（lefthook の pre-commit と Claude Code の Stop hook）。実地試験で文章の指摘 27 件を弾いたので残す

## 次

1. 受け入れ試験。書き直した skill で実務の cycle を 1 回完走する（brainstorm → plan → cycle → 人の確認）
2. 旧リポジトリ側の掃除。Python runtime、旧仕様 8 本、旧 skill、evals を消し、`~/.claude/skills/` の symlink を新しい実体に貼り直す

## 検討中

- ドメインモデルの抽出（用語の定義と境界のシナリオ）を brainstorm から別 skill に切り出す。まずは brainstorm 組み込みで運用し、実利用で分けたくなったら分ける
- `CONTEXT.md` をドメインモデルごとに分割する。用語が増えて 1 ファイルで読みにくくなったら
- レビューの往復が収束しない実例を見てから、進捗なしの判定条件を見直す
