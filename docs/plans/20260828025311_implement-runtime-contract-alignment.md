# implement runtime の仕様適合

**Verification coverage:**

- `docs/spec/workflow.md` / `機械の検査は、現実との境界と壊れた入力を見る` -> `1:test`
- `docs/spec/workflow.md` / `現在地の導き方` -> `1:test`
- `docs/spec/implement.md` / `作業場所` -> `1:test`
- `docs/spec/implement.md` / `テストで示す` -> `1:test`
- `docs/spec/workflow.md` / `機械の検査は、現実との境界と壊れた入力を見る` -> `2:test`
- `docs/spec/implement.md` / `テストで示す` -> `2:test`
- `docs/spec/implement.md` / `作った物で示す` -> `2:test`
- `docs/spec/implement.md` / `証拠の残し方` -> `2:test`
- `docs/spec/workflow.md` / `承認を儀式にしない` -> `3:test`
- `docs/spec/plan.md` / `機械が読む構造` -> `3:test`
- `docs/spec/plan.md` / `実装途中で人へ返す場面の宣言` -> `3:test`
- `docs/spec/implement.md` / `手順中に人が判断する場面` -> `3:test`

## 目的

implement runtime が、承認済み仕様と異なる作業場所、テスト失敗、成果物、または人の判断を
正しい証拠として受理しない状態にします。作業者による証拠の偽造を想定した防御ではなく、通常の
実行で別の対象や別の失敗を完了と取り違えないための境界修正です。

変更後も、人へ返すのは重要な設計判断、不可逆な操作、人だけが持つ権限、危険な対象、または
被害が広がる事故だけです。新しい承認場面、外部依存、証拠の指紋、署名、互換経路、保存場所は
追加しません。既存の version 2 binding と event に必要な構造化項目を加え、過去形式との互換性は
持たせません。このruntimeは配布前であり、互換性を維持する要求が無いためです。

## 実装方針

- パスの字句上の安全性は既存の `path_safety.py` を使います。実在ファイルが専用worktree内に
  解決されるかの検査だけを、filesystemを知るimplement境界へ追加します。新しいライブラリは
  導入しません。
- branchとworktreeの実体確認にはGit自身の `worktree list --porcelain`、`rev-parse`、
  `--git-common-dir`を使います。独自の一覧やロックは作りません。
- REDの意味判断は、テスト出力を見たimplementが既存CLIへ失敗種別と具体的理由を渡します。
  runtimeは「未実装の振る舞いによる失敗」だけを受理し、構文、読み込み、依存、権限、network、
  無関係な既存失敗、または内容の無い一般的な理由を拒否します。runtimeへtest runnerやtest
  framework固有の出力解析は追加しません。
- artifactは既存の`paths`と、Gitから導いたcommitの`paths`を照合します。内容の独自指紋は
  追加しません。
- Human gatesは既存plan parser、binding、event列を接続します。implementが意味を読んで人へ返す
  責務は変えず、runtimeは宣言されたgate、対象、timing、承認結果と後続eventの順序だけを検査
  します。runtimeを通らないshell操作まで遮断する実行基盤は作りません。

再利用する層と理由は次のとおりです。

- 相対パスの字句検査 — 既存`path_safety.py`を採用。同じ危険判定を増やさないため
- 実在pathとworktreeの照合 — Python標準`pathlib`とGitを採用。既存の境界だけで判定できるため
- branch/worktree一覧 — Gitの`worktree list`を採用。独自状態を持たない合意を守るため
- Step・Human gate構文 — 既存`plan_artifact.py`へ追加。parser正本を増やさないため
- event遷移と完了導出 — 既存`context.py`と`implementation_evidence.py`へ追加。解釈を二重化しないため

## Scope

```text
tools/
  workflow-runtime/
    plan/
      plan_artifact.py
    implement/
      runtime/
        cli.py
        context.py
        gates.py
        repository.py
    shared/
      implementation_evidence.py
      path_safety.py
    tests/
      implement_evidence_test.py
      implement_runtime_test.py
      implementation_evidence_test.py
      plan_artifact_test.py
      review_runtime_test.py
skills/
  ba0918-plan/
    SKILL.md
    references/
      creation.md
    scripts/
      plan_artifact.py
  ba0918-implement/
    references/
      artifacts.md
      evidence.md
      execution.md
      tdd.md
    scripts/
      implementation_evidence.py
      path_safety.py
      plan_artifact.py
      runtime/
        cli.py
        context.py
        gates.py
        repository.py
  ba0918-review/
    scripts/
      implementation_evidence.py
      path_safety.py
vendor-lock.json
```

## Step 1: 実行を専用branchとworktree内の対象へ束縛する

目的は、mainの作業ディレクトリや別checkoutを、今回の実装場所または凍結テストとして受理しない
ことです。既存のplan解決とversion 2 bindingを前提にします。

REDでは、少なくとも次の反例を先に追加します。

- branch名が`implement/<run-id>`でない
- リポジトリのmain作業ディレクトリ自身をworktreeとして渡す
- 同じGit repositoryでも`git worktree list`にbranchとの組として登録されていない場所を渡す
- bind時のworktree HEADがplan approval commitと異なる
- test pathが絶対パス、`..`、途中のsymlinkでworktree外へ出る、または通常ファイルでない
- 正しいlinked worktree内の相対test・fixture pathは受理される

GREENでは、bindのlibrary境界でbranchとworktreeを必須にし、branch名、Git登録、repository rootとの
分離、共通Git directory、branch tip、worktree HEAD、approval commitを1つの検査経路で照合します。
凍結対象の読込みは、相対pathの字句検査後にstrict resolveし、専用worktree内のsymlinkでない通常
ファイルだけを読みます。`_worktree`のrepository rootへのfallbackは廃止します。

REFACTORでは、pathとGit境界の判定が呼出箇所へ重複していないかを確認します。新しい状態管理、
worktree作成方法、reboundの履歴構造は変更しません。

直接検証は、上の反例を含むruntime unit testです。補助検証として全runtime testとvendor複製の
一致を確認します。

実装側に任せるのはpure helperの名前と、既存`path_safety.py`へ置く字句判定とfilesystem境界へ
置く実体判定の分け方だけです。既存Gitコマンドだけで一意に判定できない、新しい永続状態が必要、
またはreboundの意味を変える必要が出た場合は止めてbrainstormへ戻します。

## Step 2: REDとartifactを対象の証拠へ結び付ける

目的は、単なるcommand失敗をREDにせず、空の成果物や無関係なcommitでartifact手順を完了させない
ことです。Step 1のworktree内path検査と、既存のGit由来commit safety pathsを使います。

REDでは、少なくとも次の反例を先に追加します。

- REDの終了codeが非zeroでも、失敗種別が構文、読み込み、依存、権限、network、無関係な既存失敗
  なら拒否する
- 失敗理由が空、`failed`、`exit code 1`のように未実装の振る舞いを示さない場合は拒否する
- 未実装の振る舞いと具体的理由を持つREDだけを受理し、GREENとREFACTORまで同じsnapshotを使う
- artifactのpathsが空、存在しない、worktree外、またはsymlinkなら拒否する
- artifact後の同じStepのcommitがartifact pathsをすべて含まない場合は未完了のままにする
- artifact pathsを削除するcommitでは、そのpathが差分に現れても未完了のままにする
- format checkが無いartifactでも、実在pathsとそれを含むcommitがあれば完了できる

GREENでは、RED eventへ失敗種別と短い具体的理由を保存し、CLI、event入力境界、共有evidence解釈の
すべてで必須にします。artifact eventは非空の安全な実在pathsを保持します。完了導出は後続commit
のGit由来`paths`がその集合を包含し、そのcommitのtreeにも同じpathの通常ファイルが存在するとき
だけStepを完了させます。

REFACTORでは、runtime書込み時と共有読込み時の規則が同じ語彙と関係を表しているかを確認します。
test出力、秘密、環境変数、artifact内容の指紋は保存しません。

直接検証は、上の反例を含むevent遷移と完了導出のunit testです。補助検証として全runtime testと
vendor複製の一致を確認します。

実装側に任せるのは内部enum名とerror code名だけです。test framework固有parser、新しいevent種別、
証拠version、内容指紋、または外部依存が必要になった場合は実装せずbrainstormへ戻します。

## Step 3: 宣言されたHuman gateを実行順序へ接続する

目的は、危険な例外としてplanに宣言された人の判断が無い、却下された、または対象が違う状態で
後続の証拠や全手順完了を受理しないことです。承認場面を新しく作らず、planに宣言がある場合だけ
適用します。

REDでは、少なくとも次の反例を先に追加します。

- `Human gates` JSONのversion、gate idの一意性、sections、criterion、target、timing、
  allowed resultsのJSON構造が不正ならplanを拒否する。sectionsとVerification coverageの意味上の
  対応はruntimeで拒否せず、plan作成と独立reviewが判断する
- `before_edit`の承認前にそのStepのstage evidenceを記録できない
- `before_commit`の承認前にそのStepのcommitを記録できない
- `before_implementation_green`の承認前に全手順完了を記録できない
- 宣言に無いgate、対象が宣言と異なる判断、判断無し、`rejected`を後続作業の許可に使えない
- `rejected`後にrunをresumeしただけでは境界を越えられず、同じgateへの新しい`approved`か、
  人が選んだreboundでgateが不要になった場合だけ進める
- reboundでgate contractが追加または変更されたStepへ、古い完了状態や承認結果を持ち越さない。
  Stepとgate contractが同一の場合だけ既存承認を持ち越せる
- 宣言どおりの対象に`approved`を記録すると、指定した境界だけを越えられる
- Human gate宣言が無い通常のplanは、追加承認なしで従来どおり進む

GREENでは、plan parserが各Stepのgate宣言を読み、bindとreboundがStep contractへ保持します。
既存CLIへgate結果の記録入口を接続し、runtimeが宣言から対象を導いてeventへ保存します。event遷移と
完了導出はgate id、対象、timing、resultを照合します。`rejected`は停止状態として扱い、既存の
resumeだけでは解除しません。同じgateへの新しい`approved`、または人が選んだreboundで新しいplan
からgateが無くなった場合にだけ先へ進めます。rebound mappingはStepとgate contractが同一の場合
だけ完了状態と承認結果を持ち越し、gateの追加または変更があるStepは既存仕様どおりやり直します。

REFACTORでは、Human gateの意味判断がimplement、構造と順序の検査がruntimeという責務境界を
確認します。一般的なStep、artifactの意味review、cycle終端の成果物確認へ承認を増やしません。

直接検証は、plan parser、event遷移、完了導出を通したintegration寄りのunit testです。補助検証
として全runtime testとvendor複製の一致を確認します。

実装側に任せるのは内部型と関数名だけです。planに無いgateの追加、承認対象の拡張、runtimeによる
shell操作の仲介、または新しい権限機構が必要になった場合は実装せずbrainstormへ戻します。

## 完了条件

- 各Stepが反例を先に追加したRED、最小実装のGREEN、整理後のREFACTORを実測している
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`が全件成功する
- `bunx agentic-skill-vendor verify`が成功し、正本と配布用scriptの差分が無い
- main作業場所、別checkout、worktree外path、誤ったRED、空artifact、無関係commit、未承認gateを
  それぞれ独立したテストが拒否している
- 正しい専用branch/worktree、期待したRED、実在artifactと対応commit、宣言済みgateの承認を持つ
  正常系が完了できる
- 新しい依存、承認場面、独自の状態一覧、証拠version、指紋、署名、互換経路が増えていない
- 実装者とは別のreviewerが最初に全差分をreviewし、修正後は未解決findingと影響範囲だけを確認し、
  最後に仕様との全体整合を1回確認している

## 実装中に人へ返す条件

新しい外部依存、証拠versionまたは保存場所の変更、reboundの履歴構造の変更、Human gateの対象や
承認場面の追加、runtimeがshell操作を仲介する新しい権限境界、または仕様に無い重要な判断が必要に
なった場合だけ人へ返します。安全なtest file、helper、配布複製のScope漏れは理由を記録して止まらず
補います。
