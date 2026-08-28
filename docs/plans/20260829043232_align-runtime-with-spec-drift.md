# 仕様と実装の乖離を解消する

## What & Why

2026-08-29に仕様書（`docs/spec/`）と実装（`skills/`、`tools/workflow-runtime/`）を突き合わせ、裏取りできた乖離が7件ありました。内訳は、runtimeが仕様と違う動きをするもの1件、skill本文やruntimeが実体より大きな約束をしているもの3件、仕様書の文面が古いもの3件です。

このplanは、そのうち仕様が既に答えを持つ6件を「runtimeを仕様へ合わせる」か「仕様書とskill本文を実体へ合わせる」かで解消します。残り1件は仕様側の判断が要るためbrainstormへ戻します（Non-goals参照）。作る物の意味、記録の置き場所、記録のversion（version 2）、外部依存は変えません。ドッグフーディングを始める前に、束ね直しが黙って古い予定する変更範囲を使う不具合を消し、仕様書を読んだ人が存在しないコマンドを探さない状態にすることが目的です。

## Goals

- 束ね直し（`rebound`）のあと、予定する変更範囲の内外の判定が新しいplanの`## Scope`で行われるようにします。
- implementの`resolve`が、承認時と現在の仕様書の差分を出力し、skill本文の約束と一致するようにします。
- cycleが委譲を記録するとき、実行先とモデルを記録に残せるようにします。
- 仕様書とskill本文から、存在しないコマンド名、実体と違うファイル一覧、仕様書内の矛盾を取り除きます。
- cycleから委譲するときは、仕様どおりcycleが実行IDと記録場所を作ってからimplementへ渡すよう、skill本文を仕様とruntimeに合わせます。

## Non-goals

- 次の1件は仕様側で決める事項なので、このplanでは扱わず、brainstormへ戻します。
  - reviewが指摘の確かめ方として記録できる操作の出所。現在は固定リストだけで、このリポジトリの品質ゲート（`python3 tools/quality/quality_gate.py`）を記録できません。承認済みplanの検査コマンドを根拠にするかどうかは、`docs/spec/review.md`「確かめ方を先に書く」の改訂として決めます。
- 本番から呼ばれていないコード（`deliverables.py`、`gates.py`の判定関数、`gitio.py`の一部）の削除や整理はしません。
- 秘密情報検出の網羅性、個人情報や内部ホスト名の検出は変更しません。
- 配布manifest、README、CHANGELOG、CI、version、導入経路は実装しません。cycle skillがimplementの補助スクリプトを単独の配布経路で持たない問題（cycleに`metadata.contracts`が無い）も、配布の作業として別に扱います。
- SKILL.mdが仕様書の列挙を圧縮している箇所を、仕様書と同じ粒度へ展開することはしません。
- 仕様書へ、CLIの引数名やfield名などの実装詳細を新たに書き足すことはしません。既にある補助スクリプト名の誤りを実体に合わせる訂正は行います。

## Design

このplanで使う語を先に決めます。「記録」は`.agents/evidence/`以下に残す出来事の列です。「結び付け記録（binding）」は実行1回ごとに最初に書かれる`binding.json`で、plan、承認コミット、ブランチ、予定する変更範囲を持ちます。「共有導出処理」は`tools/workflow-runtime/shared/implementation_evidence.py`にある、出来事の列から現在の状態を導く処理です。

### Reuse decisions

| Layer | Adopt / build | Reason |
|---|---|---|
| 束ね直し後の予定する変更範囲の導出 | adopt | 共有導出処理が承認コミットを`rebound`の出来事から導いているので、予定する変更範囲も同じ経路で導き、別の状態保持を作りません |
| 束ね直し先planの`## Scope`の読み取り | adopt | `tools/workflow-runtime/plan/plan_artifact.py`の`read_plan_scope`が正規の読み取りです。`documents.py`がplan本文を読む既存の場所で呼び、plan readerの公開型は変えません |
| 仕様書の差分 | adopt | `plan_artifact.py`の`SpecificationChange`が承認時本文、現在本文、unified diff、現在のコミットを既に持ちます。表示経路を足すだけです |
| 委譲の記録field | refactor existing | 共有導出処理は`delegated`に任意field`role`、`returned`に任意field`outcome`を既に受け付けます。`role`を実行先として必須にし、モデルIDのfieldを1つ新設します。記録のversionは2のまま、fieldが増えるだけです |
| 配布copy | adopt | `agentic-skill-vendor`で正本から生成し、手編集しません |

### 束ね直しと予定する変更範囲

現在、予定する変更範囲（planの`## Scope`）は実行の開始時に結び付け記録へ書かれ、その後は読み直されません。束ね直しで新しいplanへ結び直しても、予定する変更範囲の内外の判定は最初のplanの`## Scope`を使い続けます。

このplanでは、`rebound`の出来事へ新しいplanの`## Scope`を記録し、安全判定と完了判定が「最新の`rebound`が持つ予定する変更範囲、無ければ結び付け記録のもの」を使うようにします。結び付け記録は書き換えません。出来事の追記だけで現在値が導ける形を保つためです。束ね直し先のplan本文から`## Scope`を読めない場合は、束ね直しを拒否します。

### 仕様書差分の出力

`resolve`は現在、plan key、パス、承認コミットだけを出力します。runtimeは参照する仕様書ごとの変更を既に計算しているので、変更があった仕様書について、パス、承認コミット、現在のコミット、unified diffを出力へ含めます。承認時本文と現在本文の全文は含めません。委譲先の会話に長い本文を積まないためで、全文が必要ならエージェントは2つのコミットから`git show`で読めます。変更が無い場合は空の一覧を出します。skill本文（`skills/ba0918-implement/SKILL.md`）の約束`approved/current specification versions plus their Git diff`は、この出力に合わせて`approved/current specification commits plus their Git diff`に直します。

### 委譲の記録

`docs/spec/cycle.md`「委譲の記録」は、誰に渡したか（実行先とモデル）が記録に残ることを求めています。`delegated`は実行先とモデルIDを必須の引数として受け取り、`returned`は戻ってきた結果の短い要約を任意で受け取ります。cycleのSKILL.mdには、この2つのコマンドを委譲の前後で呼ぶことを明記します。

### 委譲時の実行の作り方

仕様書（`docs/spec/cycle.md`「実装を委譲する」、`docs/spec/implement.md`「委譲されて動くとき」）は、cycleから委譲するときはcycleが実行IDと記録場所を先に作ると定めています。runtimeもそのとおりに作られています。`bind --delegated`は最初の出来事をcycleの書き込みとして記録し、その後cycleが`delegated`を記録するまでimplementの書き込みを拒否します（`tools/workflow-runtime/implement/runtime/events.py`の書き手検査）。

仕様とruntimeに反しているのはskill本文だけです。`skills/ba0918-implement/references/execution.md`と`evidence.md`は委譲の有無にかかわらずimplementに実行を作らせ、`skills/ba0918-cycle/SKILL.md`は実行を作る手順を持っていません。このplanでは、runtimeを変えずにskill本文を仕様へ戻します。

ブランチと作業ディレクトリを誰が作るかは、仕様書が明示していません。ただし`bind`はブランチと作業ディレクトリが既にあることを前提にし（CLIの必須引数）、記録場所は`bind`だけが作るので、仕様の「cycleが記録場所を先に作る」はcycleがブランチと作業ディレクトリも作ることを含意します。この点は2026-08-29の対話で、責務上cycleが持つと人が決めました。`docs/spec/implement.md`「作業場所」と`docs/spec/cycle.md`「実装を委譲する」へ、その含意を明文化します。

手順は次のとおりです。cycleは、実行IDを作り、承認コミットからブランチ`implement/<実行ID>`と作業ディレクトリを作り、`bind --delegated`と`delegated`を記録してから委譲し、戻ったら`returned`を記録します。委譲されたimplementは、記録の到達点から続きを行い、実行を作らず`resumed`も記録しません。`resumed`と`retire`はcycle側の操作で、`returned`のあと次の`delegated`の前に記録します。人が直接implementを動かしたときだけ、implement自身が実行を作り、再開もimplementが記録します。runtimeの制約として、承認コミットから枝を作ったことは`bind`では検査されず、`record-commit`の祖先検査で捕まります。

### 仕様書とskill本文の修正

次を実体へ合わせます。文面だけを直し、意味は変えません。

- `docs/spec/implement.md`: 「作業場所」へ、委譲時はcycleが実行ID、ブランチ、作業ディレクトリ、記録場所を作ることを明文化。存在しない補助スクリプト名`accept-red`を、実体の`stage --phase red`へ。REDの失敗理由の分類はエージェントが判断し、runtimeは終了コードと凍結した内容だけを検査することを明記。ステージングは実装者が`git add <パス>`で個別に行い、`stage`と`record-commit`の記録時にindexとコミット内容を検査して拒否すること、拒否されたらindexから外すことを明記。出来事の表へ`resume-candidate-retired`を追加。「skill の構成」のモジュール一覧を現在のファイルへ更新。「続け方」へ束ね直し後の予定する変更範囲の扱いを追記。「残っている作業があるとき」と「続け方」にある、ブランチと作業ディレクトリの作成と`resumed`の記録をimplementが行う記述を、人が直接動かしたときに限る形へ書き分け、委譲時はcycleが行うことを明記。
- `docs/spec/cycle.md`: 「実装を委譲する」へ、cycleが作る物にブランチと作業ディレクトリを含めることを明文化。
- `docs/spec/review.md`: 「記録の置き場所」で、`.agents/evidence/reviews/`を人向け報告の置き場とする、同じ節の冒頭と矛盾した記述を削除。「skill の構成」のファイル一覧を更新。
- `docs/spec/workflow.md`: 指摘IDが番号ではなく確かめ方から導かれることに合わせて記述を修正。
- `skills/ba0918-cycle/SKILL.md`: 委譲前に実行ID、ブランチ、作業ディレクトリ、記録場所を作って`bind --delegated`で結び付けること、委譲の前後に`delegated`と`returned`を呼ぶことと渡す項目を追記。人が束ね直しを選んだときは、cycleが`rebound`を書くのではなく、`delegated`のあと委譲されたimplementが最初に`rebound`を記録することを明記（runtimeはcycleの書き込みを`worktree-bound`、`delegated`、`returned`、`resumed`、`resume-candidate-retired`に限る）。
- `skills/ba0918-implement/SKILL.md`: `resolve`が返す物を「両方のコミットと差分」に修正。
- `skills/ba0918-implement/references/execution.md`: 委譲されたときはcycleが結び付けた実行の到達点から続け、実行を作ることと`resumed`の記録は人が直接動かしたときだけであることに修正。束ね直しで予定する変更範囲が新しいplanに従うことを追記。
- `skills/ba0918-implement/references/evidence.md`: ブランチと作業ディレクトリの結び付け、発見、`resumed`の記録を、委譲時はcycle側の操作として書き分ける。

**Verification coverage:**

- `docs/spec/implement.md` / `続け方` -> `1:test`
- `docs/spec/implement.md` / `どの手順書を実行するか` -> `2:test`
- `docs/spec/cycle.md` / `委譲の記録` -> `3:test`
- `docs/spec/implement.md` / `テストで示す` -> `4:artifact`
- `docs/spec/implement.md` / `コミット` -> `4:artifact`
- `docs/spec/implement.md` / `出来事` -> `4:artifact`
- `docs/spec/implement.md` / `skill の構成` -> `4:artifact`
- `docs/spec/implement.md` / `委譲されて動くとき` -> `4:artifact`
- `docs/spec/implement.md` / `作業場所` -> `4:artifact`
- `docs/spec/implement.md` / `残っている作業があるとき` -> `4:artifact`
- `docs/spec/cycle.md` / `受け取るもの` -> `4:artifact`
- `docs/spec/cycle.md` / `実装を委譲する` -> `4:artifact`
- `docs/spec/review.md` / `記録の置き場所` -> `4:artifact`
- `docs/spec/review.md` / `skill の構成` -> `4:artifact`
- `docs/spec/workflow.md` / `review → 修正 → review: 指摘の集合` -> `4:artifact`
- `docs/spec/quality-tooling.md` / `Pythonの検査対象` -> `5:check`

## Scope

```text
docs/
  spec/
    cycle.md
    implement.md
    review.md
    workflow.md
tools/
  workflow-runtime/
    shared/
      implementation_evidence.py
    implement/
      runtime/
        cli.py
        completion.py
        documents.py
        evidence.py
        safety.py
    tests/
      implement_event_test.py
      implement_evidence_test.py
      implement_safety_test.py
      implement_runtime_test.py
      implementation_evidence_test.py
skills/
  ba0918-cycle/
    SKILL.md
  ba0918-implement/
    SKILL.md
    references/
      evidence.md
      execution.md
    scripts/
      implementation_evidence.py
      runtime/
        cli.py
        completion.py
        documents.py
        evidence.py
        safety.py
  ba0918-review/
    scripts/
      implementation_evidence.py
```

## Step 1: 束ね直し後の予定する変更範囲を新しいplanから導く

`rebound`の出来事に、束ね直し先のplanの`## Scope`を記録します。安全判定（予定する変更範囲の内外と、範囲外への理由の要求）と完了判定は、最新の`rebound`が持つ予定する変更範囲を使い、`rebound`が無ければ結び付け記録のものを使います。

反例テストでは、`## Scope`が狭まったplanへ束ね直したあと、旧planにだけ含まれるパスを記録すると理由が要求されること、新planに含まれるパスは理由なしで通ることを示します。束ね直し先のplanから`## Scope`を読めない場合に`rebound`が拒否されることも示します。

前提はありません。変更してよいのは`implementation_evidence.py`、`documents.py`、`evidence.py`、`safety.py`、`completion.py`と、対応するテスト（`implement_safety_test.py`、`implement_evidence_test.py`、`implement_runtime_test.py`、`implementation_evidence_test.py`）です。実装側に任せる選択は、出来事のfield名です。`plan_artifact.py`の公開型は変えず、`## Scope`は`read_plan_scope`を`documents.py`から呼んで読みます。

Stop condition: 結び付け記録を書き換えないと予定する変更範囲を導けない設計しか成立しない場合は、独自に書き換えを足さず停止します。

## Step 2: `resolve`が仕様書の変更を出力する

`resolve`の出力へ、変更があった仕様書ごとに、パス、承認コミット、現在のコミット、unified diffの一覧を加えます。変更が無ければ空の一覧です。全文は含めません。

テストでは、承認コミット後に仕様書を1箇所変更した状態で`resolve`を実行し、出力にそのパスとdiffと2つのコミットが含まれること、全文が含まれないことを示します。変更が無い状態では一覧が空であることも示します。

前提はありません。変更してよいのは`cli.py`と対応するテストです。出力のkey名は実装側に任せます。

Stop condition: diffに秘密らしい値が含まれる場合の扱いを決めないと出力できないと判断した場合は、検査を自己判断で足さず停止します。

## Step 3: 委譲の記録に実行先とモデルを残す

`delegated`は実行先とモデルIDを必須の引数として受け取り、出来事に記録します。`returned`は結果の短い要約を任意で受け取ります。共有導出処理は、`delegated`にこれらのfieldが無い出来事を拒否します。

反例テストでは、実行先かモデルを欠く`delegated`が拒否されること、揃っていれば記録され`current-status`から読めることを示します。既存の`implement_event_test.py`にある、fieldを持たない`delegated`を受理するテストは、新しい契約に合わせて書き換えます。

前提はStep 1です。Step 1が`rebound`の出来事の検査を変え、Step 3は同じ境界出来事の検査を変えるためです。変更してよいのは`implementation_evidence.py`、`cli.py`と対応するテストです。実行先は既存の`role`をそのまま必須にし、新設するモデルIDのfield名は実装側に任せます。拒否の検査は「拒否されること」を確かめ、特定のエラーコードは求めません（共有導出処理の既存コード`evidence_invalid`で足りるため、`events.py`は触りません）。

Stop condition: 実行先を持たない既存の`delegated`出来事（version 2）を読めなくする変更しか成立しない場合は、互換処理を自己判断で足さず停止します。

## Step 4: 仕様書とskill本文を実体へ合わせる

「仕様書とskill本文の修正」に列挙した箇所を書き換えます。実体より大きな約束をしている記述を実体へ縮める訂正を含みますが、作る物の意味、人が判断する場面、記録の置き場所は変えません。Step 1、2、3で確定した振る舞い（束ね直し後の予定する変更範囲、`resolve`の出力、委譲記録の項目）と、「委譲時の実行の作り方」を反映するため、それらの後に行います。

独立レビューが当てる反例は「cycle SKILL.mdが依然としてimplementに実行を作らせている」「execution.mdが委譲時にも実行を作る」「仕様書の節が実体と違うコマンド名やファイル名を残している」です。形式検査は、仕様書には`python3 tools/quality/quality_gate.py --scope worktree`（textlintによる文章検査を含む）、skill本文には`bunx agentic-skill-vendor lint-selfcontain`（skillの外を参照していないことの検査）です。独立レビューでは、修正後の各節が対応するコードの実体と一致していること、削除した記述が他の節の意味を壊していないことを判断します。

前提はStep 1、2、3。変更してよいのは`docs/spec/`の4ファイルと、`skills/ba0918-cycle/SKILL.md`、`skills/ba0918-implement/SKILL.md`、`skills/ba0918-implement/references/execution.md`、`skills/ba0918-implement/references/evidence.md`です。cycle SKILL.mdでは補助スクリプトをパス無しのコマンド名で呼びます。

Stop condition: 文面を直す過程で、仕様の意味そのものを変えないと矛盾が解けない箇所が見つかった場合は、その箇所を直さずに停止し、brainstormへ戻します。

## Step 5: 配布同期と全体検査を行う

正本から配布copyを生成し、runtime、品質ツール、構造規則、型、文章規則、自己完結性を全体で検査します。生成物を手編集しません。前提はStep 1、2、3、4です。配布copyの生成元がすべて確定してから走らせるためです。生成した配布copyをコミットしたあと、同じ検査をもう一度走らせ、それをこの手順の最後の記録にします。

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `bunx agentic-skill-vendor lint-selfcontain`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`
- `python3 -m unittest discover -s tools/quality/tests -p '*_test.py'`
- `python3 tools/quality/quality_gate.py --scope all`

Stop condition: 新しい依存、記録のversionの変更、仕様に無い公開契約の変更が必要になった場合は停止します。
