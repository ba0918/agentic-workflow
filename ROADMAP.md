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
- investigate の scenario 2 本（iv-001、iv-002）を opencode で実走して lock に登録した（2026-08-31）。両方 pass。これで scenario を持つ 7 skill 全部に検証の記録がある
- 配布経路の実地確認を済ませた（2026-08-31）。Claude Code plugin（`ba0918-workflow:` 付きで 7 本）、Codex CLI plugin（同じ）、OpenCode plugin（git から取って `skills/` を読む）、APM、コピー（`gh skill` / `npx skills`）のどれも、v0.1.0 の 7 skill が置かれ、セッションで名前が列挙されるか本文が読めるところまで確かめた。1 回の手動確認で足りると判断し、自動化はしない。`gh skill install` は `--all` が無いと端末無しでは何も入れないので README を直した
- 名前で呼ぶ skill 同士の依存（iterate → cycle → review）を skill-regression が辿れるようにした（2026-08-31）。agentic-meta 側が `evals/dependencies.yml` の宣言を surface に 1 ホップ合流させる形で対応し、こちらは宣言を置き、scenario の `exercises` に依存先の本文を足し、lock を取り直した。cycle の本文を変えると iterate の scenario が影響ありに挙がる
- iterate と investigate の仕様書の残件 7 件を壁打ちで決めて改訂した（2026-09-01）。上限の数え方を仕様書へ、判定役の列挙にテストが無いときの iterate の補完を明文化、実装役への差し戻し文から裸の条件番号を除去、推奨表の brainstorm 行を中くらい以上に限定して iterate と排他に、修正案は問題ごとに 1〜3 案、委譲先へ写す読むだけの保証にテストの条件を含め、scenario の応答テキスト判定は実測で問題無しとして受け入れ

## 次

- using-workflow の dogfood。main 取り込み後に、このリポジトリの `AGENTS.md` へポインタ行（`## 重要` の下に「最初に `ba0918-using-workflow` を必ず読み込むこと」）を足す。その後の session 群で skill の読み込み率を測るかは、そのとき決める。測るなら、設置後の session ログのうち ba0918-using-workflow の本文を読み込んだ session の割合を数え、設置前の実測（AGENTS.md の「Always」行に挙がる 4 skill の読み込みが 31 本中 0〜9 本、2026-09-01）と比べる

## 検討中

- ドメインモデルの抽出を brainstorm から別 skill（domain-model）に切り出す。形まで決めて見送った（2026-09-01）。入口は人の明示起動と brainstorm からの名指し呼び出しの 2 つ。description による自動発動は、発言が用語集と矛盾したかを skill 発動前に評価できないため成立せず、狙わない。常駐の見張りも対話を止めるので足さない。用語集だけが変わるときは対話の回答を承認とみなして skill が CONTEXT.md だけを即 commit し、意味が変わった用語は docs/ を横断検索して波及を報告、仕様書に波及したら brainstorm 改訂へ案内する。動かす条件は、brainstorm の外で用語を直したい実例が起きたとき
- 文書の建付けを、仕様書単位からドメインモデルに紐づく要件・仕様に替える。用語の変更で仕様書への波及を探す作業が、検索で追いつかなくなったら
- `CONTEXT.md` をドメインモデルごとに分割する。用語が増えて 1 ファイルで読みにくくなったら
- GitHub の tag 保護（Settings > Rules の ruleset）。「公開した tag は動かさない」を GitHub 側でも縛るなら
- setup-workflow。using-workflow の常駐の設置を対話式で行う skill。常駐の 3 方式（ポインタ行、インライン展開、hook）から選ばせ、推奨はポインタ行。動かす条件は、設置や案内が繰り返し面倒だった、または設置で事故った実例が出たとき
- 入口の規則の表（`docs/spec/using-workflow.md`）と investigate の「推奨する次の行動」の表の整合の機械化。案は、行を名前参照にして片方だけが正本を持つ名前参照化と、表を共有文書にして vendor で両方へ配ること（agentic-skill-vendor）の 2 つ。動かす条件は、表を参照する skill が 3 つ以上になったとき、または手動の整合で食い違いの事故が起きたとき
