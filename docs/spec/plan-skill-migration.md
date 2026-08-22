# Plan skill移行仕様

## 目的

`PL-001` `ba0918-plan`は、承認済み仕様と検証契約を、不足した意味を補わず、
人間が内容を直接判断でき、後続工程が実装、停止、復旧、検証できる実行計画へ
変換しなければならない。

`PL-002` 本仕様は`docs/spec/agentic-workflow.md`を具体化する。両者が矛盾する場合は、
人間が矛盾を解消するまでplanを作成してはならない。

## 入力と拒否条件

`PL-010` planの入力は、適用する承認済み仕様revisionと条項、条項ごとの観測可能な
成功条件、反例または既知の失敗、検証方法、必要な人間gateを識別しなければならない。

`PL-011` blockingな未決定事項、証拠不足、依存関係不明、未完了のsource audit、
未合意の配布、実行、永続化、外部I/O、完了oracleがある場合、plan作成前に拒否し、
不足した意味をbrainstormへ戻さなければならない。

`PL-012` planは関連specを内容から推測して自動選択してはならない。brainstormまたは
人間が明示した仕様集合だけを入力として使用しなければならない。

## 正本plan

`PL-020` 各plan項目は、対応する仕様条項、検証契約、判断依存、先行項目、期待成果物、
書込み範囲、必要証拠、委任権限を識別しなければならない。

`PL-021` 正本plan全体は現在の利用者の言語で記述しなければならない。安定ID、schema
field、code identifier、command、file pathは機械契約として英語のまま使用してよいが、
それらだけを人間向け説明の代わりにしてはならない。

`PL-022` 人間は正本planだけから、少なくとも次を判断できなければならない。

- planの目的と利用者が得る結果
- 変更するものと変更しないもの
- 各手順が必要な理由
- 外部影響と主要risk
- 各手順の完了証拠
- 人間判断が必要な場所
- 失敗時に停止する場所

`PL-023` planを、人間向けの概要とLLMだけが理解する規範的な高密度層へ分割しては
ならない。後続runnerは、人間が確認した同じ正本planを使用しなければならない。

`PL-024` 人間gateが必要なplan項目は、通常の人間向け説明に加えて、version付きの
機械可読なgate宣言を同じ正本plan内に持たなければならない。gate宣言は少なくとも、
plan内で一意な`gate_id`、対応仕様条項、判断基準、判断対象identityの取得元、
実行timing、許可される判断結果を識別しなければならない。

`PL-025` 判断対象identityの取得元は、repository-relativeなfile集合または既存の
immutable evidence identityから一意に導出できなければならない。absolute path、
provider log全体、credential、実行時に別対象へ差し替えられる参照を使用してはならない。

`PL-026` 許可される判断結果は`approved`と`rejected`に限定する。選択肢によって製品の
意味が変わる場合は人間gateとしてplanへ埋め込まず、brainstormで意味を決定しなければ
ならない。人間gateが不要なplan項目はgate宣言を省略してよい。

## 人間確認と正本化

`PL-030` plan skillは、正本へ書き込む内容と同一の草稿をchatで人間へ提示しなければ
ならない。草稿の要約だけを確認対象にしてはならない。

`PL-031` 人間が草稿を明示的に確認するまで、正本planを書き込み、未完了plan索引へ
登録してはならない。

`PL-032` 人間が確認した草稿と正本planは、同じ内容identityを持たなければならない。
書込み前後で内容が異なる場合、成功として扱ってはならない。

## Revisionと失効

`PL-040` 進捗記録のために正本plan本文を書き換えてはならない。実行または証拠に
結び付いたplan revisionをin-placeで変更してはならない。

`PL-041` specの意味を変えない実行手順の修正は、新しいplan revisionとして人間へ
再提示してよい。影響する古い実行証拠は失効させなければならない。

`PL-042` 製品上の意味、未合意の設計、禁止、許容差異、人間判断を変更する必要がある
場合、planを修正せずbrainstormへ戻さなければならない。承認済みspecの改訂後に、
影響するplanを新しいrevisionへ作り直さなければならない。

## 進捗と未完了plan

`PL-050` Planning、In Progress、Completedなどの手書きstatus、plan本文のcheckbox、
runnerの自己申告を進捗の正本にしてはならない。

`PL-051` plan項目の進捗は、そのplan revisionと対応仕様revisionに属する現在有効な
証拠から導出しなければならない。証拠がない項目は未完了として扱わなければならない。

`PL-052` 実装済みだが証拠記録がない場合、実装を推測で完了扱いせず、現在の実装へ
oracleを再実行して証拠を再構築できなければならない。

`PL-053` plan本体は作成時の安定pathに保持しなければならない。通常のresumeが完了済み
履歴全体を走査しないよう、未完了planだけを示す再構築可能な内部索引を使用しなければ
ならない。

`PL-054` 未完了plan索引が保持してよい情報は、plan ID、安定path、plan revisionまたは
内容identity、現在対象または保留中の区別に限定する。実際の工程、完了状態、証拠内容を
複製してはならない。

`PL-055` 完了証拠が揃ったplanは未完了plan索引から除外しなければならない。runnerが
除外を忘れた場合も、正本planと証拠を照合する次の操作で自己修復できなければならない。

`PL-056` `status.md`と`session-history.md`を作成または更新してはならない。履歴の正本は
plan本体、実装証拠、review finding、commit履歴とし、人間向け一覧が必要な場合はそれら
から生成しなければならない。

## Planの切替

`PL-060` 通常の実行対象は一件とするが、中断または保留された未完了planは複数存在して
よい。複数planの同時実行は`parallel-cycle`などの明示経路だけが所有する。

`PL-061` 新しいplanを現在対象にするとき、既存の現在対象planを無言で上書きしては
ならない。以前のplanを保留して切り替える内容を提示し、人間の明示確認を得なければ
ならない。

`PL-062` 保留と放棄を区別しなければならない。headless実行を理由に、既存planを自動で
abandonedまたはcompletedとしてはならない。

`PL-063` dirty worktreeに属する変更をcommit、checkpoint、別worktreeなどへ再開可能に
隔離できていない場合、明示確認があっても別planへの切替を停止しなければならない。

`PL-064` plan skillはbranchまたはworktreeを作成、切替、所有してはならない。planと
実行環境の結び付きはPhase 3のcycleが所有し、別planの変更または証拠を暗黙に持ち越しては
ならない。

## 責務境界

`PL-070` plan skillはresume、checkpoint、TDD、実装、証拠生成、完了判定、review、
doc-check、commit、branch操作、worktree操作、複数planの並列実行を所有してはならない。

`PL-071` 対象planが明確な場合を含むresumeはPhase 5のRecoveryが所有する。planはRecoveryが
推測せず再開地点を判定できる情報を持たなければならない。

`PL-072` callerが出力pathやstatus更新抑止を指定する旧caller-supplied modeをPhase 2へ
移植してはならない。旧brainstorm consumerは新brainstormの責務外となり、並列plan生成は
将来の`parallel-cycle`移行時に明示的なadapterとして再設計しなければならない。

## 受入条件

`PL-080` 一つの小規模fixtureを、全項目が仕様条項と検証条件へ追跡可能なplanへ変換できなければ
ならない。

`PL-081` 少なくとも次の失敗を固定fixtureで検出しなければならない。

- blockingな未決定事項を含む入力からplanを作る
- specまたは検証契約にない設計をplanで追加する
- 利用者が読めない言語またはLLM専用の規範層を持つplanを提示する
- 人間確認前に正本planまたは未完了plan索引を書き換える
- 人間が確認した草稿と異なる内容を正本化する
- 既存の現在対象planを無言で置き換える
- dirty worktreeから別planへ変更を持ち越す
- status自己申告だけでplan項目を完了扱いする
- plan revision変更後も古い証拠を有効扱いする

`PL-082` skill単体がAgent Skills標準検証を通り、対象clientへ単体配置した状態で、入力、
草稿提示、人間確認、正本書込み、内容identity確認、未完了索引登録までを実processで完走
しなければならない。

`PL-083` 旧版と同じ入力で、要求充足、重大な漏れ、質問数、操作数、tool呼出し、再読範囲、
入出力tokenを比較しなければならない。品質低下をtoken削減で相殺してはならない。

## Source audit

### Source

- `claude-skills` revision: `57bb6f06aecdf191d46d99d9a3283233a26ecfdd`
- `skills/plan/SKILL.md`
- `skills/plan/references/plan-template.md`
- `skills/plan/references/status-template.md`
- `skills/plan/references/status-update-guide.md`
- `skills/plan/fixtures.json`
- shared artifact store consumer/full contracts
- shared human-readable、execution-context、checkpoint、TDD、design contracts
- shared checkpoint、secret maskingのscriptsとtests
- Phase 1のspec、plan、実装、acceptance、旧版比較、失敗分析、token効率化資料

### Triggerと利用者価値

旧版はplan作成、status更新、汎用resumeを一つのskill triggerへ束ねていた。利用者価値は、
合意済み内容を実装手順へ変換することだが、statusとresumeの責務混在により、planがworkflow
全体の状態管理を所有しているように見える構造だった。

### 永続状態と人間gate

旧版はplan、`status.md`、`session-history.md`、checkpointを更新し、未完了sessionの処遇、
plan内容、resume時のcheckpoint削除提案を人間gateとしていた。headlessでは未完了sessionを
自動abandonedにする経路があり、保留と放棄を区別しなかった。

### Mechanical checksと既知の失敗

旧fixtureはplan作成、非ASCII slug、status完了遷移、checkpoint resumeを検証していたが、
spec条項への全項目追跡、人間が正本plan全体を読めること、確認前非書込み、証拠からの進捗導出、
dirty worktreeでのplan切替を検証していなかった。runnerがstatus更新を省略すると、表示と実態が
乖離し、復旧地点が自己申告へ依存した。

### Token costs

旧版はplan作成だけでもartifact store、human-readable、execution context、三つのtemplate、
status migrationを読み得た。resumeとstatus更新ではcheckpoint/TDD共有契約まで責務が広がり、
通常のplan変換に不要な再読を発生させた。

### Destination

| 旧責務 | 移行先 | 理由 |
|---|---|---|
| plan作成と手順revision | Phase 2 Plan | 承認済み意味を実行手順へ変換する中核価値 |
| statusとcheckbox | 廃止 | 証拠から導出できず、runnerの更新忘れで乖離する |
| session history | 廃止 | planと証拠の重複転記で、実利用でもほぼ参照されない |
| 未完了planの発見 | Phase 2の内部索引 | 履歴全走査を避けつつ正本から再構築できる |
| TDDと実装 | Phase 3 | 実行と証拠生成の責務 |
| branchとworktree | Phase 3 | planではなく実行環境の責務 |
| resumeとcheckpoint | Phase 5 Recovery | brainstorm、plan、cycle、reviewを横断する復旧責務 |
| parallel plan | `parallel-cycle`移行時 | 通常経路で実利用されておらず、明示的並列経路が所有する |
| caller-supplied mode | Phase 2では廃止 | consumerは旧brainstormとparallel-cycleであり、新brainstormはplan生成を所有しない |
| spec自動検出 | 廃止 | 適用仕様を内容推測せず明示的に受け取る |
| headless自動abandoned | 廃止 | 保留を無断で放棄へ変換する |

### Acceptance fixtureと除外する挙動

移行後も、完全な入力から質問を増やさず一つのplanを作る中核挙動は保持する。一方、status更新、
session-history、汎用resume、checkpoint、TDD、実装開始、spec自動検出、自動abandoned、
caller-supplied modeは、上表の責務分離または安全上の理由によりPhase 2の挙動から除外する。
