# ROADMAP

## 済み

- 仕様書（`docs/spec/`）、理念（`docs/principles.md`）、用語集（`CONTEXT.md`）
- 開発ワークフローの skill（`skills/ba0918-*/`）。Claude の reviewer 2 体と Codex による敵対レビューを 2 往復
- textlint の直呼び（lefthook の pre-commit と Claude Code の Stop hook）。実地試験で文章の指摘 27 件を弾いたので残す
- 回帰評価の配線（`evals/`、`regression-lock.json`、opencode の economy ルート）。scenario 9 本が pass
- 受け入れ試験。investigate skill を brainstorm → plan → cycle で 1 周して取り込んだ。往復 12 回、仕様書の改訂 3 回、security の停止 1 回

## 次

1. 旧リポジトリ側の掃除。Python runtime、旧仕様 8 本、旧 skill、evals を消し、`~/.claude/skills/` の symlink を新しい実体に貼り直す
2. iterate skill（2 本目の題材）。cycle の終端報告との受け渡しを brainstorm で決める

## 検討中

- ドメインモデルの抽出（用語の定義と境界のシナリオ）を brainstorm から別 skill に切り出す。まずは brainstorm 組み込みで運用し、実利用で分けたくなったら分ける
- `CONTEXT.md` をドメインモデルごとに分割する。用語が増えて 1 ファイルで読みにくくなったら
- cycle のレビューの運用。investigate の受け入れ試験で、standard のフルレビューが 3 回続けて新しい見えている指摘を返した（往復 12）。強さ `light` を既定にするか、往復の上限を最初に付けるか、フルレビューを収束判定のときだけにするか
- investigate 仕様書の残件。scenario を応答テキストで判定する点、委譲先に写す 5 つにテストの条件が入るか、「1〜3 案」が問題ごとか 5 節全体か。次に仕様書を触るときに拾う
- investigate の scenario 2 本の実走と lock への登録。人が頼んだときだけ
