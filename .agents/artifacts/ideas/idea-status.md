# Idea Status

**Last Updated:** 2026-08-26 03:12:00

| Idea | Tags | Created | Status | Summary |
|------|------|---------|--------|---------|
| [幹の減量 — 機械検証を外の世界だけに絞り、実装を委譲して往復を自走させる](20260826011349_trunk-slimming-and-fix-loop.md) | `workflow,redesign,over-engineering,fix-loop,delegation,evidence,station-boundary` | 2026-08-26 01:13:49 | ✅ Converged | 移植は続けるが、機械検証を外の世界を見る11コード15箇所に絞り、自己検証の29コードを落とす（execution_model.pyは995行→156行）。手順書は仕様書を再記述せず参照する。実装はsubagentへ委譲してメインの文脈を守り、実装→レビュー→修正の往復はcycleが止めずに回す。工程は9駅の構想から5つのskillに収束。 |
| [Cycleのtest結果証拠を取得可能性で扱う](20260822194546_cycle-test-evidence-availability.md) | `cycle,evidence,test-summary,human-gate` | 2026-08-22 19:45:46 | ✅ Converged | test件数は構造化取得できた場合だけ保存し、取得不能時は理由を明示する。Plan作成指示にはHuman gate宣言形式を追加する。 |
| [Brainstorm移行の要件と前回失敗の再発防止](20260821212118_brainstorm-migration-recurrence-prevention.md) | `brainstorm,migration,workflow,recovery,regression` | 2026-08-21 21:21:18 | ✅ Converged | 移行の最初の対象をbrainstormに限定する。広い依頼を独立した利用者価値へ分割し、 意味状態を途中保存してcompact後も復元できるようにする。利用者の言語による仕様集合と plan readinessを整え、未合意の設計をplanへ持ち込ませない。CodexとClaudeで回帰scenarioを 実行し、品質を維持した完了brainstorm一件あたりの費用を測定する。 |
