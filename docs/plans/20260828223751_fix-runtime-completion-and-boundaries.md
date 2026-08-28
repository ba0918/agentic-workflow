# runtimeの誤完了防止と責務境界の整理

## What & Why

全体レビューで、実装が本来止まるべき状態や未完了の状態でも、完了として扱える反例が3件見つかりました。Human gateの判断が実行時へ渡らない、新しいREDが古い成功記録を無効化しない、artifactの証拠が対象ファイルと結び付かない、という問題です。

同時に、前回のruntimeリファクタリングで残った状態遷移の二重解釈、Git status parserの重複、review内部のimport cycle、テストからしか使われないhelper、plan/state helperの不明瞭な実行方法を整理します。外から見えるworkflowの意味、保存場所、event version、外部依存は変えません。

## Goals

- planで宣言したHuman gateをbindingへ運び、指定時点より前の承認記録が無ければ実装を完了できないようにします。
- 最新のTDD chainとartifact対象に基づいて完了を判定し、古い証拠や無関係なcommitによる誤完了を拒否します。
- 状態遷移、Git status解釈、finding検査の責務を1方向へ揃えます。
- planとbrainstormの補助スクリプトへ、skill本文からそのまま使える明示的なCLIを用意します。
- 現在の公開facade、version 2 evidence、保存場所、依存集合を維持します。

## Non-goals

- 秘密情報を検出する正規表現の網羅性は変更しません。
- evidence全件読み込みの性能・メモリ改善は行いません。
- `PROJECT.md`、ROADMAP、仕様書の軽微な文書driftは別作業とします。
- release manifest、README、CI、version、導入経路は実装しません。
- 過去の`.agents/artifacts/ideas`は移動または削除しません。

## Design

### Reuse decisions

| Layer | Adopt / build | Reason |
|---|---|---|
| implementation state transition | adopt | `tools/workflow-runtime/shared/implementation_evidence.py`のreducerを正本にし、別の状態機械を増やしません |
| Git status parsing | adopt | `tools/workflow-runtime/shared/git_status.py`がrename/copyを含むNUL区切り形式を既に扱います |
| review finding validation | refactor existing | 現在のbinding検査を副作用の無い下位moduleへ移し、eventsとfindingsの循環だけを解きます |
| helper CLI | adopt standard library | 既存関数を`argparse`とJSON入出力で包めば足り、新しい依存は不要です |
| distributed copies | adopt | `agentic-skill-vendor`で正本から生成し、手編集しません |

書き込み側はactor、作業場所、Git、安全検査、追記保存を担当します。eventのschemaと順序、step完了、Human gateの充足は共有reducerが担当します。候補eventを既存列の末尾へ仮に加えてreducerへ渡し、受理された場合だけ保存することで、書き込み時と再読込時の意味を一致させます。

Human gateはplanの既存JSON宣言をStep contractへ含めます。runtimeの専用commandは、bindingにある宣言から`gate_id`、対象、時機、許可結果を導き、callerによる置き換えを受け付けません。`before_edit`は対象fileがGitのindex・worktreeで未変更、かつ対象Stepの作業eventがまだ無い時だけ記録できます。`before_commit`は対象Stepの完了証拠の後に記録し、その後に対象を変えるStep eventを挟まずcommitへ進めます。`before_implementation_green`は対象Stepの完了後に記録し、その対象を変える後続eventが無い場合だけ全体完了へ進めます。event対象は、宣言したsequenceが存在し、そのeventを正確に参照する場合だけ受け付けます。`rejected`は承認済みとして扱いません。

ここで機械的に守る「判断の対象が変わっていない」は、宣言したfile path集合またはevent sequenceと、Gitで観測できる操作順です。同じ作業者が承認eventの外で同一pathのbytesを差し替えることを想定した独自fingerprint、作業directoryの同一性検査、署名は作りません。これは`docs/spec/implement.md`の単一作業者の偽造・改変対策を作らない境界を守るためです。`rebound`では旧Stepと新StepのHuman gate宣言が完全に同じ場合だけ完了状態と承認を持ち越し、追加、削除、対象、時機、問い、許可結果の変更があれば持ち越しません。

helper CLIはlibrary APIを置き換えません。plan readerは未commitの候補planを、commit済み仕様と照合して検査できる入口を持ちます。state helperは保存、読込、検査、wrap完了を既存関数経由で行います。skill referenceには推測を要しない完全なコマンドを記載します。

**Verification coverage:**

- `docs/spec/plan.md` / `人が判断する場面` -> `1:test`
- `docs/spec/implement.md` / `手順中に人が判断する場面` -> `1:test`
- `docs/spec/implement.md` / `手順の実行` -> `2:test`
- `docs/spec/quality-tooling.md` / `runtimeリファクタリング` -> `3:test`
- `docs/spec/quality-tooling.md` / `Pythonの構造規則` -> `3:test`
- `docs/spec/quality-tooling.md` / `runtimeリファクタリング` -> `4:test`
- `docs/spec/quality-tooling.md` / `Pythonの構造規則` -> `4:test`
- `docs/spec/plan.md` / `skill の構成` -> `5:test`
- `docs/spec/brainstorm.md` / `skill の構成` -> `5:test`
- `docs/spec/quality-tooling.md` / `実行経路` -> `6:check`

## Scope

```text
tools/
  workflow-runtime/
    brainstorm/
      state.py
    plan/
      plan_artifact.py
    shared/
      git_status.py
      implementation_evidence.py
    implement/
      runtime/
        cli.py
        completion.py
        events.py
        evidence.py
        gates.py
        planning.py
        repository.py
    review/
      review_model.py
      review_support/
        events.py
        finding_validation.py
        findings.py
        repository.py
    tests/
      brainstorm_state_test.py
      facade_contract_test.py
      implement_binding_test.py
      implement_event_test.py
      implement_evidence_test.py
      implement_runtime_test.py
      implementation_evidence_test.py
      plan_artifact_test.py
      review_findings_test.py
      review_model_test.py
      review_runtime_test.py
      vendor_entrypoints_test.py
skills/
  ba0918-brainstorm/
    references/
      state.md
    scripts/
      state.py
  ba0918-plan/
    references/
      creation.md
    scripts/
      plan_artifact.py
  ba0918-implement/
    references/
      evidence.md
      execution.md
    scripts/
      implementation_evidence.py
      plan_artifact.py
      runtime/
        cli.py
        completion.py
        events.py
        evidence.py
        gates.py
        planning.py
        repository.py
  ba0918-review/
    scripts/
      git_status.py
      review_model.py
      review_support/
        events.py
        finding_validation.py
        findings.py
        repository.py
vendor-manifest.yaml
vendor-lock.json
```

## Step 1: Human gateをplanから完了判定まで接続する

plan parser、resolved plan、binding、CLI、event reducerを通して既存のHuman gate宣言を運びます。宣言のschema、重複`gate_id`、許可されたtarget kind・timing・result・安全なtargetを境界で検査します。ba0918-implementのreferenceには、人へ返す時点と、回答後に専用commandで判断を記録して再開する手順を記載します。

反例テストでは、gate未記録、対象と違うgate、`rejected`、時機を過ぎた`approved`、編集済み対象への`before_edit`、対象event sequenceの不一致でstep evidence、commit、`implementation_green`が拒否されることを示します。正しい時機の`approved`では従来の実装が進むことも確認します。

`rebound`ではgate宣言全体を新しいStep contractへ運びます。gate追加、削除、file・event対象変更、timing変更、criterion変更、allowed results変更のどれかがあるStepは旧完了と旧承認を引き継がず、同一宣言だけを一対一mappingで持ち越す反例テストを追加します。

保存形式はversion 2のまま、追加fieldを持つ同version eventとして扱います。既存bindingにgate宣言が無い実行の意味は変えません。

Stop condition: 既存仕様だけではgateの対象または時機を一意に対応できない場合は、推測で新しい意味を作らず停止します。

## Step 2: 最新のTDD chainとartifact対象だけを完了証拠にする

test stepは、最後に開始したRED以降の`RED -> GREEN -> REFACTOR -> commit`だけを有効な完了chainとして扱います。完了後に新しいREDが記録された場合、古いchainは完了判定へ使いません。

artifact stepは1つ以上の対象pathを要求し、後続commitのcanonical safety pathがartifact対象をすべて含む場合だけ完了させます。形式検査が存在しないartifactは、現在の契約どおりchecks 0件を許します。空のpathと無関係なcommitの反例を追加します。同一pathの内容をartifact記録後に作業者自身が差し替えることは、このworkflowが防がない改変想定であり、独自fingerprintを追加しません。

Stop condition: version 2の既存eventを新しい意味へ移行しないと読めない場合は、互換処理を自己判断で追加せず停止します。

## Step 3: implementation状態遷移の意味を共有reducerへ一本化する

`runtime/events.py`に重複しているtest、check、artifact、commit、停止、再開の順序判定を共有reducerへ寄せます。書き込み側に残すのはactor権限、実体のGit照合、canonical operationの限定、保存前後の競合防止です。

公開facadeと既存error codeを、利用者が分岐に使う範囲で維持します。既存の全状態遷移テストに加え、同じcandidateが書き込み時と全履歴再読込時に同じ評決になるcontract testを追加します。

Stop condition: 公開error contractを変更しないと一本化できない場合は、変更を隠さず停止します。

## Step 4: review内部の重複と逆依存を除く

reviewの`uncommitted_paths`は共有`git_status.parse_porcelain_v1_z`を使い、独自parserを削除します。配布されたreview skillでも同じhelperを読めるよう、vendor mappingへ個別fileを追加します。

findingのbinding検査をeventsとfindingsの双方から依存できる`finding_validation.py`へ移し、`events -> findings -> events`の循環を無くします。production callerが存在せず、常に`True`を返す`can_append_after`と、その実装詳細だけを確認するtestを削除します。他の未使用候補は、このStepで実利用を機械確認できたものだけを削除します。

Stop condition: facadeの公開symbol削除または外部利用の可能性が確認された場合は、互換性を推測せず対象から外します。

## Step 5: plan readerとstate helperへ明示的なCLIを設ける

`plan_artifact.py`へ、未commitの候補planのcoverage、Step、Checks、Scopeと、参照するcommit済み仕様を検査するread-only commandを追加します。承認済みplanを読む既存library APIは維持します。

`state.py`へ、既存のvalidate、load、save、finish処理を呼ぶsubcommandを追加します。JSONは標準入力と標準出力で受け渡し、秘密らしい値、symlink、revision conflictなど既存の失敗を成功へ変換しません。

各skill referenceを、repository pathに依存しない完全なコマンド例へ更新します。CLIのhelp、成功、主要な拒否、isolated skill copyからの起動をbehavior testで示します。

Stop condition: CLI化に新しい保存形式、外部依存、または人の承認境界の変更が必要なら停止します。

## Step 6: 配布同期と全体検査を行う

正本から配布copyを生成し、runtime、品質ツール、型・構造規則、自己完結性を全体で検査します。生成物を手編集しません。

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `bunx agentic-skill-vendor lint-selfcontain`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`
- `python3 -m unittest discover -s tools/quality/tests -p '*_test.py'`
- `python3 tools/quality/quality_gate.py --scope all`

Stop condition: 新しい依存、保存schema versionの変更、仕様に無い公開契約変更が必要になった場合は停止します。
