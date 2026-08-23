# Review skill移行仕様

この文書は、`ba0918-review`（実装を見て問題を指摘し、修正後はその指摘だけを確認し直すskill）が
何をして何をしないかを決める。旧`plan-reviewer`を置き換える。

`RV-000` 本仕様は`docs/spec/agentic-workflow.md`と`docs/spec/cycle-skill-migration.md`を
Phase 4のReviewについて具体化する。矛盾する場合は、人間が解消するまで実装planを作成しては
ならない。

## 読み方

先に用語を揃える。本文ではこの意味で使う。

- **attempt**: cycle（Phase 3のTDD実装skill）が一回のplan実行で残した、branch、作業用worktree、
  commit列、証拠の束。reviewはこれを入力にする。
- **identity**: fileや記録の内容から機械的に計算した指紋（SHA-256）。「同じものを見ているか」を
  会話の記憶ではなく指紋の一致で確かめる。
- **event**: 起きたことを一件ずつ追記する記録file。上書きしない。cycleも同じ方式を使う。
- **finding**: reviewが見つけた指摘一件。
- **oracle**: その指摘が直ったかを機械的に判定する手段（test名やcommand）。直っていなければ
  失敗（RED）、直れば成功（GREEN）になる。
- **trailer**: commit messageの末尾に書く `Key: value` 形式の行。修正commitに「どの指摘を
  直したか」をここに書いてもらう。
- **claim**: 「今このattemptをreview中」という印のfile。同時に二つのreviewが走るのを防ぐ。
- **profile**: reviewの観点checklistを書いた散文file。対象（コードかskill文書か）で差し替える。

## この仕様で人間が判断する点

多くの条項は対話で合意済みの内容を条文にしたもの。対話で明示的に決めておらず、agentが補った
判断は次の6つ。承認はこの6つを含む文書全体への承認になる。

| 判断 | なぜ必要か | 条項 |
|---|---|---|
| 指摘を登録する時点で、そのoracleが失敗（RED）することを確認しておく | 最初から成功するoracleを持つ偽の指摘が「直った」扱いで素通りするのを防ぐ | RV-024 |
| 必須のsecurity確認は別agentではなく、同じreviewerのchecklist必須項目として扱う。終わらなければreview全体を未完了にする | 親仕様WF-124の「必須securityと任意second opinionの分離」を責務の分離と読む | RV-032 |
| reviewの記録はcycleの記録と同じ場所に置くが、別の連番にしてcycleの最後の記録を参照する。同じattemptへの同時reviewは拒否する | cycleの記録の所有権を侵さず、どの実装へのreviewかを指紋で結びつける | RV-071、RV-073 |
| cycle仕様の表が「fix loopとfinal gateはPhase 4」と書いている点は、cycle仕様を書き換えず本仕様側で行き先を訂正する | 承認済みのcycle仕様を再承認なしに変えない | RV-006 |
| 「再review中に新しい指摘を足さない」は差分再reviewに限る。人間が明示した仕上げのfull reviewはこの禁止の対象外 | 仕上げreviewの結果を固定集合へ合流させる合意と矛盾させない | RV-042、RV-050 |
| 「実測しない」はprofile散文に限る。Phase 4全体の受け入れ実測と旧版比較、決定的なscriptのunit testは行う | 合意した品質の床と旧版比較の完了条件を保つ | RV-039、RV-110、RV-113 |

## 目的と責務

reviewは「指摘を見つけること」と「修正後にその指摘が消えたか確かめること」だけを持つ。
直すのは別の役、直す往復を回すのも別の役（fix-loop）で、どちらも後続phaseで作る。

`RV-001` `ba0918-review`は、cycleが`implementation_green`（全testが通った状態）で引き渡した
attemptを入力に、初回のfull reviewでfinding集合を固定し、修正後は未解決のfindingと関連diff
だけを再確認して、finding集合を有限回で収束させなければならない。

`RV-002` 利用者が得る結果は「問題は見つかるが、reviewのたびに指摘が増え続けるloopが起きない
review」である。旧`plan-reviewer`は7観点を別々のsubagentで並列に走らせ、second opinionを
常時起動していた。そのtoken消費を、security findingとcritical級の指摘を落とさずに減らす
ことが本題である。

`RV-003` Reviewは次を所有する。

- 初回full reviewとfinding集合の固定
- severity（重さ）とaction（必要な対応）の分離
- 同じ根本原因のfindingをまとめて提示すること
- findingごとのoracleの固定と、oracleから導く安定ID
- 未解決findingと関連diffに限定した差分再review
- 必須security項目と任意second reviewerの分離
- finding集合と各roundの判定の記録

`RV-004` Reviewは次を所有してはならない。

- fixの実装、fix loopの進行制御、修正する役の呼出し
- final gate、merge、publication、worktree cleanup
- plan本文、`open-plans.json`、`status.md`、`session-history.md`の更新
- `info`級findingの自動修正
- 明示されていないsecond reviewerの起動

`RV-005` 全体flowは次の順序とし、Reviewは「初回full review」と「差分再review」の二つの
呼出し形だけを提供する。fix-loop、修正する役、doc-check、final gateは後続phaseの責務で、
本仕様はそれらとの受け渡し契約だけを定める。

```text
brainstorm -> plan -> cycle(TDD実装) -> review(初回full review)
  -> fix-loop( 修正 -> review(差分再review) の往復 ) -> doc-check -> final gate -> done
```

`RV-006` `docs/spec/cycle-skill-migration.md`のSource audit表は「review、severity、fix loop、
final gate」をPhase 4へ割り当てている。本仕様により、reviewとseverityはPhase 4、fix loopと
修正する役、final gateは後続phaseへ行き先を訂正する。cycle仕様の本文は変更しない。

## 入力と拒否条件

reviewを始める前に「本当にcycleが引き渡したものを見ているか」を指紋で確かめる。
会話の記憶で対象を決めない。

`RV-010` 初回full reviewの入力は、cycleが引き渡すattempt ID、branch、worktree、commit一覧、
plan identity、参照spec identity、`regression-lock.json`とする。候補を選ぶのに会話理解を
使ってよいが、実行前にattemptのevent記録からbranch、worktree、base HEAD、plan、specの
identityを機械的に再検証しなければならない。

`RV-011` attemptの最後のeventが`implementation_green`でない、identityが食い違う、worktreeが
無いか別のbranchを指している、参照specが承認済みrevisionと一致しない場合は、findingを作る前に
拒否しなければならない。

`RV-012` 差分再reviewの入力は、固定済みfinding集合のidentity、未解決finding、finding IDを
trailerに持つ修正commit、修正が新たに持ち込んだriskとする。固定済みfinding集合が依拠した
specのidentityが現在の承認済みrevisionと異なる場合は、findingを閉じずに`findings_stale`
（指摘の前提が古くなった）として停止し、人間へ返さなければならない。

`RV-013` finding IDのtrailerを持たないcommitが修正commitに混ざっている場合、関連diffを
推測で補わず、範囲外として拒否しなければならない。

## Finding

指摘一件が持つ情報と、「同じ指摘かどうか」をどう決めるかを定める。核は「IDはoracleから作る」。
修正で行番号がずれても、同じoracleなら同じ指摘として扱える。

`RV-020` findingは少なくとも次のfieldを持たなければならない。

- `id`: oracleから決定的に導く安定ID
- `severity`: `security`、`critical`、`warn`、`info`のいずれか
- `action`: `auto_fix`（人に聞かず直す）、`fix_and_verify`（直して検証する）、
  `human_judgment`（人が決める）、`record_only`（記録だけ）のいずれか
- `clauses`: 影響する承認済み仕様条項
- `evidence`: 観測したfile、行範囲、出力の要約
- `oracle`: test名またはcommand。`human_judgment`の場合はoracleを書けない理由
- `root_cause`: 同じ根本原因でまとめるための集約キー
- `state`: `open`、`closed`、`stale`（前提が古い）、`deferred`（後続候補へ送った）のいずれか
- `spec_identity`: 依拠した承認済み仕様のidentity
- `profile`: このfindingを生んだprofile

`RV-021` severityとactionは独立したfieldとし、一方から他方を暗黙に導いてはならない。`info`は
`record_only`以外のactionを持ってはならない。

`RV-022` 安定IDはoracleから決定的に導出しなければならない。file pathと行範囲をIDの材料に
してはならない。同じoracleを持つfindingは同一findingとして扱い、再登録してはならない。

`RV-023` reviewerは全findingについて先にoracle化を試み、書けない理由を記録した場合だけ
`human_judgment`へ落とせる。「書く手間」だけを理由に`human_judgment`にしてはならない。
`warn`のoracleは既存testの再実行や静的検査でよく、新規test作成を強制しない。

`RV-024` `human_judgment`以外のfindingは、作成時点でoracleがREDであることを観測し、
evidenceへ記録しなければならない。作成時点でGREENのoracleを持つfindingを固定集合へ入れては
ならない。

`RV-025` `human_judgment`のfindingは固定集合に含めるが、機械的に閉じてはならない。人間の判断を
`human_gate` eventとして記録した場合だけ`closed`へ遷移できる。`human_judgment`のfindingは
roundごとに一括して提示し、一件ずつ質問してはならない。

`RV-026` 同じ`root_cause`のfindingは一つの修正単位として提示しなければならない。集約は提示の
単位であり、各findingのIDとoracleは個別に保持する。

## 初回full review

一人のreviewerが、選ばれたprofileのchecklistを一回だけ回す。観点ごとに別agentを立てない。
重い指摘（security、critical）の候補だけ周辺まで読み、軽い候補はdiffだけ見る。小さな変更に
7観点を全部当てるのが過剰なときは、人間が`light`を指定すればsecurityとcriticalだけを見る。

`RV-030` 初回full reviewは現在の実行agentが一回だけ行い、選択されたprofileのchecklistを
並列subagentではなく同一contextで回さなければならない。観点ごとに入力を読み直してはならない。

`RV-031` 入力範囲はseverityの候補ごとに変えなければならない。

- `security`と`critical`の候補: diffに加えて、diffが触れたシンボルの直接の呼出し元（1 hop、
  worktree内）と、影響する承認済み仕様条項まで読む。呼出し元は候補が立ってから読み、先読み
  しない
- `warn`の候補: diffだけを読む
- `info`: 記録のみ。追加で読まない

`RV-031a` 入力の大きさが閾値を超える場合、自動で分割せず停止して人間へ返さなければならない。
分割はplanの粒度の問題であり、Reviewが解いてはならない。閾値は受け入れ実測後に定める。

`RV-032` 必須security項目はchecklist内の必須項目として同じreviewerが扱う。完了できない場合、
review全体を未完了かつ再開可能な状態で停止し、成功を宣言してはならない。

`RV-033` 初回full reviewの完了時に、finding集合を一つのeventとして固定し、その集合のidentityを
以後の差分再reviewの入力identityとしなければならない。

`RV-034` reviewの強度は`--level=light|standard`相当の明示optionで指定でき、既定は`standard`
とする。`light`は`security`と`critical`の候補だけを探索し、`warn`と`info`は集めない。
oracleの必須（RV-022〜024）、必須security項目（RV-032）、差分再reviewと収束の契約は
levelで変えてはならない。変更量や行数からlevelを自動で選んではならず、`light`は人間が明示した
場合だけ使う。reviewerは`light`で足りそうだと提案してよいが、決めるのは人間である。

## Review profile

観点のchecklistは本体から切り離した散文fileにする。コード用とskill文書用を同梱し、
対象のfile種別で自動的に選ぶ。profileを足しても本体は触らない。

`RV-035` review観点はprofileとして`references/profile/`配下の散文fileへ分離し、付け替え
可能にしなければならない。Phase 4は`default.md`（旧`plan-reviewer`の7観点: 正確性、security、
性能とmemory、architecture、網羅性、仕様適合、条件付きUI/UX）と`skill.md`（skill文書用。
旧`skill-reviewer`の観点を実装時に読んで取り込む）を同梱する。

`RV-036` `SKILL.md`本体はloop契約とfinding契約だけを持ち、選択されたprofileだけを読まなければ
ならない。全profileを先読みしてはならない。

`RV-037` 各profileは、担当するpath pattern、checklist、severity候補の判定基準、許されるoracle
種別、`light`でも回す項目を自分で宣言しなければならない。profileの追加で`SKILL.md`とscriptsを変更してはならない。

`RV-038` profileは既定でdiffのfile種別から自動選択し、`--profile`相当の明示optionで上書き
できる。混在diffでは該当する全profileをfile集合ごとに範囲限定して適用し、finding集合は一つに
保つ。

`RV-039` profileは散文で副作用を持たないため、profile専用のE2E、fixture、旧版比較を要求しない。
観点の過不足はdogfoodingで見つけ次第、profile fileだけを直す。

## 差分再reviewと収束

修正後は全部を読み直さない。未解決の指摘と、それを直したと宣言しているcommitだけを見て、
oracleを自分で走らせて閉じる。新しく気づいた別問題は今回の合否に混ぜない。

`RV-040` 差分再reviewは未解決finding、そのfinding IDをtrailerに持つ修正commitのdiff、
影響するevidence、修正が持ち込んだ新riskだけを入力とし、全文を再読してはならない。

`RV-041` 差分再reviewは修正した側の「直した」という報告を読まず、各未解決findingのoracleを
自分で再実行して`closed`を判定しなければならない。REDのままのfindingは`open`のまま保持する。

`RV-042` 差分再review中に見つかった新しい指摘（`warn`を含む）は現在の合否へ追加せず、
`deferred`として後続候補へ分離しなければならない。修正commitが新たに持ち込んだriskだけは
WF-114に従い、新findingとして固定集合へ追加できる。

`RV-043` full reviewの再実行候補は、修正commitが初回reviewのdiffのfile集合の外を触った場合に
限る。specの改訂は`RV-012`の`findings_stale`で扱う。候補になっても自動で再実行せず、人間gate
へ上げて理由をevidenceへ記録する。

`RV-044` 収束はfinding集合が有限であることから機械的に保証する。同じfindingのoracleが一定回数
GREENにならない場合は「収束しない」ではなく「直せていない」として`human_judgment`へ昇格し、
人間へ返さなければならない。round数の上限を自動loopの終了条件にしてはならない。

## 仕上げfull reviewとsecond reviewer

新しい目で全部を見直したいときは、人間が明示したときだけ一回。結果は固定集合へ合流させ、
そこからは差分再reviewで閉じる。Codexなどの第二意見も明示optionがあるときだけ初回に一回。

`RV-050` 人間が現在の対話で明示した場合だけ、新規contextのagentによる仕上げfull reviewを
一回追加できる。その結果は固定集合へ合流させ、以後は差分再reviewで閉じる。自動で繰り返しては
ならない。

`RV-051` second opinion（Codex等の独立reviewer）は、`--second-reviewer`相当の明示optionが
ある場合だけ、初回full reviewに一回だけ併走させる。権限を持ち越さず、自動再試行してはならない。
利用不能な場合は警告を記録して初回full reviewだけで続行する。渡すのはplan内容とdiffだけとし、
full source fileを渡してはならない。渡す前にsecret走査を行い、自分のreview結果や結論を
渡してはならない。

`RV-052` second reviewerの実行先は差し替え可能にし、特定のbackendを仕様で固定してはならない。

## fix側との受け渡し契約

直す側とreviewの間の約束。直す側はfinding集合を読むだけで書き換えず、commitにどの指摘を
直したかをtrailerで書く。reviewは直す側の報告を信じず、oracleで確かめる。

`RV-060` finding集合はReviewだけが書く不変のartifactとする。直す側はこれを読むだけで、
findingの`state`を書き換えてはならない。

`RV-061` 直す側は、修正commitのtrailerに対象finding IDを書かなければならない。Reviewは
`git log`のtrailerから関連diffを決定的に計算する。

`RV-062` 直す側が修正中に見つけた別問題は、finding集合ではなく後続候補として別fileへ書かなければ
ならない。

`RV-063` 直す側が修正中に仕様不足を見つけた場合、specの改訂はbrainstormへ戻し、Reviewは
`RV-012`の`findings_stale`で停止する。

`RV-064` 直す側の正体（利用者向けskillとしての`iterate`か、fix-loop内部の実装役か）は本仕様で
決めない。finding集合の形と本節の契約は、直す側に依存してはならない。

## 永続化と並行性

reviewの記録はcycleのattemptと同じ場所に、cycleと同じ「一件一file、追記のみ」の方式で置く。
cycleの記録には書き足さず、自分の連番を持つ。

`RV-070` finding集合とround判定は、attemptに紐づくeventとして
`.agents/artifacts/executions/{plan-id}/{attempt-id}/review/`へ一event一fileの連番で積まなければ
ならない。host-localな制御fileは`.agents/runtime/reviews/{attempt-id}/`、消えてよい一時物は
`.agents/tmp/reviews/{attempt-id}/`へ置く。

`RV-071` reviewのevent列はcycleのevent列とは別の連番を持ち、最初のeventでcycleの最後のevent
identityを参照しなければならない。cycleのevent列へ追記してはならない。

`RV-072` findingの開閉は追記eventで表し、固定済みfinding集合のeventを上書きしてはならない。
各eventはschema version、連番、event type、attempt ID、plan/spec identity、直前eventの
identity、自身のidentityを持つ。

`RV-073` review実行はrepositoryごとの`.agents/runtime/reviews/current.claim`を原子的に取得し、
同じattemptへの並行reviewを拒否しなければならない。

`RV-074` finding集合の寿命はplanと同じとし、古い記録の扱いとmigrationはPhase 5が扱う。
`.agents/artifacts/reviews/`は人間向けreportの置き場であり、機械契約の正本にしてはならない。

`RV-075` stdout、stderr、provider log全体をeventへ複製してはならない。

## 人間gateと失敗

`RV-080` `human_judgment`の判断、`findings_stale`、必須security未完了、`RV-044`の昇格は
人間gateとし、`human_gate` eventとして記録する。

`RV-081` 必要な人間、evidence、worktree、oracle実行環境が利用不能な場合、成功ではなく未完了
かつ再開可能な状態を残さなければならない。

`RV-082` 拒否または停止後にfinding集合のeventを削除してはならない。

## Securityと信頼境界

`RV-090` oracleのcommandはworktree内で実行し、absolute path、worktree外への書込み、
credentialを含むcommandを拒否しなければならない。

`RV-091` evidenceへsecret、personal data、internal hostnameを記録してはならない。

## 設計判断と再検討条件

| 判断 | 理由 | 再検討条件 |
|---|---|---|
| 7観点を並列subagentではなく同一contextのchecklistにする（RV-030） | 旧版は最大8 agentが同じ入力を独立に全読みした。Phase 3の実測では旧版cycleがsubagent 3本でも900秒以内に報告を返せなかった | 結果配送を機械的に保証でき、checklistより小さい入力で同等以上の検出率を実測できた場合 |
| 組み込み`/code-review`や公式pluginへ初回reviewを委ねない | 実行agentによっては存在せず、出力品質がぶれ、finding IDと限定再reviewを持たない | 全対象backendで同一契約の出力を返すreview機構が使えるようになった場合 |
| fixをReviewにもcycleにも置かない（RV-004、RV-064） | reviewerの責務ではなく、cycleへ置くと状態管理が複雑化してCY-004と衝突する | 該当なし。直す役の分離要否は後続phaseで判断する |
| round上限の自動loopを作らない（RV-044） | 旧版のCodex reviewで新規指摘が出続け、無人のまま22 round回った事例がある。回すなら人間が明示してコスト感を持つ | 差分再reviewだけで収束しない実例が蓄積し、上限の方が人間gateより安全だと実測できた場合 |
| review強度を`light`と`standard`の2段にし、自動選択しない（RV-034） | 小さな変更で7観点とwarnのoracle作成が過剰になる。行数は影響度の代理にならない（認可判定の1行変更が最も危ない）。`deep`相当は仕上げfull review（RV-050）が担う | `light`の誤用でsecurity/critical漏れが実測された場合、または3段目の需要がdogfoodingで繰り返し出た場合 |
| 安定IDをoracleから導く（RV-022） | 「oracleを固定」「GREENなら閉じる」とIDを同一視すると契約が最も単純になる | oracleを持てないfindingが多数を占め、位置や原因ベースのIDの方が再登録を防げると実測できた場合 |
| 観点をprofile散文へ分離し、skill用も同じcycleで同梱する（RV-035〜039） | 実装物はテキスト1 fileで副作用がない。cycle分割やprofile専用fixtureは過剰設計 | profileの選択誤りや観点の欠落が繰り返し起き、機械的な判定が必要になった場合 |
| 合成fixtureを作らず実branchで測る（RV-113） | 実データの方が精度が出る。fixtureを二つにすると実測コストが増える | 実branchに品質の床を測れるsecurity/critical findingが含まれないと判明した場合 |
| reviewのeventをcycleのattempt配下に置く（RV-070） | 入力がattemptそのものであり、同じ指紋の木に置くとspecの改訂やdiffとの対応切れを構造的に防げる | Phase 5のartifact責務分離で別の配置が承認された場合 |

## Acceptance

決定的なscript（event、ID導出、claim）にはunit testを書く。profile散文には書かない。
実agentでの検証と旧版比較は実branchで行うが、opencode backendの回復を待つ。

`RV-110` scriptsのunit testは少なくとも次を検証しなければならない。

- attempt、plan、spec、worktree、base HEADのidentity不一致を拒否する
- `implementation_green`でないattemptを拒否する
- 同じoracleから同じIDが導かれ、file pathと行範囲の変化でIDが変わらない
- 作成時点でGREENのoracleを持つfindingを固定集合へ入れない
- severityとactionの不正な組合せ（`info`に`auto_fix`等）を拒否する
- 差分再reviewでIDのないcommitを拒否し、関連diffをtrailerから決定的に計算する
- spec identityの変化で`findings_stale`として停止し、findingを閉じない
- 差分再review中の新規指摘が`deferred`になり、固定集合の件数が増えない
- oracle GREENでfindingが`closed`になり、REDのままなら`open`が保たれる
- eventの連番とidentityの衝突を上書きしない
- 同じattemptへの並行reviewをclaimで拒否する

`RV-111` 実agentでの検証は少なくとも次のscenarioを実行し、停止の自己申告ではなくfile、Git、
eventの事後状態で判定しなければならない。

- 初回full reviewから固定集合が作られ、人間が手で積んだID付き修正commitに対する差分再reviewで、
  oracle GREENのfindingだけが閉じる
- 全test GREEN後に差分再reviewを繰り返しても固定集合に新規findingが増えない
- 差分再review中に見つけた別問題が後続候補へ分離され、現在の合否へ混ざらない
- `--second-reviewer`なしでsecond reviewerが起動しない
- `--level=light`でsecurity/critical findingが作られ、warn/infoが作られない

`RV-112` fix-loopと直す役が存在しない間は、fixtureと人間がfix-loopの席に座り、ID付きcommitを
積んで差分再reviewを駆動する。

`RV-113` 旧版比較と受け入れ実測のfixtureは、Phase 3が残した実branch
`cycle/20260822143915-implementation`とそのworktree、commit列、`regression-lock.json`を使う。
旧版は`claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`の`plan-reviewer`とし、同一
backendで、検出したsecurity/critical finding、review回数、全文再読の回数、request数、token、
実行時間を比較する。品質低下を効率改善で相殺してはならない。

`RV-114` 旧版がtimeoutで報告を返さない場合、「旧版: 未完了、新版: 完走」を比較結果として
記録してよいが、それだけを品質の床の証拠にしてはならない。

`RV-115` 実process実測と旧版比較は、利用者指定のopencode backendが回復するまで保留する。
設計、実装、unit testは先行してよいが、Phase 4の完了判定は実測後とする。

## Source audit

移行元は`claude-skills` revision `57bb6f06aecdf191d46d99d9a3283233a26ecfdd`（作業ツリーが
このrevisionと一致し、未commit変更がないことを確認した）。

読んだもの:

- `skills/plan-reviewer/SKILL.md`、`references/output-format.md`、
  `references/review-dimensions.md`、`fixtures.json`、`commands/plan-review.md`
- `skills/plan-implement/SKILL.md`のreview、fix loop、final review部分
- `skills/cycle/SKILL.md`のPhase 3（reviewとfix loop）、Phase 4（final gate）、
  `references/fix-delegation.md`、`final-gate-delegation.md`、`skill-review-routing.md`
- 共有契約: `severity-and-verdicts.md`、`orchestration-patterns.md`、`quality-gate-contract.md`、
  `fix-action-taxonomy.md`、`codex-integration.md`
- 比較対象として、Claude Code組み込み`/code-review`のdescriptionと公式`code-review` pluginの
  `README.md`、`commands/code-review.md`
- Phase 1からPhase 3の仕様、実装、acceptance、比較結果

| 項目 | 旧`plan-reviewer`の実態 |
|---|---|
| Trigger | `/claude-skills:plan-review`、またはcycle Phase 3からのsubagent委譲 |
| User value | 実装コードをplanと仕様に照らして独立に批判し、BLOCK/WARN/PASS/ESCALATEを返す |
| Responsibility | 7観点の並列review、Codex second opinion、scoring、escalation分類、report、分岐提示 |
| Dependencies | artifact store、`.agents/config/review-rules.md`、ledger、clauses、result file relay、wait discipline、Codex integration |
| Persistent state | `.agents/runtime/delegation/{run_id}_review-{dim}.md`（読了後に削除）。findingの永続化なし |
| Human gates | WARN時の「了承して進む / 修正する」確認、ESCALATE時のbrainstorm差し戻し提示 |
| Mechanical checks | `fixtures.json`のpr-001（CLI、seeded欠陥3件）、pr-002（frontend、UI/UX trigger）。finding自体に機械的な検証gateはない |
| Token costs | 最大7 review + Codex 1を並列起動し、各agentがplan、CLAUDE.md、review-rules、対象コードを独立に全読み。high-capability modelを明示 |
| Known failures | findingに安定IDも再review時の突き合わせ手段もなく、再reviewは同一promptで全diffを再実行する。新規findingの扱いに規定がなく、Codex reviewで新規指摘が出続けて無人のまま22 round回った事例がある |
| Destination | 初回full review、severity、oracle、finding集合の固定はPhase 4へ再設計。fix loop、final gateは後続phase。並列fan-out、relay、wait discipline、Codex常時起動は廃止 |
| Rationale | 品質の床（security/critical）を守りつつ、同じ入力を最大8回読む構造と収束しない再reviewを除く |
| Acceptance fixture | pr-001相当のseeded欠陥（仕様外依存、test欠落、設計rule違反）を初回full reviewが検出する。ただしPhase 4の比較fixtureは実branch |
| Excluded behavior | 7観点の並列subagent、Codex常時起動、result file relay、wait discipline、sequential fallback表示、score bandによるverdict、WARN時のユーザー確認分岐 |

| 旧責務 | 出典 | 移行先 |
|---|---|---|
| 7観点のchecklist | `review-dimensions.md` | `default.md` profile（RV-035） |
| UI/UXの条件付き起動判定 | `plan-reviewer/SKILL.md` Step 2.5 | `default.md`の条件付き項目 |
| escalation分類（合意やclauseの変更が必要か） | `plan-reviewer/SKILL.md` Step 0 | `findings_stale`とbrainstorm差し戻し（RV-012、RV-063） |
| severity（critical/important/minor）とscore bandによるverdict | `output-format.md`、`severity-and-verdicts.md` | severityを`security/critical/warn/info`へ置換。score bandは廃止 |
| fix action（AUTO_FIX/NEEDS_JUDGMENT/REPORT_ONLY）の直交軸 | `fix-action-taxonomy.md` | `action` field（RV-020） |
| 7観点 + Codexの並列fan-out、result file relay、wait discipline | `plan-reviewer/SKILL.md` Step 3–4、`orchestration-patterns.md` | 廃止（RV-030） |
| Codex second opinionの常時起動 | `plan-reviewer/SKILL.md` Review 8 | 明示option時のみ一回（RV-051） |
| second opinionへのsource非開示、adversarial framing、secret走査 | `codex-integration.md`、`final-gate-delegation.md` | 保持（RV-051） |
| 最終reportの構造 | `output-format.md` | 人間向けreportとして簡素化。機械契約の正本はevent（RV-074） |
| WARN時の「了承して進む / 修正する」確認分岐 | `plan-reviewer/SKILL.md` Step 6 | fix-loop（後続phase） |
| cycle Phase 3のfix loop、WARN auto-fix、payload sanitize、allowed-files交差、scope違反時のrevert | `cycle/SKILL.md` Phase 3、`fix-delegation.md` | fix-loopと直す役（後続phase）。sanitizeとscope制約は受け渡し契約の参考 |
| 再reviewが同一promptで全diffを再実行する挙動 | `cycle/SKILL.md` Step 3d | 廃止。差分再review（RV-040）へ置換 |
| iteration capを「決定不能の検出器」とし、oscillationを即escalateする契約 | `quality-gate-contract.md` | round上限は廃止。直せないfindingの人間昇格（RV-044）として保持 |
| cycle Phase 4 final gate（holistic + independent） | `cycle/SKILL.md` Phase 4 | final gate（後続phase） |
| plan-implementのstep単位reviewと受容WARNのprogress file記録 | `plan-implement/SKILL.md` Step B–D | 廃止。cycleのTDD evidenceが代替し、受容判断は`human_gate` eventへ |
| file種別によるreviewer振り分けと混在時のscope限定 | `skill-review-routing.md` | profile自動選択（RV-038） |
| skill-reviewerの観点（指示品質、context経済、責務配置、script強度） | `skills/skill-reviewer/`（本auditでは未読。実装時に読む） | `skill.md` profile（RV-035） |
| `.agents/runtime/delegation/`のsingle-use result file | `plan-reviewer/SKILL.md` Step 3 | 廃止。event（RV-070）へ置換 |
| plan statusの`⚠️ Review Failed`への書き戻し | `cycle/SKILL.md` | 廃止。plan本文とstatusを更新しない（CY-073と同じ） |

旧版で未確認のまま残る点: plan-implementのreviewがplan-reviewer skillを呼ぶのか独自agentかは
本文から判断できない。cycle Phase 3表示の`{findings_addressed}/{total}`の算出方法は定義されて
いない。`quality-gate-contract.md`の収束条件を三skillのどれかが実際に参照しているかは確認
できなかった。これらはPhase 4の互換条件にしない。
