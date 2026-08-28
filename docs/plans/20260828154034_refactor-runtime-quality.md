# runtimeを品質ゲートへ適合させる

**Verification coverage:**

- `docs/spec/quality-tooling.md` / `目的` -> `1:test`
- `docs/spec/quality-tooling.md` / `配置` -> `1:test`
- `docs/spec/quality-tooling.md` / `依存方向` -> `1:test`
- `docs/spec/quality-tooling.md` / `共通コマンドの契約` -> `1:test`
- `docs/spec/quality-tooling.md` / `Pythonの検査対象` -> `1:test`
- `docs/spec/quality-tooling.md` / `仕様書の検査対象` -> `1:test`
- `docs/spec/quality-tooling.md` / `実行経路` -> `1:test`
- `docs/spec/quality-tooling.md` / `失敗時の扱い` -> `1:test`
- `docs/spec/quality-tooling.md` / `Pythonの構造規則` -> `2:check`
- `docs/spec/quality-tooling.md` / `runtimeリファクタリング` -> `2:check`
- `docs/spec/quality-tooling.md` / `runtimeリファクタリング` -> `3:check`
- `docs/spec/quality-tooling.md` / `runtimeリファクタリング` -> `4:check`
- `docs/spec/quality-tooling.md` / `Pythonの検査対象` -> `5:check`
- `docs/spec/quality-tooling.md` / `Pythonの構造規則` -> `5:check`
- `docs/spec/quality-tooling.md` / `実行経路` -> `5:check`
- `docs/spec/quality-tooling.md` / `失敗時の扱い` -> `5:check`
- `docs/spec/distribution.md` / `実装単位` -> `5:check`

## 目的

現在はruntimeの振る舞いを137件のテストで確認できますが、正本全体をPylintとstrict mypyへ
通すと多数の違反が残ります。このplanでは、品質ゲートがコミット対象を正しく検査する契約を
先に固定し、既存の振る舞いを維持したままruntimeを機械検査へ適合させます。

振る舞いを追加する品質ゲートの変更だけは、反例を先に失敗させるRED、最小実装のGREEN、整理後の
REFACTORで進めます。runtime本体は振る舞いを変えないため、新しい失敗する振る舞いテストを
形式的に作りません。既存テストを変更前からgreenに保ち、現在失敗しているPylintとmypyを構造上の
不足として観測してから、greenなテストの下でリファクタリングします。

配布manifest、README、GitHub Actions、release tagは後続planの対象です。新しい外部依存、保存形式、
eventの意味、公開CLI、人の判断境界も追加または変更しません。

## 設計方針

- JSONやGit出力は外部境界で検証し、型が確定した値だけを内部へ渡します。`Any`、`cast`、抑制行で
  型検査を迂回しません。
- 大きい手続きは、純粋な判定、Gitとfilesystem、保存、CLIの順に分離します。業務ロジックの再利用は
  継承ではなく、小さい関数と値の移譲・合成で行います。
- `implement_runtime.py`と`review_runtime.py`は既存利用者向けの薄いfacadeとして残します。内部を
  分割しても、公開関数、引数、終了code、JSON、保存pathを維持します。
- Pylintとmypyの設定は`tools/quality`に1つずつ置き、直接実行、Codex、Lefthookで同じ設定を使います。
  設定contract validatorが有効規則、禁止設定、対象root、実行commandを検査し、部分検査用に規則を
  弱めた別入口を拒否します。
- テストは責務単位のclassとfileへ分割します。テスト名で振る舞いを示し、前提や反例を名前だけでは
  誤解する場合に限ってコメントまたはdocstringを残します。
- 正本の変更後にagentic-skill-vendorで配布用scriptを生成します。配布先を直接直しません。
- 型付きJSON decoderは、配布contractをまたぐ共通moduleにしません。各正本fileまたは既存の配布単位
  内へ置き、単独で配布されたskillに隠れたimport依存を作りません。

## Scope

```text
tools/
  quality/
    agents/
      codex_stop.py
    plugins/
      design_checker.py
    tests/
      design_checker_test.py
      entrypoints_test.py
      lefthook_test.py
      quality_configuration_test.py
      quality_gate_test.py
      repository_snapshot_test.py
      spec_textlint_test.py
    checks.json
    configuration_contract.py
    mypy.ini
    project_paths.py
    pylint.rc
    quality_gate.py
    repository_snapshot.py
    spec_textlint.py
  workflow-runtime/
    brainstorm/
      draft.py
      state.py
    implement/
      runtime/
        __init__.py
        cli.py
        completion.py
        context.py
        deliverables.py
        deps.py
        documents.py
        events.py
        gates.py
        gitio.py
        planning.py
        repository.py
        resume.py
        safety.py
        secret_detect.py
        staging.py
        storage.py
        tdd.py
        types.py
      implement_runtime.py
    plan/
      plan_artifact.py
    review/
      review_support/
        __init__.py
        binding.py
        cli.py
        events.py
        findings.py
        repository.py
        types.py
        validation.py
      review_model.py
      review_runtime.py
    shared/
      git_status.py
      implementation_evidence.py
      path_safety.py
    tests/
      brainstorm_draft_test.py
      brainstorm_state_test.py
      facade_contract_test.py
      implement_binding_test.py
      implement_evidence_test.py
      implement_event_test.py
      implement_runtime_test.py
      implement_safety_test.py
      implementation_evidence_test.py
      plan_artifact_test.py
      review_binding_test.py
      review_findings_test.py
      review_lifecycle_test.py
      review_model_test.py
      review_runtime_test.py
      vendor_entrypoints_test.py
skills/
  ba0918-brainstorm/
    scripts/
  ba0918-implement/
    scripts/
  ba0918-plan/
    scripts/
  ba0918-review/
    scripts/
vendor-lock.json
vendor-manifest.yaml
```

## Step 1: 品質ゲートへ正確な検査対象を渡す

目的は、worktree、Git index、全追跡対象の意味を入口から個別検査まで一貫させることです。
既存の品質ツールunit testを前提に、Git repositoryを一時作成する実物寄りのテストを追加します。

REDでは、少なくとも次の反例を先に失敗させます。

- Pythonを部分ステージングし、worktreeだけを修正してもindex側の違反を見逃さない
- worktree、index、全追跡対象の各scopeで、Python正本のsymlinkや非通常fileを拒否する
- clean checkoutの全追跡範囲が空の検査として成功しない
- repository直下以外から起動しても、同じ正本と設定を選ぶ
- snapshotの作成、設定の読込み、検査器の起動に失敗した場合を成功扱いしない
- 仕様書のworktree、index、全追跡対象が、それぞれ変更候補、index本文、追跡済み本文を選び、
  各scopeでsymlinkやfile-type changeを通常fileとして受理しない
- 共通CLI、Codex変換処理、Lefthookが同じ共通検査へ到達する

GREENでは、Git indexを一時directoryへcheckoutする処理と通常ファイル検査を
`repository_snapshot.py`へ集約します。共通CLIはscopeに対応するsnapshotを作って各検査を起動し、
個別検査は渡されたrootとscopeだけを使います。`all`を公開scopeへ追加します。Codex固有処理は結果の
JSON変換だけに保ちます。

REFACTORでは、Git subprocess、path mode、temporary directoryの責務が品質ゲートと文章検査へ
重複していないかを確認します。利用者のindex、worktree、設定を変更してはいけません。

直接検証は、上記反例が既存の共通CLIと各入口を通るintegration寄りのunit testです。実Git以外へ
置き換えるとindexとworktreeの差を証明できないため、Git subprocessはmockしません。

実装側に任せるのは、snapshot valueの内部型とtemporary directory内の名前だけです。indexを安全に
再現できない、新しいGit依存以外の外部ツールが必要、または利用者のindex変更が必要になった場合は
実装せずbrainstormへ戻します。

## Step 2: 型と構造の基礎を小さいruntimeへ通す

目的は、品質ツール自身とbrainstorm、plan、shared、review modelの境界型を確定し、後続の大きい
runtimeが使える部品を作ることです。変更前後で関連する既存テストを成功させたままにします。

最初に、最終Pylint設定がfatal、error、warning、命名、禁止名、複雑度、重複、公開メソッド数、
祖先数、独自設計規則を検出することを小さいfixtureで確認します。同時に、一律docstring、行長、
最小公開メソッド数、インスタンス属性数を誤って強制しないことも確認します。strict mypyについても、
型なし関数と不正なreturnを持つfixtureが失敗することを確認します。

設定contract validatorは、Pylintの有効規則、strict mypy、`tools/quality`と
`tools/workflow-runtime`の両root、設定file、plugin、共通CLIのcheck集合を正本として検査します。
`ignore_errors`、per-module override、canonical rootを隠すexclude、inline suppression、規則または
対象rootの欠落、同じ検査を弱い引数で呼ぶ別入口を反例として拒否します。validator自体を共通CLIが
必ず実行するため、設定を弱めてから同じ品質ゲートをgreenにする経路を残しません。

その後、対象moduleのPylintとmypy失敗を観測し、配布単位内のJSON boundary decoder、具体的な結果型、
小さい純粋関数へ置き換えます。

継承は例外階層やPylint拡張点などの境界用途だけに残し、処理の共有には使いません。テストclassは
責務単位に分け、公開メソッド数違反を単なる名前変更で隠しません。公開contract、Markdown形式、
Git操作、error codeは維持します。

**Checks:**

- `python3 -m unittest discover -s tools/quality/tests -p '*_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'brainstorm*_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'plan*_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'implementation_evidence_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'review_model_test.py'`
- `PYTHONPATH=tools/quality:tools/workflow-runtime/implement:tools/workflow-runtime/review:tools/workflow-runtime/shared UV_CACHE_DIR=/tmp/agentic-workflow-uv-cache uv run --with pylint==4.0.5 python -m pylint --rcfile=tools/quality/pylint.rc tools/quality tools/workflow-runtime/brainstorm tools/workflow-runtime/plan tools/workflow-runtime/shared tools/workflow-runtime/review/review_model.py`
- `UV_CACHE_DIR=/tmp/agentic-workflow-uv-cache uv run --with mypy==1.18.2 mypy --config-file tools/quality/mypy.ini tools/quality tools/workflow-runtime/brainstorm tools/workflow-runtime/plan tools/workflow-runtime/shared tools/workflow-runtime/review/review_model.py`

新しい型を表すために保存JSONを変更する必要がある、既存error codeを変える必要がある、または
外部依存が必要になった場合は止めてbrainstormへ戻します。安全なhelperやtest fileのScope漏れは
理由を記録して止まらず補います。

## Step 3: implement runtimeを移譲可能な責務へ分ける

目的は、event検証、完了導出、文書追従、安全検査、Gitとfilesystemを`context.py`から分離し、
CLIとfacadeから合成することです。既存のimplement関連テストを変更前に成功させ、以後の各抽出でも
同じテストを成功させます。

production codeを分割する前に、`implement_runtime.py`の公開symbolである`Run`、`RuntimeFailure`、
`RuntimeResult`、`locate_plan`、`plan_candidates`、`resolve_plan`、`bind_run`、`append_event`、
`load_events`、`freeze_test`、`frozen_test_matches`、`main`の存在と`inspect.signature`を
characterization testで固定します。代表CLIの終了code、stdout、stderr、bindingとeventの保存path・
JSON bytesも既存fixtureから固定し、内部の私有helperまでは互換対象にしません。

`context.py`は公開関数を保つ薄いfacadeとし、内部は値を受け取る純粋な判定から先に抽出します。
I/Oは既存のstorage、repository、gitioへ寄せます。依存を引数で渡せる境界は移譲し、基底classは
作りません。循環importを遅延importで隠さず、依存方向そのものを一方向へ直します。

テストはbinding、event遷移、安全検査、resume、CLIの責務へ分けます。既存の観測可能な正常系と
反例を移動してから元の重複を削除し、assertionを弱めません。型合わせのための部分mockやtest専用の
production APIは追加しません。

**Checks:**

- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'implement*_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'implementation_evidence_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'facade_contract_test.py'`
- `PYTHONPATH=tools/quality:tools/workflow-runtime/implement:tools/workflow-runtime/review:tools/workflow-runtime/shared UV_CACHE_DIR=/tmp/agentic-workflow-uv-cache uv run --with pylint==4.0.5 python -m pylint --rcfile=tools/quality/pylint.rc tools/workflow-runtime/implement tools/workflow-runtime/tests/implement_binding_test.py tools/workflow-runtime/tests/implement_evidence_test.py tools/workflow-runtime/tests/implement_event_test.py tools/workflow-runtime/tests/implement_runtime_test.py tools/workflow-runtime/tests/implement_safety_test.py tools/workflow-runtime/tests/implementation_evidence_test.py tools/workflow-runtime/tests/facade_contract_test.py`
- `UV_CACHE_DIR=/tmp/agentic-workflow-uv-cache uv run --with mypy==1.18.2 mypy --config-file tools/quality/mypy.ini tools/workflow-runtime/implement tools/workflow-runtime/tests/implement_binding_test.py tools/workflow-runtime/tests/implement_evidence_test.py tools/workflow-runtime/tests/implement_event_test.py tools/workflow-runtime/tests/implement_runtime_test.py tools/workflow-runtime/tests/implement_safety_test.py tools/workflow-runtime/tests/implementation_evidence_test.py`

公開関数、CLI、保存形式、event遷移、人の停止条件を変えないと分割できない場合は実装せず
brainstormへ戻します。内部function名や責務に沿うtest fileの追加は止まらず決めます。

## Step 4: review runtimeを独立した部品へ分ける

目的は、reviewの入力束縛、event保存、finding遷移、Git検査、CLIを1115行の
`review_runtime.py`から分離することです。外部から見える関数はfacadeで維持し、各部品を継承ではなく
明示的に合成します。

分割前に、facadeの公開結果型と`ok`、`failure`、`execution_binding`、`standalone_binding`、
`input_kind`、`choose_comparison_base`、`requires_full_review`、`resolve_input`、`review_directory`、
`append_event`、`load_events`、`bind_review`、`current_findings`、`record_second_review`、`begin_stage`、
`record_findings`、`close_finding`、`record_human_decision`、`record_targeted_result`、`add_findings`、
`record_progress`、`mark_stale`、`rebound_findings`、`complete_review`、`load_review_binding`、`main`の存在と
`inspect.signature`をcharacterization testで固定します。代表CLIの終了code、stdout、stderr、binding、
event、findingの保存pathとJSON bytesも固定し、私有helperは互換対象にしません。

既存テストをbinding、finding、lifecycle、CLIへ先に移動し、移動の前後で全assertionが成功することを
確認します。次に、外部入力の検証と型付き値への変換、純粋な状態判断、repository I/Oの順に抽出します。
初回full review後に対象を絞る既存方針、finding数やevent数を打ち切らない契約、既存のsecurity境界を
変更してはいけません。

**Checks:**

- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'review*_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'facade_contract_test.py'`
- `PYTHONPATH=tools/quality:tools/workflow-runtime/implement:tools/workflow-runtime/review:tools/workflow-runtime/shared UV_CACHE_DIR=/tmp/agentic-workflow-uv-cache uv run --with pylint==4.0.5 python -m pylint --rcfile=tools/quality/pylint.rc tools/workflow-runtime/review tools/workflow-runtime/tests/review_binding_test.py tools/workflow-runtime/tests/review_findings_test.py tools/workflow-runtime/tests/review_lifecycle_test.py tools/workflow-runtime/tests/review_model_test.py tools/workflow-runtime/tests/review_runtime_test.py tools/workflow-runtime/tests/facade_contract_test.py`
- `UV_CACHE_DIR=/tmp/agentic-workflow-uv-cache uv run --with mypy==1.18.2 mypy --config-file tools/quality/mypy.ini tools/workflow-runtime/review tools/workflow-runtime/tests/review_binding_test.py tools/workflow-runtime/tests/review_findings_test.py tools/workflow-runtime/tests/review_lifecycle_test.py tools/workflow-runtime/tests/review_model_test.py tools/workflow-runtime/tests/review_runtime_test.py`

既存review event、finding schema、公開関数、CLI、保存pathを変える必要がある場合は止めてbrainstormへ
戻します。責務を正しく分けるための内部moduleやtest fileのScope漏れは止まらず補います。

## Step 5: 正本全体を同じ品質ゲートで証明する

目的は、正本、配布用複製、直接実行、Codex、Lefthookが同じ規則へ収束し、配布作業を混在させずに
runtime単位を完了させることです。

`vendor-manifest.yaml`ではimplementの既存`runtime/` directory mappingを維持し、reviewへ新しい
`review_support/`から`scripts/review_support/`へのdirectory mappingを追加します。型decoderは
brainstorm、plan、implement、reviewの各配布単位内へ置くため、新しい共有placementを作りません。
正本から各skillのscriptを生成し、lockとの一致とskillの自己完結性を確認します。

生成後は各skillを一時directoryへ単独でcopyし、brainstorm、implement、reviewのentry scriptは
`--help`まで、CLIを持たないplanと共有moduleはimportまで実行します。正本側のpathが偶然importを
満たす状態を避け、欠けたplacementを検出します。その後、runtimeと品質ツールの全テスト、全追跡範囲の
共通品質ゲートを実行します。設定contract validatorにより、抑制、対象除外、設定緩和、別入口を
機械的に拒否します。

**Checks:**

- `bunx agentic-skill-vendor gen`
- `bunx agentic-skill-vendor verify`
- `bunx agentic-skill-vendor lint-selfcontain`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p 'vendor_entrypoints_test.py'`
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'`
- `python3 -m unittest discover -s tools/quality/tests -p '*_test.py'`
- `python3 tools/quality/quality_gate.py --scope all`
- `git diff --check`
- `git diff --quiet "$(git merge-base HEAD main)"...HEAD -- .github .claude-plugin .opencode README.md CHANGELOG.md LICENSE package.json`

GitHub Actions、配布manifest、README、version、release tagは変更しません。最終検査に新しい外部依存が
必要、既存runtimeの振る舞いが失われる、または仕様の緩和が必要になった場合は完了扱いにせず
brainstormへ戻します。安全な配布複製やtest fileの漏れは理由を記録し、止まらずScopeへ補います。

## 完了条件

- 品質ゲートの新しい振る舞いは、意味のある反例を先に失敗させてから実装している
- runtimeの既存テストを減らさず、責務分割の前後で全件成功している
- Pylintの合意済み規則とstrict mypyが`tools/quality`と`tools/workflow-runtime`の正本全体で成功する
- 設定contract testがPylint・mypyの規則緩和、対象欠落、除外、override、別入口を拒否している
- worktree、部分ステージングされたindex、全追跡対象、非通常ファイル、検査器失敗を独立して検証している
- 業務ロジックを共有する新しい継承、lint抑制、型回避、対象除外、別名の検査入口を追加していない
- 正本とskill配布用scriptが一致し、既存の公開CLI、JSON、保存形式、event、人の判断境界が変わっていない
- 単独copyした各skillでentry scriptと配布moduleを読み込める
- 配布・リリース作業が差分へ混在していない

## 実装中に人へ返す条件

新しい外部依存、公開CLIや保存形式の変更、eventまたはfindingの意味変更、人の判断境界の変更、
Git indexを安全に再現できない問題、または仕様に無い重要な設計判断が必要になった場合だけ人へ返します。
安全なhelper、test file、vendor配置の漏れ、内部module名など、大筋を変えない判断では止まりません。
