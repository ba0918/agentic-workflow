# Review skillの移行

**Plan ID:** `20260823133736`  
**Plan revision:** `1`  
**作成日時:** 2026-08-23 13:37:36 JST  
**公開先:** `.agents/artifacts/plans/20260823133736_review-skill-migration.md`

**対象仕様:**

- `docs/spec/review-skill-migration.md`（Phase 4固有の承認済み仕様）
  - 内容identity: `sha256:26ae1705b9f18307f592680319be7e8771e17bcda3523197ab3d37ae11a8f6f8`
  - 適用条項: `RV-000`〜`RV-006`、`RV-010`〜`RV-013`、`RV-020`〜`RV-026`、`RV-030`〜`RV-034`（`RV-031a`を含む）、`RV-035`〜`RV-039`、`RV-040`〜`RV-044`、`RV-050`〜`RV-052`、`RV-060`〜`RV-064`、`RV-070`〜`RV-075`、`RV-080`〜`RV-082`、`RV-090`〜`RV-091`、`RV-110`〜`RV-115`
- `docs/spec/agentic-workflow.md`（workflow全体の親仕様）
  - 内容identity: `sha256:b50e663b49847b597d1cf4ebce14fcd43c4943acd93da0b4cb30a1f14d3af883`
  - 適用条項: `WF-104`、`WF-110`〜`WF-115`、`WF-120`〜`WF-124`、`WF-160`、`WF-170`、`WF-182`、`WF-186`、`WF-190`
- `docs/spec/cycle-skill-migration.md`（Phase 3のcycle仕様。reviewが受け取る引き渡し物の形を定める）
  - 内容identity: `sha256:bafb3c45c11cfa549b452eeedb7eab3c4322412036ab3892251b599215820c6e`
  - 適用条項: `CY-002`、`CY-032`、`CY-061`〜`CY-065`、`CY-070`〜`CY-073`

**実装境界資料:**

- `ROADMAP.md`（Phase 4節）: `sha256:7307905d9e8f38893d62e6282db78744079d483696b071f71b6459d24718fee7`
- 移行元: `claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`の`plan-reviewer`、`skill-reviewer`、`cycle`のreview部分
- 受け入れ実測の対象: Phase 3が残したbranch `cycle/20260822143915-implementation`とそのworktree `.agents/tmp/worktrees/20260822143915-cycle`

## 用語

この計画で使う言葉。仕様書と同じ意味。

- **attempt**: cycle（TDD実装skill）が一回のplan実行で残した、branch、作業用worktree、commit列、証拠の束。
- **event**: 起きたことを一件ずつ追記する記録file。上書きしない。
- **finding**: reviewが見つけた指摘一件。
- **oracle**: 指摘が直ったかを機械的に判定する手段（test名やcommand）。直っていなければRED、直ればGREEN。
- **trailer**: commit messageの末尾の `Key: value` 行。修正commitに「どの指摘を直したか」を書く場所。
- **claim**: 「今このattemptをreview中」という印のfile。
- **profile**: reviewの観点checklistを書いた散文file。
- **identity**: fileの内容から計算した指紋（SHA-256）。

## 目的

cycleが`implementation_green`（全testが通った状態）で引き渡したattemptを入力に、一回のfull reviewで
指摘の集合を固定し、修正後はその指摘と関連diffだけを見直して有限回で収束する`ba0918-review`を作る。
旧`plan-reviewer`が7観点を別々のsubagentで並列に走らせ、同じ入力を最大8回読んでいた構造を、
一人のreviewerがprofileのchecklistを一回回す構造へ置き換える。security findingとcritical級の指摘を
落とさないことを品質の床とする。

Reviewの責務は「指摘を見つける」と「修正後にその指摘が消えたか確かめる」の二つに限る。直す役、
直す往復を回すfix-loop、final gateは後続phaseで作る。

## 利用者が得る結果

- 初回reviewで指摘の集合が固定され、以後のreviewで指摘が増え続けない。
- 各指摘はoracleから導いた安定IDを持ち、修正で行番号がずれても同じ指摘として扱われる。
- 修正後は未解決の指摘と、その指摘IDをtrailerに持つcommitのdiffだけを読む。全文は再読しない。
- oracleがGREENになった指摘だけが閉じ、直す側の「直した」という報告は信用しない。
- 再review中に見つけた別問題は今回の合否に混ざらず、後続候補へ分離される。
- second reviewer（Codex等）は`--second-reviewer`を明示したときだけ初回に一回併走する。
- `--level=light`を明示すればsecurityとcriticalだけを見る。既定は全観点。
- 対象がコードかskill文書かでprofileが自動的に切り替わる。

## 変更するもの

```text
skills/ba0918-review/
  SKILL.md
  references/
    review.md          初回full reviewと差分再reviewの手順
    evidence.md        finding eventの形と保存場所
    profile/
      default.md       コード用7観点
      skill.md         skill文書用
  scripts/
    review_model.py    純粋なmodel（finding、ID導出、状態遷移、event schema）
    review_runtime.py  Git・filesystem adapter（identity検証、trailer、claim、event書込み、oracle実行）

tests/
  review_model_test.py
  review_runtime_test.py

evals/cases/ba0918-review/
  fixed-findings-converge.yaml
  reject-new-findings-after-green.yaml
  defer-unrelated-problem.yaml
  no-second-reviewer-without-flag.yaml
  light-level-security-critical-only.yaml

evals/inputs/ba0918-review/
  （上記scenarioの最小fixture）

regression-lock.json
```

reference fileの分割数と名前は実装へ委ねる（下記「実装へ委ねる選択」）。上記以外のfileが必要なら、
責務、理由、検証方法を新しいplan revisionとして提示する。

## 変更しないもの

- fixの実装、fix loop、直す役の呼出し、final gate、doc-check、merge、worktree cleanup
- `ba0918-cycle`の本体、cycleのevent列、`docs/spec/cycle-skill-migration.md`
- plan本文、`open-plans.json`、`status.md`、`session-history.md`
- `.agents/artifacts/reviews/`（人間向けreport置き場。機械契約の正本にしない）
- Phase 5の共有artifact store、古い記録の扱い、migration
- 旧`plan-reviewer`のresult file relay、wait discipline、score band、並列fan-out（移植しない）
- 組み込み`/code-review`や公式pluginへの委譲（採用しない）

## 外部への影響と主要risk

- oracleのcommandをworktree内で実行する。absolute path、worktree外への書込み、credentialを含む
  commandは拒否する（`RV-090`）。拒否が甘いと、reviewが任意commandの実行口になる。
- 実process検証と旧版比較はopencode backendの実行時間と利用量を消費する。backendは現在利用不能で、
  回復は2026年9月見込み。回復まで該当stepは停止し、`regression-lock.json`を更新しない。
- 旧版がtimeoutで報告を返さない可能性が高い。その場合「旧版: 未完了、新版: 完走」は記録するが、
  それだけを品質の床の証拠にしない（`RV-114`）。
- finding IDをoracleから導くため、oracleを書けない指摘は機械的に閉じられない。人間判断の指摘が
  多いと往復が増える。緩和策（oracle化を先に試みる、roundごとに一括提示）は仕様に入っている。
- 入力の大きさの閾値（`RV-031a`）は実測後に決める。実測前はguardの存在だけ実装し、閾値は未設定で
  停止しない。
- 新dependency、network、push、PR、mainへのmergeは行わない。

## Human gate

この計画にplanned Human gateは置かない。必要な製品判断は仕様へ反映済みである。仕様の`RV-080`が
定める人間gate（人間判断の指摘、`findings_stale`、必須security未完了、直せない指摘の昇格）は、
完成したreviewが実行時に出すgateであって、この実装計画のgateではない。実装中に新しい製品判断が
必要になった場合は即席gateを追加せずbrainstormへ戻る。

## 実装手順

手順は二つの塊に分かれる。0〜6は今すぐ進められる。7〜8はopencode backendの回復を待つ。
各手順はtest-first（失敗するtestを先に書き、最小実装で通し、必要なら整理する）で進める。

### 0. 実装branchとworktreeを用意する

**対応仕様:** `CY-032`（cycleの配置規約に倣う）  
**書込み範囲:** Git metadata、`.agents/tmp/worktrees/`

- mainから実装branchを切り、専用のlinked worktreeへ隔離する。
- 三仕様とROADMAPのidentityが上記と一致することを確認する。
- 既存unit test 136件がGREENであることを確認する。

**必要証拠:** branch名、worktree path、四fileのSHA-256、unit test結果。  
**停止条件:** identity不一致、dirty worktree、既存testのfailure。

### 1. 純粋なmodelを作る（finding、安定ID、状態遷移、event schema）

**対応仕様:** `RV-020`〜`RV-026`、`RV-033`、`RV-042`、`RV-044`、`RV-072`  
**書込み範囲:** `skills/ba0918-review/scripts/review_model.py`、`tests/review_model_test.py`

何をするか: findingのfield（`RV-020`の10項目）、severityとactionの独立性、oracleからのID導出、
`open`/`closed`/`stale`/`deferred`の遷移、finding eventの形を、副作用のない関数として書く。

- 同じoracleから同じIDが導かれ、file pathと行範囲の変化でIDが変わらないことをtestで固定する。
- `info`に`record_only`以外のactionが付く等、不正な組合せを拒否する。
- 作成時点でGREENのoracleを持つfindingを固定集合へ入れない（RED観測の記録を必須にする）。
- 差分再reviewで見つかった新規指摘が`deferred`になり、固定集合の件数が増えないことを遷移で保証する。
- 同じfindingが一定回数GREENにならない場合の`human_judgment`昇格を遷移で表す。
- eventはschema version、連番、event type、attempt ID、plan/spec identity、直前eventのidentity、
  自身のidentityを持ち、unknown fieldを拒否する。

**必要証拠:** 各testの期待REDと修正後GREEN、unknown field拒否、ID安定性のtest。  
**停止条件:** 仕様にないfieldや状態が必要になった場合（brainstormへ戻す）。

### 2. 入力の検証とclaimを作る

**対応仕様:** `RV-010`〜`RV-013`、`RV-070`、`RV-071`、`RV-073`、`CY-061`〜`CY-065`、`CY-070`〜`CY-073`  
**書込み範囲:** `skills/ba0918-review/scripts/review_runtime.py`、`tests/review_runtime_test.py`

何をするか: cycleが残したattemptのevent列を読み、最後のeventが`implementation_green`であること、
branch、worktree、base HEAD、plan、specのidentityが一致することを機械的に確かめる。reviewの
event列を`.agents/artifacts/executions/{plan-id}/{attempt-id}/review/`に別連番で開き、最初の
eventでcycleの最後のevent identityを参照する。`.agents/runtime/reviews/current.claim`を原子的に
取得し、同じattemptへの並行reviewを拒否する。

- 一時repositoryにcycle相当のevent列を置いたfixtureで、正常受理と各種不一致の拒否をtestする。
- `implementation_green`でないattempt、worktreeが別branchを指す場合、spec identity不一致を拒否する。
- cycleのevent列へは一切書かない。reviewの連番とcycleの連番が混ざらないことをtestで固定する。
- claimの取得失敗（既存claimあり）で停止し、既存claimを上書きしない。

**必要証拠:** 受理1件と拒否5種のRED/GREEN、cycle event列の不変性、claim競合のtest。  
**停止条件:** cycleのevent形式を変えないと読めない場合（cycle仕様の改訂はbrainstormへ）。

### 3. 差分再reviewの機械部分を作る（trailer、関連diff、oracle再実行、開閉）

**対応仕様:** `RV-040`〜`RV-043`、`RV-060`〜`RV-063`、`RV-080`〜`RV-082`、`RV-090`〜`RV-091`  
**書込み範囲:** `skills/ba0918-review/scripts/review_runtime.py`、`tests/review_runtime_test.py`

何をするか: `git log`のtrailerからfinding IDと修正commitの対応を決定的に計算し、IDのないcommitが
混ざっていれば拒否する。未解決findingのoracleをworktree内で再実行し、GREENなら`closed`、REDなら
`open`のままeventを追記する。固定済みfinding集合が依拠したspec identityが変わっていれば
`findings_stale`で停止する。full review再実行の候補判定（修正commitが初回diffのfile集合の外を
触ったか）を機械的に計算し、自動実行はせず人間gateへ上げる。

- trailerの有無、複数ID、IDのないcommit混在をtestする。
- oracle commandのabsolute path、worktree外書込み、credential様の値を拒否する。
- oracle再実行の結果を、直す側の報告ではなく自分の実行結果から判定する。
- `findings_stale`、必須security未完了、昇格を`human_gate` eventとして記録し、finding eventを削除しない。
- stdout、stderr全体をeventへ複製しない。

**必要証拠:** trailer解析、oracle再実行の開閉、stale停止、危険command拒否、event不削除のtest。  
**停止条件:** oracleの種類を仕様外に広げないと判定できない場合。

### 4. profileを書く（default.md、skill.md）

**対応仕様:** `RV-035`〜`RV-039`、`RV-034`  
**書込み範囲:** `skills/ba0918-review/references/profile/default.md`、`skill.md`

何をするか: 観点のchecklistを散文で書く。各profileは担当するpath pattern、checklist、severity候補の
判定基準、許されるoracle種別、`--level=light`でも回す項目を自分で宣言する。

- `default.md`は旧`plan-reviewer`の`review-dimensions.md`の7観点（正確性、security、性能とmemory、
  architecture、網羅性、仕様適合、条件付きUI/UX）を、score bandを外して取り込む。
- `skill.md`は旧`skill-reviewer`の`SKILL.md`とreferencesを実装時に読み、観点（指示品質、context経済、
  責務配置、script強度）を取り込む。担当path patternはskillの`SKILL.md`、`references/**`、
  fixture fileとし、scriptsはdefaultへ回す。
- profile専用のtest、fixture、旧版比較は作らない。

**必要証拠:** 読了した旧fileの一覧、二つのprofileが宣言5項目を持つことの目視確認。  
**停止条件:** 旧skill-reviewerの観点が既存のagentic-meta側の監査と重複し、どちらに置くか判断が要る場合。

### 5. SKILL.mdとreferenceを書く

**対応仕様:** `RV-001`〜`RV-006`、`RV-030`〜`RV-034`、`RV-036`、`RV-038`、`RV-050`〜`RV-052`、`RV-064`、`RV-074`〜`RV-075`  
**書込み範囲:** `skills/ba0918-review/SKILL.md`、`skills/ba0918-review/references/`（profile以外）

何をするか: 本体は責務の境界、二つの呼出し形（初回full review、差分再review）、optionの意味
（`--profile`、`--level`、`--second-reviewer`）、referenceへのroutingだけを持つ。手順の詳細は
referenceへ置き、選ばれたprofileだけを読む指示にする。

- 初回full reviewは一人で、選ばれたprofileのchecklistを一回回し、severity候補ごとに入力範囲を変える
  （security/criticalは直接の呼出し元1 hopと影響条項まで、warnはdiffだけ、infoは記録のみ）。
- oracle化を先に試み、書けない理由を記録した場合だけ`human_judgment`にする。人間判断の指摘は
  roundごとに一括提示する。
- second reviewerは明示flagがあるときだけ一回。渡すのはplan内容とdiffだけ、secret走査をしてから。
- 仕上げfull reviewは人間が明示したときだけ一回、結果は固定集合へ合流。
- 入力の大きさのguardは停止して人間へ返す動作だけ書き、閾値は「実測後に定める」と明記する。
- 英語で書く（LLM向け文書の規約）。fix loop、final gate、Recoveryの手順を書かない。

**必要証拠:** referenceの相対linkが解決すること、責務外keyword（fix loop、final gate、merge）の不在、
`skills-ref validate`相当の静的検査（実行体が無い場合はその事実を記録）。  
**停止条件:** instructionだけでは強制できずscriptの境界が必要な場合は、対応するtestを先に追加する。

### 6. Unit regressionを閉じる

**対応仕様:** `RV-110`  
**書込み範囲:** `tests/review_model_test.py`、`tests/review_runtime_test.py`

- `RV-110`の11項目がすべてtestに対応していることを一覧で確認する。
- 全unit suite（既存136件 + 新規）を`python3 -m unittest discover -s tests -p '*_test.py'`で通す。
- `py_compile`で構文検査を通す。

**必要証拠:** 11項目とtest名の対応表、全suite GREEN、`py_compile`成功。  
**停止条件:** production先行、または既存testを弱めないとGREENにならない場合。

ここまでで実装は完了する。以降はbackendの回復を待つ。

### 7. 実process scenarioとregression lockを生成する（実測待ち）

**対応仕様:** `RV-111`〜`RV-112`、`RV-115`  
**書込み範囲:** `evals/cases/ba0918-review/`、`evals/inputs/ba0918-review/`、`regression-lock.json`、一時fixture

- 五scenario（固定集合の収束、GREEN後の新規finding拒否、別問題の分離、flagなしのsecond reviewer
  不起動、`--level=light`でsecurity/criticalだけ）を実processで実行する。
- fix-loopが無いため、fixtureと人間がID付きcommitを積んで差分再reviewを駆動する。
- 停止の自己申告ではなく、event列、finding集合、Git、worktreeの事後状態で判定する。
- 全証拠が揃った後だけlockを更新する。

**必要証拠:** 五scenarioの終了結果と事後状態、backendとsession IDの対応、lock再検証。  
**停止条件:** backend利用不能、事後状態とprocess結果の不一致がある場合はlockを更新しない。

### 8. 旧版と同一入力で比較する（実測待ち）

**対応仕様:** `RV-113`〜`RV-114`、`WF-170`  
**書込み範囲:** `.agents/tmp/review-comparison/`の一時run data、最終実装報告

- Phase 3の実branchを対象に、旧`plan-reviewer`と新`ba0918-review`を同一backend、同一prompt、同一
  timeoutで走らせる。
- 検出したsecurity/critical finding、review回数、全文再読の回数、request数、token、実行時間を記録する。
- 旧版がtimeoutした場合はその事実を記録し、品質の床の比較は別途説明する。
- 品質低下を効率改善で相殺しない。

**必要証拠:** 同一入力条件、旧新のsession ID、測定表、security/critical findingの対応表。  
**停止条件:** 新版が旧版の検出したsecurity/critical findingを落とした場合（brainstormへ戻す）。

### 9. 最終検証と引渡し

**対応仕様:** 全対象条項  
**書込み範囲:** 変更対象全体、最終実装報告

- 全unit test、lock検証、scope監査、credential形状検査、`git diff --check`を実行する。
- 手順0〜6だけが完了している場合は「実装完了、実測待ち」として引き渡し、Phase 4の完了判定は
  しない。
- 手順7〜8が完了した場合は、ROADMAP Phase 4節の「現在の検証状況」へ書く材料（数値と判定）を
  報告として返す。ROADMAPの編集自体はこのplanの範囲外。
- mainへのmerge、worktree cleanup、review、fix-loopは行わない。

**必要証拠:** command、exit code、全test数、spec identity、commit列、scope内diff。  
**停止条件:** 必須test failure、identity drift、scope外変更、secret疑い、証拠欠落がある場合。

## 実装へ委ねる選択

- `review_model.py`と`review_runtime.py`の内部関数名と分割。同じ観測可能な挙動とexact schemaを
  保つ範囲で変えてよい。
- `references/`の分割数とfile名。選ばれたprofileだけを読む構造を保てばよい。
- oracleのIDを導くhash関数の入力正規化（空白、引数順序等）。同じoracleから同じIDが出ることを
  testで固定すればよい。
- trailerのKey名（例: `Finding-Id`）。仕様は「finding IDをtrailerに持つ」とだけ定める。
- claim fileの中身の形式。原子的取得と上書き拒否を保てばよい。
- 人間向けreportの見た目。機械契約の正本はeventであり、reportは`.agents/artifacts/reviews/`に置く。

## 完了条件

- 三仕様とROADMAPのidentityが実行前と各境界で再検証される。
- oracleからの安定ID、severity/action独立、RED観測必須、状態遷移がunit testで固定される。
- attemptのidentity検証、cycle event列の不変性、claim競合拒否が通る。
- trailerからの関連diff計算、oracle再実行による開閉、`findings_stale`停止、危険command拒否が通る。
- 二つのprofileが宣言5項目を持ち、SKILL.mdが選ばれたprofileだけを読む。
- `RV-110`の11項目がtestに対応し、全unit suiteがGREENである。
- （実測後）五scenarioが事後状態でPASSし、lockに記録される。
- （実測後）旧版比較でsecurity/critical findingを落としておらず、全文再読とreview回数が減っている。
- 全変更がplan scope内の独立commitである。
