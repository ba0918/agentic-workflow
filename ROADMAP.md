# ROADMAP

## 済み

- 仕様書（`docs/spec/`）、理念（`docs/principles.md`）、用語集（`CONTEXT.md`）
- 開発ワークフローの skill（`skills/ba0918-*/`）。Claude の reviewer 2 体と Codex による敵対レビューを 2 往復
- textlint の直呼び（lefthook の pre-commit と Claude Code の Stop hook）。実地試験で文章の指摘 27 件を弾いたので残す
- 回帰評価の配線（`evals/`、`regression-lock.json`、opencode の economy ルート）。scenario 9 本が pass
- 受け入れ試験。investigate skill を brainstorm → plan → cycle で 1 周して取り込んだ。往復 12 回、仕様書の改訂 3 回、security の停止 1 回
- 旧リポジトリの掃除。Python runtime、旧仕様 8 本、旧 skill、evals を消し、作り直した履歴を `main` に繋いだ。`~/.claude/skills/` の symlink は `skills/ba0918-*` の 6 本を向く

## 次

1. iterate 仕様書の改訂（brainstorm）。cycle の受け入れ試験で出た 4 つの決めごとを潰す。差し戻し時の「さらに回す」の扱い、再開規則の拡張と往復番号、実装役への受け渡しの境界、scenario の期待と lock の依存の扱い
2. 改訂後、`feat/iterate` に残る軽い指摘 5 件を直して取り込む。指摘は worktree の `.agents/artifacts/reviews/feat/iterate.json`

## 検討中

- ドメインモデルの抽出（用語の定義と境界のシナリオ）を brainstorm から別 skill に切り出す。まずは brainstorm 組み込みで運用し、実利用で分けたくなったら分ける
- `CONTEXT.md` をドメインモデルごとに分割する。用語が増えて 1 ファイルで読みにくくなったら
- cycle のレビューの運用。investigate の受け入れ試験で、standard のフルレビューが 3 回続けて新しい見えている指摘を返した（往復 12）。強さ `light` を既定にするか、往復の上限を最初に付けるか、フルレビューを収束判定のときだけにするか
- investigate 仕様書の残件。scenario を応答テキストで判定する点、委譲先に写す 5 つにテストの条件が入るか、「1〜3 案」が問題ごとか 5 節全体か。次に仕様書を触るときに拾う
- investigate の scenario 2 本の実走と lock への登録。人が頼んだときだけ
