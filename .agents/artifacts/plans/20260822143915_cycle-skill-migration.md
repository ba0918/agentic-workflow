# Cycle skillの移行

**Plan ID:** `20260822143915`  
**Plan revision:** `1`  
**作成日時:** 2026-08-22 14:39:15 JST  
**対象仕様:**

- `docs/spec/agentic-workflow.md`
  - 内容identity: `sha256:bf8964ceb45b18cf04c890619d73eec098d52bd8b4a37fcbd4f721a2286f5c59`
  - 適用条項: `WF-001`〜`WF-003`、`WF-020`〜`WF-025`、`WF-060`〜`WF-075`、`WF-080`〜`WF-085`、`WF-089`〜`WF-094`、`WF-100`〜`WF-104`、`WF-130`〜`WF-136`、`WF-150`〜`WF-152`、`WF-160`〜`WF-161`、`WF-170`〜`WF-174`、`WF-180`〜`WF-181`、`WF-183`、`WF-185`、`WF-187`〜`WF-188`、`WF-190`〜`WF-191`、`WF-204`〜`WF-205`、`WF-207`
- `docs/spec/plan-skill-migration.md`
  - 内容identity: `sha256:1eb5a91519529937548dadb62211dceb5b2a161acd0576e0705723879081b75e`
  - 適用条項: `PL-020`〜`PL-023`、`PL-040`〜`PL-042`、`PL-050`〜`PL-056`、`PL-060`〜`PL-064`、`PL-070`〜`PL-071`
- `docs/spec/cycle-skill-migration.md`
  - 内容identity: `sha256:984080810d9b1aad9f0c7dc28747f0cbbf2ad0dd3b34b62486563ca02e67361b`
  - 適用条項: `CY-000`〜`CY-004`、`CY-010`〜`CY-013`、`CY-020`〜`CY-025`、`CY-030`〜`CY-034`、`CY-040`〜`CY-043`、`CY-050`〜`CY-057`、`CY-060`〜`CY-065`、`CY-070`〜`CY-073`、`CY-080`〜`CY-083`、`CY-090`〜`CY-095`、`CY-100`〜`CY-102`、`CY-110`〜`CY-116`

**実装境界資料:**

- `ROADMAP.md`
  - 内容identity: `sha256:d396cd90126aaddbbcad10574b7c417d20f1b074845298654dfbbc9dc353752e`
- 移行元: `claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`
- Phase 1とPhase 2の仕様、plan、実装、acceptance、比較、失敗分析

## 目的

承認済みplanを、軽量タスクを含め常に専用branchとlinked worktreeへ隔離し、現在の実行agentがRED、GREEN、REFACTOR、commitまで直接実行する`ba0918-cycle`を作る。

Phase 3の正常到達は`implementation_green`であり、plan全体の完了ではない。review、fix loop、final gate、復旧、再開、cleanupは実装せず、同じbranch、worktree、commit、immutable evidenceをPhase 4へ引き渡す。

## 利用者が得る結果

- 明示path、直前のpublication結果、正常なcurrent locatorの順でplanを安全に解決できる。
- main checkoutの未commit変更を混ぜず、base HEADから作ったlinked worktreeだけで実装できる。
- 未実装の期待契約によるREDだけを受理し、基盤故障やidentity driftではproduction変更前に停止できる。
- 各stepのRED、GREEN、REFACTOR、commitを、上書き不能なeventとGit状態から検証できる。
- compactやfresh sessionの後も、会話履歴ではなくplan、spec、binding、eventから同じgateを再構成できる。
- 停止時もworktree、commit、確定済みevidenceを保持し、Phase 5が推測せず扱える。

## 実装開始条件

このplanの正本化だけでは実装開始を許可しない。実装前に、次をすべて満たす。

- 人間が別途「実装して」などの開始指示を出している。
- 対象三仕様の上記identityが、実行base HEADから読める。
- 現在未commitの`docs/spec/cycle-skill-migration.md`と`ROADMAP.md`は、projectのcommit ruleに従う別のcommit操作で正本化されている。
- main checkoutの`.agents/artifacts/plans/open-plans.json`がこのplanを唯一の`current`として示し、plan bytesとidentityが一致する。
- repository単位の既存Cycle claimがない。

仕様またはROADMAPのcommit、planの正本化はCycle自身の責務に含めない。開始条件を満たさない場合はattemptを作らず停止する。

## 変更するもの

```text
skills/ba0918-plan/scripts/
  plan_artifact.py

skills/ba0918-cycle/
  SKILL.md
  references/
    execution.md
    tdd.md
    evidence.md
  scripts/
    execution_model.py
    cycle_runtime.py

tests/
  plan_artifact_test.py
  cycle_execution_model_test.py
  cycle_runtime_test.py

evals/cases/ba0918-cycle/
  complete-approved-plan.yaml
  stop-on-spec-drift.yaml
  reject-unintended-red.yaml

evals/inputs/ba0918-cycle/
  （三scenarioのfixture repositoryを構成する最小file群）

regression-lock.json
```

`plan_artifact.py`の変更は、Planが所有するlocator schemaをCycle側へ複製しないための、読取り専用consumer interfaceに限定する。publication、revision、切替の既存動作は変えない。

実装中に別fileが必要になった場合は、上記責務で表せない理由と影響をplan revisionとして人間へ提示する。

## 変更しないもの

- 承認済みspec、正本plan、`ROADMAP.md`の意味と進捗表示
- `ba0918-brainstorm`と`ba0918-plan`の利用者向けworkflow
- review policy、reviewer起動、finding、fix loop、final gate
- resume、checkpoint、Recovery、claim回収、rebind、worktree cleanup
- dependency解析による失敗後の部分継続
- parallel cycle、merge、publication、issue、PR、release
- `status.md`、`session-history.md`、`plans/progress`
- legacy plan、旧cycle、旧artifactとの後方互換
- 既存の無関係な`.claude`

## 外部への影響

- skillの通常実行はGit branch、linked worktree、step単位commitを作成する。
- main checkout側の`.agents/artifacts/executions`、`.agents/runtime/cycles`、`.agents/tmp/cycles`へ書き込む。
- claim、worktree、branch、evidenceは`implementation_green`または停止後も自動削除しない。
- 実process受入では一時fixture repositoryと許可済みの低コストbackendを使う。利用不能なbackendを完了条件にせず、未許可のnetwork、dependency導入、外部service操作は行わない。
- 新しい外部packageは追加せず、Python標準library、Git、既存のproject test toolchainを使用する。
- 実repositoryのmain branchへのmerge、push、PR作成は行わない。

## 設計

### Skillとreference

`SKILL.md`はtrigger、責務境界、段階ごとのreference routing、完了条件だけを持つ。

- `execution.md`: plan解決、claim、worktree bootstrap、境界再検証、停止と引渡し
- `tdd.md`: oracle解決、RED、GREEN、REFACTOR、step単位commit
- `evidence.md`: binding、immutable event、result導出、permissionと永続化失敗

現在の段階に必要なreferenceだけを読み、通常経路でも旧cycleのreview、Recovery、publication契約を読み込まない。内部でsubagentを起動せず、外側のrunnerがfresh sessionを開始することだけを許容する。

### 決定的helper

決定的処理を二層に分ける。

- `execution_model.py`は、pathとidentity、binding、event schema、hash chain、state transition、oracle binding、result導出を副作用なしで検証する。
- `cycle_runtime.py`は、Git metadata、filesystem、process実行を境界adapterとして扱い、modelを呼び出す。clock、attempt ID生成、process runner、filesystem境界はtestから差し替え可能にする。

Plan locatorのschema検証は`plan_artifact.py`が所有する公開読取りinterfaceを再利用する。Cycleは候補の優先順位とCycle固有のregistration整合だけを所有する。汎用workflow runtimeまたは共有packageは作らない。

### 実行状態

- main checkout側の`.agents/runtime/cycles/current.claim`を排他的に作成し、一repository一通常Cycleに限定する。
- attempt IDはhelperが生成し、path-safeかつ各storeで未使用であることを確認する。
- immutable `binding.json`をcanonical execution directoryへ確定してからbranchとworktreeを作る。
- Gitが報告するmain checkout、common directory、base HEAD、branch、linked worktree identityを再検証し、`worktree-bound` event後だけtest編集を許可する。
- 一event一fileをatomicに確定し、連番、直前identity、自身のcontent identityでhash chainを作る。
- resultはevent列から導出し、第二のresult正本を作らない。
- claimとartifactの寿命判断、cleanup、resumeはPhase 5へ残す。

### TDDとcommit

各plan stepで次を行う。

1. planの意味oracleから実行command、cwd、environment名、timeoutを一意に解決する。
2. testを先に書き、未実装の期待理由によるREDを確認してoracle bindingを凍結する。
3. 最小のproduction変更で同じoracleをGREENにする。
4. 同じoracleを保持したまま必要なREFACTORを行う。変更不要なら理由をeventへ残す。
5. identity、write scope、staging内容、hook、post-commit dirtinessを確認し、一concern単位でcommitする。

新しい挙動には新しいREDを要求する。受理済みtest、fixture、commandの変更、意図しないRED、hook変更、scope外変更、意味不足を検出した場合は後続stepへ進まず停止する。

commit messageと分割はproject固有ruleを優先し、global ruleをfallbackにする。fileを個別にstageし、`git add .`と`git add -A`、hook無効化、commit専用agentへの移譲を禁止する。

## 再利用判断

| 層 | 判断 | 理由 |
|---|---|---|
| locator schema | `plan_artifact.py`を拡張して再利用 | schema ownerを一つに保ち、Cycle側のvalidator複製を避ける |
| content identityとatomic write | Phase 1・2の検証済みパターンを採用 | Python標準libraryだけで決定性、symlink拒否、部分書込み防止を実現できる |
| Git identity | Gitの`rev-parse`、`worktree list --porcelain`等をadapter越しに使用 | pathや環境変数の推測よりrepository、common directory、worktree関係を機械検証できる |
| state machine | Cycle固有の小さなmodelを作る | 汎用workflow stateやPhase 5 Recoveryを先取りせず、許可遷移だけをtestできる |
| test runner | plan、project指示、既存script、標準toolの順に既存commandを利用 | Cycle独自test frameworkや依存を追加しない |
| unit test | Python標準`unittest`を使用 | 現在のPhase 1・2と同じtoolchainで、filesystemとGitを一時directory内に隔離できる |
| skill regression | 既存のeval caseと`regression-lock.json`を使用 | 三つの利用者scenarioと旧版比較を既存形式へ載せられる |
| raw logs | 再利用・複製しない | provider側のexecutor/session IDへ安全に辿り、durable evidenceは判定に必要なbounded summaryへ限定する |
| worktree cleanupとresume | 実装しない | Phase 5の寿命・Recovery責務を侵食する |

## 実装手順

### 1. Plan locatorの読取り契約を公開する

**対応仕様:** `CY-010`〜`CY-013`、`PL-053`〜`PL-064`  
**先行項目:** 実装開始条件  
**期待成果物:** Cycleが再利用できる、path・revision・content identity・stateを検証済みで返す読取り専用interface

**書込み範囲:**

```text
skills/ba0918-plan/scripts/plan_artifact.py
tests/plan_artifact_test.py
```

**行うこと:**

- malformed、unknown field、current pointer不整合、unsafe path、plan bytesとのidentity不一致を拒否するtestを先に追加し、期待理由でREDを確認する。
- 既存の内部index validatorとpath validatorを用いて、locator entryとplan bytesを副作用なく読める公開interfaceを追加する。
- locator不在を空indexとして扱うpublication契約は変えず、Cycle consumerではregistration不在を区別できる戻り値にする。
- 読取りでplan、index、status、session historyを一切変更しない。
- 既存publication testを同じcommandで再実行し、回帰がないことを確認する。

**必要証拠:**

- 新testの期待REDとGREEN
- 既存`plan_artifact_test.py`全件GREEN
- 不正入力時のfile tree非変更
- 公開interfaceがprivate implementationの複製を持たない静的確認

**実装へ委任する判断:** 公開関数名と戻り値のPython型は、上記fieldとfailure区別を失わない最小形から選ぶ。新しいserialization形式は追加しない。

**停止条件:** 既存publication semanticsを変更しなければ安全なconsumer interfaceを作れない場合は、実装を止めplan revisionへ戻す。

### 2. Cycleのpure modelを実装する

**対応仕様:** `CY-011`、`CY-021`、`CY-031`〜`CY-033`、`CY-041`〜`CY-043`、`CY-050`〜`CY-065`、`CY-070`〜`CY-073`、`CY-081`、`CY-083`、`CY-095`、`CY-100`〜`CY-102`、`CY-110`

**先行項目:** 手順1  
**期待成果物:** identity drift、無効遷移、scope違反、staleまたは衝突したevidenceを副作用なしで拒否するmodel

**書込み範囲:**

```text
skills/ba0918-cycle/scripts/execution_model.py
tests/cycle_execution_model_test.py
```

**行うこと:**

- binding、event、oracle binding、resultのschemaと許可遷移をtestで先に固定し、module未実装または期待関数不在によるREDを確認する。
- canonical JSON bytesとSHA-256 content identityを一意に生成する。
- plan、spec、base HEAD、worktree、current step、write scope、oracle、delegationの期待identityと観測identityを比較する。
- event sequence、previous identity、event type別必須field、attempt IDを検証し、既存eventとの同一identity再試行だけを冪等成功にする。
- `not_started`、`stopped`、`implementation_green`をeventから導出する。
- secret値、absolute path、traversal、symlink alias、scope外pathをschemaへ受理しない。
- event数は観測値として数えられるが、停止条件や成功条件には使わない。

**必要証拠:**

- identityとserializationの決定性test
- 全identity drift、write scope、step/oracle欠落、event衝突、stale chainの拒否test
- 正常列と停止列からのresult導出test
- 拒否入力に対してmodelが副作用を持たないtest

**実装へ委任する判断:** schema内のfield順、bounded signatureの正規化方法、attempt IDの時刻表現とrandom suffix長は、決定性、path safety、fixtureでの衝突検査を満たす最小形から選ぶ。

**停止条件:** resultの導出にevent以外の第二の進捗状態が必要になる場合、またはPhase 5の再開状態を追加しなければ表現できない場合は実装を止める。

### 3. Claim、binding、worktree bootstrapを実装する

**対応仕様:** `CY-020`〜`CY-034`、`CY-040`〜`CY-043`、`CY-060`、`CY-080`〜`CY-083`、`CY-100`〜`CY-102`、`CY-110`

**先行項目:** 手順2  
**期待成果物:** main artifact rootへattemptをbindし、専用branchとlinked worktreeを安全に作るruntime adapter

**書込み範囲:**

```text
skills/ba0918-cycle/scripts/cycle_runtime.py
tests/cycle_runtime_test.py
```

**行うこと:**

- 一時Git repositoryを使い、既存claim、bare repository、submodule、偽worktree、dirty main持越し、attempt ID衝突、symlink、atomic write失敗、permission failureのtestを先にREDにする。
- plan候補を承認済み優先順で解決し、手順1のinterfaceでregistrationとidentityを検証する。
- Git metadataからmain checkout、common directory、base HEAD、linked worktree identityを取得する。
- canonical artifacts、runtime、tmp、Git管理領域をpreflightし、claimとattempt directoryを排他的に作る。
- immutable bindingを先に確定し、branchとworktree作成後に実identityを`worktree-bound` eventへ記録する。
- main checkoutの未commit変更をコピーせず、base HEADだけをworktreeへ展開する。
- bootstrap失敗時も作成済みworktree、claim、binding、eventを推測で削除しない。
- sandbox拒否を`permission_required`として凍結し、許可後は同一identity書込みだけを再試行する。`persistence_unavailable`との区別をtestする。

**必要証拠:**

- 一時repositoryでの正常bootstrap test
- repository identity、base HEAD、worktree identity、既存claimの拒否test
- main dirty fileがlinked worktreeへ現れないtest
- binding前にworktreeを作らず、`worktree-bound`前にtest書込みを許さない順序test
- atomic failureで部分artifactを正本扱いしないtest
- permission requiredとpersistence unavailableの分岐test
- 拒否後にproduction変更またはcommitがないGit証拠

**実装へ委任する判断:** branch名とworktree directory名は、attempt IDを含む衝突しないpath-safe形式から選ぶ。Git commandの組合せは上記identityを観測できる最小集合から選ぶ。

**停止条件:** main checkoutのcanonical artifact rootとlinked worktreeをGit metadataだけで一意に結び付けられない場合、permissionが得られない場合、または既存claimがある場合は追加書込みせず停止する。

### 4. TDD、event、commit境界を実装する

**対応仕様:** `CY-040`〜`CY-057`、`CY-061`〜`CY-065`、`CY-070`〜`CY-095`、`CY-100`〜`CY-102`、`CY-110`

**先行項目:** 手順3  
**期待成果物:** 同じoracleをREDからREFACTOR後まで保持し、step内の一concern単位commitとimmutable eventを確定するruntime

**書込み範囲:**

```text
skills/ba0918-cycle/scripts/cycle_runtime.py
tests/cycle_runtime_test.py
```

**行うこと:**

- fake process runnerと一時Git repositoryで、oracle解決の曖昧性、意図しないRED、oracle弱化、identity drift、scope外stage、hook failure、post-commit dirty、event衝突を先にREDにする。
- commandをplan、project指示または既存script、標準toolの一意検出の順に解決する。
- cwd、environment名、timeout、expected failure kind、bounded signatureをRED受理時に凍結する。
- RED前、GREEN前後、REFACTOR前後、commit前後に正本identityとwrite scopeを再検証する。
- command output全体を保存せず、合否、pass/fail/skip数、exit code、bounded signatureだけをeventへ記録する。
- fileを個別stageし、scope外、secret、runtime、log、cache、build生成物を除外する。hookを有効にしたままproject/global commit ruleへ従う。
- blocking failureでは`stopped` eventを確定し、後続stepの独立性を解析せず全体を停止する。
- 全stepが同じ正本に対してGREEN、必要なREFACTOR、commit済みで、evidenceが確定した場合だけ`implementation_green` eventを作る。

**必要証拠:**

- 正常なRED→GREEN→REFACTOR→commit event chainのtest
- infrastructure、import、fixture、permission、network failureを期待REDとして拒否するtest
- specを変更するRED commandがproduction変更前に停止するtest
- oracle変更、identity drift、scope外stage、hook failure、post-commit dirtyの停止test
- commit SHAとstaging対象がevent・Git状態に一致するtest
- raw logとsecret値がartifact、result、commit messageへ入らないtest
- persistence failure時に`implementation_green`を返さないtest

**実装へ委任する判断:** projectに複数の同等oracle候補がない場合の標準tool検出表と、fixture実測に基づく固定timeout値は実装時に選べる。候補が複数または根拠がない場合は人間gateへ送る。

**停止条件:** 受理済みoracleを変更する必要がある、未合意の製品判断・network・dependency・外部操作が必要、hookまたはcommitが失敗、identity driftを検出、evidenceを確定できない場合は自動fixやretryをせず停止する。sandbox permissionだけは仕様どおり限定再試行できる。

### 5. Human-facing Cycle skillを実装する

**対応仕様:** `CY-001`〜`CY-004`、`CY-010`〜`CY-013`、`CY-040`〜`CY-043`、`CY-050`〜`CY-057`、`CY-070`〜`CY-095`、`CY-116`、`WF-066`〜`WF-068`、`WF-130`〜`WF-136`

**先行項目:** 手順4  
**期待成果物:** 一つの`ba0918-cycle`入口から、必要なreferenceだけを読み、現在のagentが直接helperとTDDを実行するskill

**書込み範囲:**

```text
skills/ba0918-cycle/SKILL.md
skills/ba0918-cycle/references/execution.md
skills/ba0918-cycle/references/tdd.md
skills/ba0918-cycle/references/evidence.md
```

**行うこと:**

- trigger、責務境界、段階別routing、開始条件、停止時と正常時の返却を英語の短い`SKILL.md`へ置く。
- plan解決、bootstrap、TDD、evidenceを各referenceへ分離し、同じ規範を複製しない。
- plan_pathが明示されなくても状況証拠から候補を導出し、機械検証後に一意なら質問せず進む。導出不能、競合、曖昧性だけを人間へ確認する。
- compact自体では停止せず、正本から意味を再構成できない場合またはidentity不一致だけで止める。
- nested implementation subagent、review、fix loop、final gate、resume、Recovery、cleanup、parallel、merge、publication、issue、status更新をtriggerまたは内部fallbackとして持たせない。
- 人間向け進捗と最終返却は日本語で、内部schema名だけを説明の代用にしない。

**必要証拠:**

- repository validatorとMarkdown参照検査の成功
- 通常経路が段階に応じたreferenceだけを読む静的確認
- 旧責務と禁止fallbackが新skillへ残っていない検索結果
- helperのfailure kindとskillの停止・返却表現の対応表検査
- reviewまたはsubagentを起動しないことのfixture期待値

**実装へ委任する判断:** reference内の見出しと説明順は、通常実行時の再読範囲を最小化しつつ責務重複を作らない形から選ぶ。

**停止条件:** 正常経路にPhase 4またはPhase 5の規範を読み込まなければ実行できない場合、責務分離を見直すまで停止する。

### 6. Unit、実agent E2E、旧版比較を完了する

**対応仕様:** `CY-110`〜`CY-116`、`WF-170`〜`WF-174`、`WF-204`、`WF-207`

**先行項目:** 手順5  
**期待成果物:** 正常完走と二つの安全停止を事後状態で区別できる回帰fixture、および現在のbehavior surface lock

**書込み範囲:**

```text
evals/cases/ba0918-cycle/
evals/inputs/ba0918-cycle/
regression-lock.json
```

失敗を修正するproduction変更はこの手順の書込み範囲に含めない。E2Eでskillまたはhelperの欠陥が見つかった場合、PASSへ書き換えず全体を停止し、影響する前手順の新しいREDから再開する。

**行うこと:**

- 三scenarioのcase、fixture repository、critical expectationを先にschema検証する。
- 正常scenarioでは、小さな承認済みplanをfresh sessionで解決し、専用worktree内の実変更、期待RED、GREEN、REFACTOR判断、step commit、`implementation_green`まで完走させる。
- identity drift scenarioでは、RED command自身がfixtureの承認済みspecを変更し、production fileとcommitがない状態で停止することを確認する。
- unintended RED scenarioでは、fixture、importまたは検証基盤のfailureを発生させ、production fileとcommitがない状態で停止することを確認する。
- agentの自己申告ではなく、main checkout、linked worktree、branch、commit、claim、binding、event chainを事後検査する。
- 正常と停止scenarioを対にし、常に停止するguardrailをPASSにしない。
- 強制compactは行わず、会話履歴を持たないfresh sessionが正本artifactだけから同じgateを実行できることを確認する。
- 最初の実測は許可済みの`opencode --auto`低コストbackend一つに限定する。Codexを追加で使う場合は明示許可後に`gpt-5.6-luna`だけを使う。
- 固定revisionの旧版と同じ入力で、要求充足、重大な漏れ、質問数、操作数、tool call、再読範囲、token、実行時間を比較する。
- 全critical expectationと構造検査が成功した場合だけ`regression-lock.json`へsurface、file hash、scenario結果、backend、測定日を登録する。

**必要証拠:**

- `python3 -m unittest discover -s tests -p '*_test.py'`の全件GREEN
- `python3 /home/mizumi/develop/claude-skills/scripts/validate_repo.py .`の成功
- 三fixtureのschema検証成功
- 各scenarioのfile・Git・evidence事後検査結果
- 正常scenarioの`implementation_green` eventとstep commit
- 二停止scenarioのreason、最後のsequence、production変更なし、commitなし
- fresh sessionの会話履歴非依存証拠
- 旧版との品質・操作・token・時間比較
- `regression-lock.json`のfreshness、coverage、hash整合

**人間gate:** backend、network、credential、sandbox権限が現在の許可範囲を超える場合だけ、対象と影響を示して確認する。利用不能なbackendを理由に別backendへ無断変更しない。

**停止条件:** 一つでもcritical expectation、unit test、repository validation、identity照合に失敗した場合、または正常scenarioと停止scenarioをfile・Git・evidenceから区別できない場合は`regression-lock.json`をPASSにせず停止する。

## Test一覧

### Plan解決と開始拒否

- 明示path、直前publication、current locatorの優先順位が一意に働く。
- 候補なし、複数候補、identity競合だけを人間確認へ送る。
- locator不在、不整合、unsafe path、planまたはspec identity不一致をattempt前に拒否する。
- base HEADに承認済みspec identityが存在しない場合、書込み前に拒否する。
- bare repository、submodule、偽linked worktree、既存claimを拒否する。

### 隔離とbootstrap

- 軽量タスクでもlinked worktreeを使い、in-place fallbackを持たない。
- main checkoutのdirty fileをworktreeへコピーしない。
- binding、branch、worktree、eventの作成順を守る。
- attempt ID、claim、directory、eventの衝突を上書きしない。
- bootstrap失敗後のworktree、claim、evidenceを推測で削除しない。

### TDDと逸脱防止

- 未実装の期待理由だけをREDとして受理する。
- timeout、command不在、dependency、import、collection、fixture、permission、network、既存failureを期待REDにしない。
- REDからREFACTOR後まで同じoracleを保持する。
- 新しい挙動の前に新しいREDを要求する。
- plan、spec、worktree、base HEAD、step、scope、oracle、delegation driftを各境界で拒否する。
- compact自体では止めず、正本を再構成不能または不一致の場合だけ止める。
- blocking failure後に後続stepへ進まない。

### Evidence、permission、result

- bindingとeventがcanonical bytes、atomic write、hash chainを持つ。
- 同一identityのpermission再試行だけが冪等成功する。
- permission requiredとpersistence unavailableを区別する。
- raw stdout、stderr、provider log、secret値を保存しない。
- provider provenance取得不能だけではGREENを妨げない。
- evidence未確定時は成功を宣言しない。
- resultはeventから`not_started`、`stopped`、`implementation_green`を導出する。
- event数をhard limitまたは停止oracleにしない。

### Commitと責務境界

- project commit ruleを優先し、一concern一commit、step跨ぎなし、個別stageを守る。
- hook失敗、hook変更、post-commit dirtyで自動retryせず停止する。
- scope外、secret、runtime、log、cache、生成物をcommitしない。
- review、fix loop、final gate、Recovery、cleanup、parallel、merge、publication、issueを実行しない。
- plan、locator、status、session history、plan progressを進捗目的で変更しない。
- Phase 3の正常結果をplan完了と呼ばない。

## 主要risk

- 現在のspec差分がbase HEADにないrisk  
  実装開始条件でcommit済みidentityを要求し、dirty mainのコピーで回避しない。
- `.agents`がlinked worktreeへ自動配置されないrisk  
  main checkoutのcanonical artifact rootをGit metadataでbindし、worktree側に複製しない。
- Plan locator validatorが二重化するrisk  
  Plan helperの読取り専用interfaceを使い、Cycleはschemaを再定義しない。
- helperが汎用runtimeへ肥大化するrisk  
  pure Cycle modelとGit/filesystem adapterの二層だけに限定し、Recoveryやreview状態を入れない。
- sandbox拒否を永続化不能と誤判定するrisk  
  permission requiredを先に扱い、同一identityの限定再試行と真のpersistence unavailableを分離する。
- eventの部分書込みまたは競合を成功扱いするrisk  
  一event一file、exclusive create、atomic rename、hash chain、読戻しidentity確認を要求する。
- guardrailが常時停止して見かけ上安全になるrisk  
  正常・drift・unintended REDを正負の対として実agentで判定する。
- claimとworktreeが残り後続実行を塞ぐrisk  
  これはPhase 4への引渡しとPhase 5 Recoveryの意図した契約であり、Phase 3で自動回収しない。
- raw logまたはcredentialがevidenceへ混入するrisk  
  bounded summaryと安全なprovenance IDだけを保存し、秘密を含むcommandは実行前に停止する。
- E2Eの自己申告だけでPASSするrisk  
  fixture外からfile tree、Git、event chain、identityを事後判定する。

## 実装中の人間gate

次の場合だけ停止して人間判断を求める。

- plan候補またはoracle commandが一意に決まらない。
- 承認済みspecにない製品判断、許容差異、外部I/O、dependency追加が必要になる。
- scoped sandbox permission、network、credential、外部backendの新しい許可が必要になる。
- planの書込み範囲または手順を変更する必要がある。
- specの意味を変える必要がある。この場合はplan revisionではなくbrainstormへ戻す。

人間の回答で既存specにない意味をad hocに追加しない。identity drift、意図しないRED、hook失敗、commit失敗、persistence unavailableは自動継続せず、確定済み証拠を保持して停止する。

## Phase 3の完了境界

Phase 3は、全unit・静的検証と三つの実agent scenarioが成功し、旧版比較で重大な品質低下がなく、実装対象planの全stepがcommit済みで、最新eventが`implementation_green`になった時点までとする。

この時点でもplanはopenであり、repository単位claim、branch、linked worktree、commit、evidenceを保持する。review、修正、最終gate、plan完了、claim回収、worktree cleanup、mainへの反映はPhase 4以降の責務である。
