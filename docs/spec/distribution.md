# 配布とリリース

## 対象と価値

agentic-workflowは、`skills/`にある5つのワークフローskillを複数のAIエージェントへ配布します。対応する実行先はClaude Code、Codex、OpenCodeです。導入した利用者は、旧claude-skills pluginに依存せず、brainstorm、plan、implement、review、cycleを認識して実行できます。

導入経路は、plugin marketplace、APM、`gh skill`、`npx skills`です。導入ツールが対応していても、前記以外のAIエージェント上での実行までは保証しません。

## 配布経路

配布経路が異なっても、配布するskillの正本はリポジトリ直下の`skills/`だけです。経路ごとにskillの複製を作りません。

| 経路 | 対象 | 配布方法 |
|---|---|---|
| Plugin marketplace | Claude Code、Codex | `.claude-plugin/marketplace.json`からリポジトリ直下をpluginとして導入する |
| OpenCode plugin | OpenCode | `package.json`から`.opencode/plugins/agentic-workflow.js`を読み、`skills/`をskill検索パスへ追加する |
| APM | APMが対応する対象 | リポジトリのplugin情報と`skills/`をAPMに発見させる。専用manifestは追加しない |
| Copy | `gh skill`、`npx skills`が対応する対象 | `skills/`全体または指定されたskillを対象プロジェクトへ複製する |

OpenCode用処理は`skills/`を登録するだけにします。セッションへの文面注入、ワークフローの独自実行、状態管理は行いません。OpenCode固有の補助manifestが必要かは、`agentic-meta`の構成と実際のgit導入検査からplanで確定します。必要な場合は参照構成を採用し、独自形式は作りません。

## 配布物の構成

plugin名は`ba0918-workflow`、リポジトリ名とOpenCode package名は`agentic-workflow`とします。

- `.claude-plugin/plugin.json`はpluginの識別情報、正本バージョン、ライセンス、リポジトリを宣言する。
- `.claude-plugin/marketplace.json`はClaude CodeとCodexが読むmarketplace情報を宣言する。
- `.opencode/plugins/agentic-workflow.js`はOpenCodeへ`skills/`を登録する。
- `package.json`はOpenCodeが読む入口と配布対象を宣言する。npm registryへ公開しないため`private: true`を維持する。
- `README.md`はskillの役割、必要条件、各導入方法、代表的な利用方法、検証方法、既知の制限を説明する。
- `CHANGELOG.md`は公開済みバージョン間の利用者から見える差分を記録する。
- `LICENSE`はリポジトリ全体のMITライセンスを記録する。各`SKILL.md`も`license: MIT`を宣言する。

配布manifestやversion followerを生成する独自ツールは作りません。小さな宣言の一致はCIで検査します。

## バージョンと更新

正本バージョンは`.claude-plugin/plugin.json`の`version`です。初回リリースは`0.1.0`とします。`.claude-plugin/marketplace.json`と`package.json`のversion、`CHANGELOG.md`の最新公開見出しは正本へ一致させ、CIで不一致を拒否します。

公開済みバージョンにはannotated tagを1つ対応させます。初回タグは`v0.1.0`です。共有remoteへ公開したタグは移動、再利用、再作成せず、修正は新しいバージョンとして公開します。

Marketplace経路の更新はversionの更新で利用者へ届けます。Gitの参照を扱えるcopy経路とAPMでは、再現性を必要とする利用者がrelease tagまたはcommit SHAへ固定できます。その方法をREADMEで説明します。

## CIによる機械検証

GitHub Actionsはpull requestと`main`へのpushで動作し、権限を`contents: read`に制限します。CIは公開せず、ファイルも生成せず、次を検査します。

- lockfileを変更しないfrozen install
- agentic-skill-vendor自身のself-test
- vendored copyと正本の一致
- 配布skillがリポジトリ外の暗黙のパスへ依存していないこと
- 正本とfollowerのversion一致
- 5つのskillがAgent Skills仕様に適合すること
- workflow runtimeのテスト
- 品質検査ツール自身のテスト
- `docs/spec/quality-tooling.md`が定める全追跡範囲の品質検査
- OpenCode用入口が`skills/`だけを1度登録すること
- claude-skills pluginへの実行時依存が配布物に残っていないこと

CIでは、導入経路ごとに別のskill実装を検査しません。全経路が同じ`skills/`を配布することと、それぞれの入口がその正本へ到達することを分けて検査します。

## 導入経路の検証

公開前に、Claude Code、Codex、OpenCode、APM、`gh skill`、`npx skills`の各経路を一時的な設定または出力先で検査します。利用者の既存設定、global installation、認証情報を変更してはいけません。

各経路は、対象のリリース候補から5つのskillを発見または複製でき、配布対象外の`evals/`、`tools/`、開発用文書をskillとして導入しないことを確認します。導入ツールが決定論的なdry-runを提供する場合はCIで実行します。出力先を指定できる経路もCIで実行します。外部認証や利用者設定を必要とする経路は、manifestと入口をCIで検査し、隔離環境での実導入を公開前の手動スモークテストに含めます。

導入ツールのversionは、参照実装または公式の固定可能な配布物を使います。versionを固定できないpreview機能は独立したCI手順にし、その変更を他の品質検査から区別できるようにします。

## 初回リリースの検証

リリース候補commitを先に作り、そのcommitと同じ内容を機械検証します。旧claude-skills pluginに依存しない一時的な設定へ候補を導入し、主要skillが認識されることを確認します。さらに、1つの代表環境で`brainstorm -> plan -> cycle`が完了できることを一度だけ確認します。

LLMを実行するE2Eは、モデル、トークン消費、実行時間が大きく変動するためCIの必須検査にしません。skill本文だけを変更するたびにE2Eを強制する仕組みも追加しません。

## 失敗時の扱い

機械検証または手動スモークテストが失敗した場合、候補commitへ`v0.1.0`タグを付けません。原因を修正した新しい候補commitを作り、そのcommitで同じ検証をやり直します。導入ツールの仕様変更が疑われる場合は、skill本文を迎合させる前に、参照実装と現在のツール出力を確認します。

旧claude-skills pluginは、新しいpluginの単独動作を確認するまで削除しません。削除と利用者環境の設定変更は、このリポジトリのリリース実装には含めません。

## 公開境界

検証に成功したリリース候補commitへannotated tag `v0.1.0`を付けます。`CHANGELOG.md`の`0.1.0`見出しと比較リンク、正本version、version followerは、その候補commitに含まれていなければなりません。

`main`とタグのpushは外部公開操作です。実行直前に人へ、対象commit、検証結果、公開するbranchとtagを示して確認を求めます。GitHub Releaseオブジェクト、npm公開、中央registryへの登録は、導入経路が要求しない限り作成しません。

## 実装単位

最初に`tools/workflow-runtime`を全体品質検査へ適合させ、振る舞いを維持したまま独立レビューを完了します。その変更を取り込んだ後、配布manifest、README、CI、導入経路検証、リリース候補を別のplanで実装します。runtimeリファクタリングと配布作業を1つのreview差分へ混在させません。

## 非対象

- Claude Code、Codex、OpenCode以外の実行互換性
- 旧claude-skillsとの互換層または移行処理
- npm registryへのpackage公開
- 配布manifestの独自生成器
- LLM E2Eを継続的に必須化する仕組み
- 旧pluginの削除や利用者環境の永続設定変更
