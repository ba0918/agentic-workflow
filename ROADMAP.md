# ROADMAP

## 済み

- 仕様書（`docs/spec/`）、理念（`docs/principles.md`）、用語集（`CONTEXT.md`）
- 開発ワークフローの skill（`skills/ba0918-*/`）。Claude の reviewer 2 体と Codex による敵対レビューを 2 往復
- textlint の直呼び（lefthook の pre-commit と Claude Code の Stop hook）。実地試験で文章の指摘 27 件を弾いたので残す
- 回帰評価の配線（`evals/`、`regression-lock.json`、opencode の economy ルート）。scenario 9 本が pass
- 受け入れ試験。investigate skill を brainstorm → plan → cycle で 1 周して取り込んだ。往復 12 回、仕様書の改訂 3 回、security の停止 1 回
- 旧リポジトリの掃除。Python runtime、旧仕様 8 本、旧 skill、evals を消し、作り直した履歴を `main` に繋いだ。`~/.claude/skills/` の symlink は `skills/ba0918-*` の 6 本を向く
- 受け入れ試験の 2 本目。iterate skill を brainstorm → plan → cycle で 1 周して取り込んだ。往復 16 回、仕様書の改訂 1 回（19 問）、指摘 79 件のうち 40 件を閉じた。scenario 2 本を opencode で実走して lock に登録（合計 11 本）
- 配布の配線を足した。plugin manifest、OpenCode plugin、`README.md` の入れ方（APM とコピー経路も）、`CHANGELOG.md`、CI である。公開は `/release` で行う。`main` への push を受けた release workflow が tag と GitHub release を作る
- v0.1.0 を公開した（2026-08-31）。7 つの skill を初めて配布した版で、`/release` → CI → tag → GitHub release の流れを実機で 1 周した。CI の bun を lock を書いた 1.4 系に揃える直しが 1 回入った

## 次

1. cycle と review の仕様改訂（brainstorm）。iterate の受け入れ試験で、文章を対象にしたフルレビューが収束しなかった（2 回とも新規を返し、大半は受け入れ済みの再発見と圧縮で生まれた文言差）。題材は 4 つ。受け入れ済みの指摘を reviewer に渡す。意味が変わらない表現差を指摘にしない。フルレビューは差分ループの後 1 回で打ち切る。再開規則の空白（往復番号の続け方、「さらに回す」の後の連続、再入口が仕様書と skill 本文で割れている件）を埋める

## 検討中

- ドメインモデルの抽出（用語の定義と境界のシナリオ）を brainstorm から別 skill に切り出す。まずは brainstorm 組み込みで運用し、実利用で分けたくなったら分ける
- `CONTEXT.md` をドメインモデルごとに分割する。用語が増えて 1 ファイルで読みにくくなったら
- iterate 仕様書の残件。往復の上限が今回の実行の review の回数を数える約束は skill 本文にだけある。判定役がテストを列挙に入れないとき、iterate が決定権で補う動き（実走で 1 回起きた）を明示するかどうか。実装役の委譲行の裸の条件番号。次に仕様書を触るときに拾う。指摘の記録は `.agents/artifacts/reviews/feat/iterate.json`
- skill-regression の lock が名前で呼ぶ skill 同士の依存（iterate → cycle → review）を辿れない。cycle の本文が変わっても iterate の scenario が影響ありに挙がらない
- investigate 仕様書の残件。scenario を応答テキストで判定する点。委譲先へ写す 5 つがテストの条件を含むかどうか。「1〜3 案」の単位（問題ごとか、5 節全体か）。推奨表の「小さいタスク → iterate」と「仕様書が無い → brainstorm」が同じ状況（仕様書の無い小さいタスク）で重なる件。次に仕様書を触るときに拾う
- investigate の scenario 2 本の実走と lock への登録。人が頼んだときだけ
- 配布経路の実地確認。Claude Code / Codex CLI / OpenCode / APM / コピーのどれも、v0.1.0 を実際に入れて skill が読まれるかはまだ試していない
- GitHub の tag 保護（Settings > Rules の ruleset）。「公開した tag は動かさない」を GitHub 側でも縛るなら
