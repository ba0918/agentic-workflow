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
- 開発中の skill の読ませ方を、`~/.claude/skills/` の symlink からリポジトリ内 `.claude/skills/` の symlink に替えた（2026-08-31）。他のプロジェクトは APM で配布版を入れる。`~/.claude/skills/` に同名があると個人スコープが勝つので、そちらは外す
- cycle と review の収束規則を改めた（2026-08-31）。フルレビューに既知の指摘だけを見せる、意味が変わらない言い換えは指摘にしない、フルレビューは 2 回目で最後、再開の規則（往復番号、連続のリセット、「さらに回す」の再入口）。iterate の cycle 待ちの未決定も閉じた。skill 本文は実走なしで lock を取り直したので、次に cycle を回したとき収束の変化を見る

## 次

- 無し。検討中から選ぶ

## 検討中

- ドメインモデルの抽出（用語の定義と境界のシナリオ）を brainstorm から別 skill に切り出す。まずは brainstorm 組み込みで運用し、実利用で分けたくなったら分ける
- `CONTEXT.md` をドメインモデルごとに分割する。用語が増えて 1 ファイルで読みにくくなったら
- iterate 仕様書の残件。往復の上限が今回の実行の review の回数を数える約束は skill 本文にだけある。判定役がテストを列挙に入れないとき、iterate が決定権で補う動き（実走で 1 回起きた）を明示するかどうか。実装役の委譲行の裸の条件番号。次に仕様書を触るときに拾う。指摘の記録は `.agents/artifacts/reviews/feat/iterate.json`
- skill-regression の lock が名前で呼ぶ skill 同士の依存（iterate → cycle → review）を辿れない。cycle の本文が変わっても iterate の scenario が影響ありに挙がらない
- investigate 仕様書の残件。scenario を応答テキストで判定する点。委譲先へ写す 5 つがテストの条件を含むかどうか。「1〜3 案」の単位（問題ごとか、5 節全体か）。推奨表の「小さいタスク → iterate」と「仕様書が無い → brainstorm」が同じ状況（仕様書の無い小さいタスク）で重なる件。次に仕様書を触るときに拾う
- investigate の scenario 2 本の実走と lock への登録。人が頼んだときだけ
- 配布経路の実地確認。APM は `apm install ba0918/agentic-workflow` で v0.1.0 の 7 skill が `.claude/skills/` に置かれるところまで確かめた。セッションで読まれるか、Claude Code / Codex CLI / OpenCode / コピーの各経路は、まだ試していない
- GitHub の tag 保護（Settings > Rules の ruleset）。「公開した tag は動かさない」を GitHub 側でも縛るなら
