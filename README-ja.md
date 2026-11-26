# agentic-workflow

[English](README.md)

AI コーディングエージェント向けの開発ワークフローを、[Agent Skills](https://agentskills.io) の形式で配る skill 集である。

5 つの skill で 1 つのワークフローを作る。
エージェントは、人と仕様に合意するまで質問を重ねる。
人が仕様書を承認したら、実装、敵対的レビュー、修正を、仕様書の成功条件が確かめられて指摘が収束するまで繰り返す。
1 人の実装者が持てない量のときだけ先に手順書を作り、手順書は誰も承認しない。
人が結果を受け取るのは最後の 1 回だけである。

ワークフローの横に、さらに 3 つの skill がある。

- 仕様書が要らない、小さいタスクのための skill
- ファイルを変えずに調べる調査用の skill
- 新しい依頼をどの skill から始めるかを決める skill

各 skill は、自分が書いたファイルのパスを次の skill に渡す。
skill どうしをつなぐ物はそれだけで、実行環境、状態ストア、スクリプトはどれも持たない。

## skill の一覧

| skill | 役目 |
|---|---|
| `ba0918-brainstorm` | 推奨回答を添えた番号付きの質問をラウンドごとに人へ出し、依頼の理解が人と揃うまで続ける。揃ったら仕様書を書く |
| `ba0918-plan` | 1 人の実装者が持てない量だと cycle が判断したとき、承認された仕様書から Markdown の手順書を 1 つ作る。仕様書の内容は写さず節へのリンクで示し、手順ごとに完了の証拠と止める条件を書き、承認を取らずに作業ブランチへコミットする |
| `ba0918-cycle` | 小さなオーケストレータ。承認された仕様書と承認のコミットとブランチを受け取り、実装、レビュー、修正を別の文脈のエージェントに任せ、成功条件が確かめられて指摘が収束するまで繰り返す。報告の末尾に、先に見てほしい所を並べる |
| `ba0918-implement` | 仕様書の要求を実装する。手順書があればそれに従う。コードはテストを先に書き、関心事ごとに 1 コミットにする。承認済みの文書が決めていない判断は暫定の答えで進め、証拠の場所とその答えが覆る条件を報告する |
| `ba0918-review` | 差分や文書一式を敵対的にレビューする。レビュー役は別の文脈で動き、指摘を返すだけで編集はしない。人が直接呼んで、コードベースの診断に使うこともできる |
| `ba0918-iterate` | 小さいタスクの入口。依頼が小さいことを確かめ、仕様書なしで cycle のループを回す |
| `ba0918-investigate` | ファイルを変えずに症状や疑問を調べ、直接の原因、根本原因、影響範囲、直し方の選択肢を報告する |
| `ba0918-using-workflow` | 新しい依頼をどの skill から始めるかを決める。対象は、小さいタスク、中規模以上の変更、未実装の要求が残る承認済みの仕様書、原因の分からない不具合、ファイルを読まないと答えられない質問である。質問と雑談には、skill へ回さずそのまま答える。どの作業でも、人に聞いてよい問いを絞る |

skill 本文は英語で、エージェントが読むために書いてある。
本文の元になった仕様書、その上に立つ理念、用語集は日本語で、`docs/` と `CONTEXT.md` にある。
これらが食い違ったときは、理念が仕様書より優先し、仕様書が skill 本文より優先する。

マージは既定では人がする。
`ba0918-cycle` と `ba0918-iterate` に収束後のマージまで任せるには、リポジトリのエージェント向けの指示（`AGENTS.md` や `CLAUDE.md`）に「cycle は収束したらマージまで進める」のような 1 文を書く。
そのときも、pull request の検査が通り、人が見るべき物が無いときだけマージし、「今回はマージしない」と言えばその回は止まる。

## 入れ方

入れ方はプラグイン、パッケージマネージャ、コピーの 3 種類である。
どの入れ方でも入る skill は同じで、違うのは更新の届き方である。

### Claude Code（プラグインのマーケットプレイス）

入れた skill はマーケットプレイスの記載の版に従うので、その版が上がると更新が届く。

```
/plugin marketplace add ba0918/agentic-workflow
/plugin install ba0918-workflow@agentic-workflow
```

### Codex CLI（プラグインのマーケットプレイス）

Codex も同じマーケットプレイスの記載を読む。
skill はプラグイン名の下に、`ba0918-workflow:ba0918-brainstorm` のような名前で現れる。

```
codex plugin marketplace add ba0918/agentic-workflow
codex plugin add ba0918-workflow@agentic-workflow
```

### OpenCode（プラグイン）

`opencode.json` の `plugin` にこのリポジトリを足し、OpenCode を再起動する。
足す先は、プロジェクトの `opencode.json` でも、全体設定の `~/.config/opencode/opencode.json` でもよい。

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["agentic-workflow@git+https://github.com/ba0918/agentic-workflow.git"]
}
```

`.opencode/plugins/agentic-workflow.js` は、`skills/` を skill の置き場として登録するだけである。
この入れ方は `package.json` を読む。
この `package.json` は配布の情報を書いたもので、公開するパッケージではない。
`private: true` によって npm レジストリには載らない。

### APM（パッケージマネージャ）

[APM](https://github.com/microsoft/apm) は、複数のエージェントの skill を 1 つのマニフェストで管理する。
`apm install` は `apm.yml` に依存を足し、`apm.lock.yaml` は解決したコミットを記録する。
`apm update` を実行すると、そのコミットが新しくなる。

```
apm install ba0918/agentic-workflow --target claude
apm install -g ba0918/agentic-workflow
```

APM は、版を固定していない依存に警告を出す。
リリースのタグ（`ba0918/agentic-workflow#v{version}`）かコミット SHA で固定する。

### コピー（`gh skill` / `npx skills`）

これらのコマンドは skill をプロジェクトにコピーする。
更新は、同じコマンドをもう一度実行して取り込む。
skill を 1 つ指定するとその skill だけが入り、リポジトリを指定すると全部が入る。
ワークフローの 5 つの skill はお互いを名前で呼ぶので、まとめて入れる。

```
gh skill install ba0918/agentic-workflow --agent claude-code --all
npx skills add ba0918/agentic-workflow
```

コピーで入るのは `skills/` の中身だけである。
仕様書と回帰シナリオはこのリポジトリに残る。

## 入口の skill を常に読ませる

`ba0918-using-workflow` は新しい依頼をすべて振り分けるので、description が一致したときだけでなく、毎ターン読まれる必要がある。
プロジェクトのエージェント向け指示（`AGENTS.md`、またはエージェントが読むファイル）に、次のポインタ行を足す。

```markdown
## 重要

- 最初に `ba0918-using-workflow` を必ず読み込むこと
```

エージェントがポインタ行に従わない場合は、skill 本文をその指示ファイルへ直接貼る。
その場合、貼った本文の更新は手作業になる。

## レビューの任意の席

`ba0918-review` のフルレビューには、別のモデルで動くレビュー役を足せる。
cycle の中で呼ばれた場合と直接呼んだ場合のどちらでも同じである。
この任意の席には、品質のレビュー役と同じプロンプトを渡す。
別のモデルは、最初のモデルが見落とした指摘を拾えることがある。
その代わり、席 1 つにつきフルレビュー 1 回分のコストがかかる。

席の一覧は、ユーザースコープの指示ファイル（Claude Code なら `~/.claude/CLAUDE.md`）に書く。
使えるモデルはリポジトリではなく自分のアカウントで決まるので、一覧もそこに置く。
一覧が無ければ任意の席は無く、レビューは従来どおり動く。

各項目には次の内容を書く。

- 名前。どの席が参加したかを報告で示すときに使う
- 起動するコマンド、または呼ぶ skill。レビューのプロンプトを受け取り、指摘を JSON で返す
- 時間の上限（任意）。書かなければ、レビューは席が終わるまで待つ

```markdown
## ba0918-review optional seats

- gpt: command `<your-cli> run -` (prompt on standard input). Time limit 15 minutes
```

各席は、作業ツリーの使い捨てのコピーの中で動き、コピーは席が終わると消される。
コピーには HEAD、未コミットの変更、追跡していないファイルが入る。
追跡していないシンボリックリンクは入らない。
席が書いた物は作業ツリーに届かない。
ただし、席のコマンドを自分のサンドボックスで包むかどうかは利用者が決める。

席が失敗したとき（使用量の上限、時間切れ、起動の失敗、読めない出力）は、その席を再試行せずに外し、残りのレビュー役で続ける。
差分レビューでは任意の席を使わない。

1 回だけ席を減らしたいときは、開始するときに「今回は席 1 つ」「gpt だけ」のように伝える。
数には品質のレビュー役も含まれ、数だけを伝えると一覧の上から順に席を使う。

## 開発

### 検査

```
bun install
bun run lint:docs                                  # docs/ に textlint をかける
bunx skills-ref validate skills/<name>             # Agent Skills の仕様に照らす
```

CI は push と pull request のたびに同じ検査を走らせる。
加えて、`.claude-plugin/marketplace.json` と `package.json` の版が `.claude-plugin/plugin.json` の版と一致するかを検査する。

### リリース

版は `.claude-plugin/plugin.json` に書く。
リリースは、[CHANGELOG.md](CHANGELOG.md) の `Unreleased` の節をその版の見出しに書き換える、`main` への 1 コミットである。
そのあと release workflow が検査を走らせ、そのコミットにタグを打ち、その節をリリースノートにした GitHub release を公開する。
skill の指示の意味が変わる変更は、CHANGELOG.md に破壊的変更として記録する。

## ライセンス

MIT。`LICENSE` を参照。
