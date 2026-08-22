# agentic-workflow 移行ロードマップ

## 目的

`claude-skills`にあるworkflow責務を、一度に複製せず、小さな利用可能単位ごとに
`agentic-workflow`へ移す。

各フェーズは単独で利用価値を持ち、Agent Skills標準への準拠、実環境での動作、
機械検証、トークン効率を確認してから完了する。あるフェーズの完了は、次のフェーズを
自動的に開始する権限を与えない。

## 現在地

最初の移行では全workflowを一つのplanへ含めたため、文脈が肥大化し、未合意の設計判断と
review loopを招いた。また、旧skill全体を読まず、名前の分類だけを全体調査として扱った。
`cycle/20260821172451`の実装は成果物および移植元として採用しない。失敗原因と消費を
確認できる記録としてのみ隔離する。

再移行は、承認済みのworkflow仕様とトークン効率化資料を入力にして、`main`から開始する。
既存実装のコード、schema、test、独自メタデータは移植元として扱わない。新しいフェーズで
必要性が独立に証明された小さな部分だけ、元の`claude-skills`と再比較して再利用を判断する。

## 全フェーズ共通の契約

### 小さく移す

- 一つのフェーズでは、一つの利用者向け能力だけを完成させる。
- 一つの実装cycleでは、原則として一つのskillだけを移行する。
- 複数skillの責務を統合する場合も、成果物は一つの利用者向けskillに限定する。
- 各skillまたは独立した利用者価値に、個別のbrainstorm、実装、検証、reviewを用意する。
- 仕様文書とplanの一対一対応は要求しない。planは関係する承認済み仕様条項へ追跡できればよい。
- 一つのplanへ複数の独立skillや将来フェーズを含めない。
- フェーズ終了時に必ず停止し、人間が成果と実測値を確認する。
- 次のフェーズは、新しい会話または明示的な再開指示から始める。

### Brainstormを二つの粒度に分ける

プロジェクト全体のbrainstormと、一つのskillを実装するbrainstormを同じ成果物として
扱わない。

#### 戦略brainstorm

- プロジェクト全体の目的、原則、責務境界、移行順序を決める。
- 成果物はROADMAPとし、直接実装planへ変換しない。
- 複数skillや複数cycleを含んでよい。
- 各フェーズで改めて決める事項を明示する。

#### 実装brainstorm

- ROADMAP上の一つのskillまたは一つの利用者向け能力だけを対象にする。
- 元skillのsource auditと、直前フェーズの実測結果を入力にする。
- 配布、実行、状態、外部I/O、人間ゲート、機械検証を決める。
- 成果物は、そのskillだけを実装できる、現在の利用者の言語による仕様集合とする。
- 一つのcycleで完了できることを確認してからplanへ進む。

### Plan readiness gate

次をすべて満たさないbrainstormは、実装planへ変換しない。

- 成果物が一つのskillまたは一つの独立した利用者向け能力に限定されている。
- 利用者が得る結果を一文で説明できる。
- 対象と対象外が明示されている。
- 配布単位と実行方法が決まっている。
- 永続状態、寿命、migrationが決まっているか、適用外と確認されている。
- 外部I/Oと必要な権限が決まっている。
- 人間が判断する項目と提示内容が決まっている。
- 完了を判定する機械的なoracleがある。
- 変更予定のskill、scripts、references、fixturesを列挙できる。
- 未決定の基礎設計が残っていない。
- 一つのcycleで実装、検証、reviewまで完了できる見込みを説明できる。

満たさない場合はplanを大きくするのではなく、ROADMAP上の複数フェーズへ分解する。

### Agent Skills標準に従う

- 各skillは`SKILL.md`を中心とした標準的なskillディレクトリとして配布する。
- 決定的な処理が必要なら、そのskillの`scripts/`へ実行可能な形で同梱する。
- 補助文書はそのskillの`references/`へ置き、`SKILL.md`から相対パスで参照する。
- 外部依存が必要なら`compatibility`へ明記する。
- 実際に解釈するconsumerが存在しない独自メタデータを追加しない。
- 共有runtimeやplugin全体を暗黙の前提にしない。
- `skills-ref validate`に加え、対象クライアントへskill単体を配置した起動試験を行う。

### 利用価値を先に証明する

- 内部構造のテストだけでは完了としない。
- 利用者がskillを起動し、期待した成果物を得るまでを固定fixtureで検証する。
- 旧版と同じ入力を使い、重大な仕様漏れ、操作回数、tool呼び出し、review回数、
  再読範囲、入出力トークンを比較する。
- 品質を下げるトークン削減は採用しない。
- 実測していない改善を、効率化の成果として記載しない。

### 合意を越えない

- planは合意済みの意味を実装手順へ変換する。新しい製品設計を追加しない。
- 新しい配布方式、runtime、永続化方式、独自schema、外部依存はbrainstormへ戻す。
- 人間向けの判断材料は現在の利用者の言語と平易な言葉で提示する。
- 正本spec、正本plan、ROADMAPは現在の利用者の言語で記述し、利用者が翻訳を介さず意味を確認できるようにする。
- 条項ID、状態名、schema fieldなど機械処理に必要な識別子は英語を使用してよいが、
  その意味と判断材料は現在の利用者の言語で記述する。
- 未決定事項を実装者やreviewerが補完しない。

### reviewを収束させる

- 初回reviewでfinding集合を固定する。
- 各findingへ再現テスト、静的検査、または明示的な人間ゲートを割り当てる。
- 修正後は固定findingと関連diffだけを再確認する。
- 再reviewで見つかった別問題は現在の合否へ追加せず、後続候補として分離する。
- INFOは修正ループへ入れない。
- second reviewerは現在の実行でflagまたは対話により人間が明示した場合だけ、一度だけ起動する。許可を持ち越さず、自動再試行しない。

## 移行順序

```mermaid
flowchart LR
    P0[0 基準を修復] --> P1[1 Brainstorm]
    P1 --> P2[2 Plan]
    P2 --> P3[3 Implement]
    P3 --> P4[4 Review]
    P4 --> P5[5 Recovery]
    P5 --> P6[6 Adapters]
    P6 --> P7[7 Work modes]
    P7 --> P8[8 UI workflow]
```

矢印は候補順序を示すだけで、自動進行を意味しない。

## Phase 0: 移行基準の修復

### 目的

再移行の開始地点と、今後越えてはいけない境界を明確にする。

### 対象

- 失敗した実装ブランチを未採用の記録として保持する。
- `main`上の正本spec、brainstorm記録、トークン効率化資料を確認する。
- 既存の英語specを、条項IDと意味を維持した日本語specへ置き換える。
- spec内の`core`が共有runtimeを意味しないことを明記する。
- specification verificationを独立skillとして移植しないことを明記する。
- Agent Skills標準準拠とskill単体配布を受入条件へ追加する。
- 最初の移行対象である旧`brainstorm`について、`SKILL.md`だけでなく直接参照される
  references、scripts、fixtures、共有契約まで読む。
- 旧`brainstorm`のsource auditを作り、利用者価値、責務、trigger、依存関係、永続状態、
  人間ゲート、機械検証、既知の失敗、トークン要因、残す挙動、捨てる挙動を記録する。
- 後続skillは移行直前に同じsource auditを行う。全skillの調査完了をPhase 1の開始条件にしない。
- 直接依存と共有契約を可視化し、単独で読んだだけでは判断できない責務を明示する。

### Source auditの必須項目

| 項目 | 記録する内容 |
|---|---|
| Source | 読んだ`SKILL.md`、references、scripts、fixtures、共有契約とsource revision |
| Trigger | 何をきっかけに起動するか |
| User value | 利用者のどの摩擦を解決するか |
| Responsibility | そのskillが所有する責務 |
| Dependencies | 他skill、共有契約、外部tool |
| Persistent state | 保存する状態、保存先、寿命 |
| Human gates | 人間が判断する場所と提示内容 |
| Mechanical checks | script、test、validator、未検証部分 |
| Token costs | 長い文書、再読、subagent、review loop |
| Known failures | 漏れ、儀式化、非収束、互換性問題 |
| Destination | 移植、統合、後回し、rules、meta、UI、廃止 |
| Rationale | その行き先を選ぶ理由 |
| Acceptance fixture | 移行後も維持する観測可能な挙動 |
| Excluded behavior | 意図的に捨てる挙動と理由 |

### 対象外

- workflow skillの実装
- 失敗ブランチからのコード移植
- skill名だけに基づく分類
- 新しい共通runtimeの選定

### 完了条件

- 日本語の移行境界を人間が説明できる。
- 旧`brainstorm`に読了したsource一覧とsource auditがある。
- 旧`brainstorm`の直接依存と共有契約が列挙されている。
- 旧`brainstorm`から残す挙動と捨てる挙動が証拠から決まり、受入fixtureと理由がある。
- 未決定の設計事項が、後続planへ紛れ込まない。
- Phase 1だけを対象とした新しいplanを作成できる。

## Phase 1: Brainstorm vertical slice

### 利用者価値

広い依頼を独立した利用者価値へ分け、最初の一フェーズだけを詳細化する。対話の途中で
compactや中断が起きても意味を失わず、利用者が直接読める仕様集合とplan readiness結果を作る。

### 統合する責務

- 旧`brainstorm`の対話と要件深掘り
- 旧`ledger`の合意、禁止、未決定、委任、改訂の管理
- 旧`decision-journal`のうち、高影響判断に必要な選択肢、採否理由、証拠、再検討条件
- 旧`spec-verify`のうち、条項抽出、projectに適した検証方法の選択、検証不能項目の検出、反例の記録

これらは一つのbrainstorm体験へ統合する。`ledger`、`decision-journal`、`spec-verify`を
独立した利用者向けskillとして作らない。

### 成果物

```text
skills/ba0918-brainstorm/
├── SKILL.md
├── scripts/
├── references/
└── fixtures/
```

- 現在の利用者の言語による正本spec
- 広い依頼から分けた全体フェーズと、最初に詳細化する一フェーズ
- 合意、禁止、未決定、委任、却下、改訂、現在位置の復元可能なprogress
- plan readinessの合否と不足項目
- 条項ごとの観測可能な成功条件、反例または既知の失敗、projectに適した検証方法
- 機械検証できない項目に対応する人間ゲート

brainstormはplan生成、ideaのarchive・drop、cycle開始を所有しない。

### 必須fixture

- 今回のような広い移行依頼を一つのplanにせず、全体フェーズと最初の一フェーズを提示する。
- compact後も合意、禁止、未決定、委任、却下、改訂、次の論点が復元される。
- 意味が変わらない会話では状態を書き換えない。
- 同じsessionへの同時更新を上書きまたは自動mergeせず、競合として停止する。
- wrapと承認の成功後はprogressを除去し、失敗時は再開可能な状態で残す。
- 高影響判断の理由と再検討条件が残る。
- PBTに向かない条件を無理にPBTへ変換しない。
- 人間判断が必要な条件を自動成功にしない。
- 利用者が読めない言語のspecまたはplanを承認対象にしない。
- planで未合意のruntime、保存方式、skill分割、architectureを補完しない。
- 明示許可なしにsecond reviewerを起動しない。
- 旧idea memoを新形式へ自動変換しない。

### 完了条件

- skill単体がAgent Skills標準検証を通る。
- まず利用者指定の低コストな`opencode --auto` process backend上で、対話から承認までの一本が実際に動く。
- Claudeでの実測は利用可能になるまで保留し、現在phaseの完了を妨げない。
- Codexで実測する場合は`gpt-5.6-luna`を明示し、既定modelや`gpt-5.6-sol`を使わない。
- `ba0918-skill-regression`の同じscenarioを利用可能なbackendで実行し、結果をbackend別の独立した証拠として記録する。
- 固定fixtureが、重大な仕様漏れと不適切な検証方法を検出する。
- 旧版との品質・操作・トークン比較が記録される。
- 人間が現在の利用者の言語による正本specを読み、意味を承認する。

### 現在の検証状況

- `opencode-go/deepseek-v4-flash`で広域依頼分割、compact後の復元と競合拒否、利用者言語のwrap/readinessを最終contractに対して再実測し、三scenarioがPASSした。
- 承認前draftをchatだけで提示し、fileを変更しないことをworktreeで確認した。
- 現在のbehavior surfaceを`regression-lock.json`へ記録した。
- Phase 1専用acceptance runで、同一progressの作成、日本語draft提示、人間承認、承認内容と同一hashの正本反映、内容確認、progress除去を順に確認した。
- 旧版`claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`と同一入力、同一`opencode-go/deepseek-v4-flash` backendで比較した。旧版は14 request、197.9秒、input 49,109、output 15,092、reasoning 1,292、cache read 288,768 token、$0.023638796だった。新版の有効runは5 request、75.7秒、input 16,639、output 2,450、reasoning 5,941、cache read 73,472 token、$0.009712944だった。
- 旧版は初回応答で重要な反例を深く問う一方、六つの質問と利用不能な自動second reviewerを起動した。新版は全体を独立phaseへ分け、次の重要判断を一問に限定し、無許可の外部呼出しとfile更新を行わなかった。
- 新版の初回比較runはreport生成後にbackend processが終了せず300秒でtimeoutしたが、同一条件の一回再実行では再現しなかった。未確認事項としてruntime固有の単発timeoutを残す。
- 旧版の全42契約を固定revisionから照合した。plan/archive/drop/cycle、旧idea memo、強制wrap、自動second reviewerは承認済みspecによる責務分離または安全gateを根拠に移行しない。
- 最終監査で見つかったpre-wrap自己監査、保存先policyのfail-closed処理、機密情報の人間確認境界、人間不在時の再開可能な停止、完了summary、open question契約を補い、unit test 11件とskill interface静的検査を通した。

重要機能の欠落、安全制約違反、重大な品質劣化は残っていないため、最終判定を「移行可」とする。Phase 1は完了とし、このrunではPhase 2へ進まない。

### Phase 1 acceptanceと旧版比較の完了条件

Phase 1のacceptanceと旧版との比較は、次の条件をすべて満たしてから完了とする。

- 既存の三つの回帰scenarioは変更せず、承認成功pathをPhase 1専用の独立したacceptance runとして検証する。
- 同一runでprogress作成、日本語draft提示、人間承認、正本更新、内容確認、progress除去の順序を証明する。
- 旧版はclaude-skillsの固定revision 57bb6f06aecdf191d46d99d9a3283233a26ecfddとし、同一入力で新版と比較する。
- 最終比較では要求充足、曖昧さの扱い、重要事項の深掘り、不要な承認要求、正本反映、失敗時の透明性を評価する。
- 重要機能の欠落、安全制約違反、重大な品質劣化を平均点で相殺してはならない。
- 正当な削除は承認済みspecの廃止、置換、責務移管を根拠とし、spec外でも互換性、安全性、データ保護、中核価値への重大影響を確認する。
- 低コストな契約完全性検査を先に行い、同一入力による内容品質の実測は最後に限定する。
- 最終評価は移行可、修正後に再評価、移行不可のいずれかで判定し、根拠と未確認事項を記録する。

## Phase 2: Plan

### 開始条件

Phase 1が完了し、brainstormが生成するspec、検証契約、反例の形式が実利用で安定している。

### 利用者価値

承認済み仕様を、実装者が勝手に意味を補わない実行計画へ変換する。

### 対象

- 承認済み条項、検証契約、反例からplanを生成する。
- 正本planは現在の利用者の言語で、変更箇所、変更しない箇所、外部影響、主要リスク、完了証拠を示す。
- 未決定事項、証拠不足、依存関係不明をplan作成前に拒否する。
- 正本と同一内容の草稿を人間が確認した後にだけ、正本planを書き込む。
- plan本文を進捗更新に使わず、後続工程が必要証拠から進捗を導出できるようにする。
- 未完了planを履歴全体から探さずに済む、再構築可能な内部索引を持つ。
- 現在対象planの切替では人間確認を必須とし、dirty worktreeを再開可能に隔離できない場合は停止する。

### 対象外

- 要件の追加や再解釈
- 実装
- review
- 複数planの並列実行
- TDD、branch、worktree操作
- resume、checkpoint、完了判定
- 手書きstatus、session history、plan本文の進捗checkbox

### 完了条件

- 一つの小規模fixtureをplanへ変換できる。
- 全plan項目がspec条項と検証条件へ追跡できる。
- 人間が正本plan全体だけで変更範囲、非変更範囲、外部影響、主要risk、完了証拠を判断できる。
- 人間確認前に正本planと未完了plan索引を変更せず、確認内容と同じidentityのplanだけを正本化する。
- runnerがstatus更新を省略しても、証拠がない項目を未完了として安全に扱える。
- 既存planの無言の置換、自動abandoned、dirty worktreeからの変更持越しを拒否する。
- 旧planのstatus、session history、resume、checkpoint、TDD、caller-supplied modeの処遇がsource auditから追跡できる。
- plan内部表現は、実測上の必要性が出るまで大規模な共有runtimeにしない。

### 現在の設計状況

- Phase 2固有の承認済み仕様と旧planのsource auditを`docs/spec/plan-skill-migration.md`へ記録した。
- plan skillはplan作成と手順revisionに限定し、TDDと実装をPhase 3、resumeとcheckpointをPhase 5へ移す。
- `status.md`、`session-history.md`、plan本文の進捗checkbox、headless自動abandonedを移植しない。
- 通常の実行対象は一件とするが、保留中の未完了planは複数保持できる。並列実行は明示的な別経路が所有する。
- 正本plan全体を現在の利用者の言語で書き、LLMだけが読む規範層を作らない。

### 現在の検証状況

- `ba0918-plan`を薄い`SKILL.md`、選択的に読む三つのreference、決定的なartifact helperとして実装した。通常の作成pathは136行、既存plan切替を含むpathでも174行のinstructionを読む。
- Python `unittest`は既存11件とplan用9件の合計20件がPASSした。identity不一致、path traversal、symlink、既存planの確認なし切替、dirty worktree、revisionのin-place変更を拒否する。
- `validate_repo.py`、三つのfixture schema、Markdown参照、`regression-lock.json`のfreshnessとcoverageを検証した。`skills-ref`実行体は環境に存在しないため、その名称での検証だけは未実施である。
- `opencode-go/deepseek-v4-flash`で、完全入力の日本語plan、不完全入力のbrainstorm返却、既存planとdirty worktreeの保護を再実測した。全critical条件をartifactとbaseline hashから再判定し、三scenarioをPASSとして現在のbehavior surfaceをlockへ記録した。
- 回帰中に、確認前のscratch draft作成、正本本文外へのplan ID/revision表示、仕様外の入力class追加を検出した。各原因を修正し、影響scenarioだけを再実行して固定した。
- skill単体の受入では、第一clientが正本全文、保存先、identityを提示してfileを変更せず停止し、確認済みbytesを受け取ったpublication clientが正本化、索引登録、読戻しidentity確認、一時file削除まで完走した。正本と索引は`sha256:53754da436ec3538ec1ed25887364c15eb52d3cae5b0a73ddacfea89eed93d9a`で一致し、`status.md`と`session-history.md`は作られなかった。
- OpenCode 1.18.18の`--session`による同一session継続は二回とも無出力でtimeoutした。部分書込みはなかった。確認済みbytesとidentityを明示した新規clientではpublicationが成功したため、skillのpublication契約とは分離したclient runtimeの未確認事項として残す。
- 同一入力・同一backendで固定revision`claude-skills@57bb6f06aecdf191d46d99d9a3283233a26ecfdd`の旧planと比較した。旧版は264.9秒、38 tool call、input 53,630、output 5,815、reasoning 25,343、cache read 1,147,392 token、約$0.040394624だった。新版の成功した草稿提示とpublicationの合計は86.2秒、25 tool call、input 56,553、output 6,664、reasoning 1,649、cache read 326,400 token、約$0.02021304だった。
- 旧版は質問なしでplanを書いたが、人間確認前に`status.md`、artifact policy、workspace policy、`.gitignore`と複数artifact directoryまで作成した。新版は人間が読む同一正本を確認対象にし、status、session history、TDD、resume、checkpointを移植せず、仕様外の意味を追加しなかった。

重要機能の欠落、安全制約違反、重大な品質劣化は残っていないため、最終判定を「移行可」とする。Phase 2は完了とし、このrunではPhase 3へ進まない。

## Phase 3: Implement and Cycle

### 開始条件

Phase 2のplanを人間が確認し、実装開始を明示している。

### 利用者価値

合意済みplanを専用worktreeでRED、GREEN、REFACTOR、commitの証拠付きで実装し、
独立reviewへ渡せる状態を作る。

### 対象

- `plan-implement`相当のTDD実装を一つの`ba0918-cycle`へ統合する。
- planを明示入力、直前のpublication結果、正常なcurrent plan索引から安全に解決する。
- repository単位claim、専用branch、linked worktreeへ実行をbindする。
- 現在の実行agentが直接TDDを実行し、nested delegationを行わない。
- plan、spec、worktree、oracle、write scopeのidentityを各境界で再確認する。
- RED、GREEN、REFACTOR、commitをimmutable eventとしてplan項目へ結び付ける。
- blocking failureでは追加編集を止め、worktree、commit、証拠を保持する。

### 対象外

- review policy、fix loop、final gate
- resume、checkpoint、Recovery
- dependency解析による部分継続
- parallel cycle
- merge、publication、issue管理
- worktree cleanup
- status、session history、plan本文または進捗fileの更新
- legacy artifactと旧cycleの後方互換

### 完了条件

- 一つの承認済みplanを、専用worktreeの実コード変更、GREEN、step単位commitまで完走できる。
- production codeを書く前に、承認済み条項に対応するREDを期待した理由で確認する。
- 意図しないREDをproduction変更とcommitの前に拒否する。
- spec、plan、worktree、oracleのidentity driftを追加編集前に拒否する。
- fresh sessionが会話履歴へ依存せず、正本とbindingから同じgateを実行できる。
- 正常、identity drift、意図しないREDの三scenarioを実agentで検証する。
- Phase 4が同じbranch、worktree、commit、evidenceを受け取れる。
- Phase 3はplan全体の完了、再開、cleanupを宣言または実行しない。

## Phase 4: Review

### 開始条件

Phase 3でGREENと実装証拠が得られている。

### 利用者価値

問題を見つけながら、findingを無限に増やすreview loopを発生させない。

### 対象

- 初回reviewからstable findingを生成する。
- severityと必要actionを分離する。
- 同じ原因のfindingをまとめる。
- findingごとに再現oracleを固定する。
- 修正後は未解決findingと関連diffだけを再確認する。
- 必須security・release gateと任意second reviewerを分離する。

### 対象外

- 全文敵対reviewの反復
- INFOの自動修正
- 再review中の新規finding追加
- 明示されていないsecond reviewer

### 必須fixture

- 全テストGREEN後、reviewのたびに新しいfindingが追加されるケースを拒否する。
- 同じfindingのoracleがGREENなら、そのfindingを閉じる。
- 別問題は現在の合否へ混ぜず、後続候補へ分離する。

### 完了条件

- 固定finding集合が有限回で収束する。
- review一回あたりの入力範囲とトークンが記録される。
- 旧版より全文再読とreview回数が減っている。

## Phase 5: Artifacts, Handoff, and Recovery

### 開始条件

Phase 1から4までで、保存すべき実データと再開要件が確定している。

### 利用者価値

compact、セッション切断、必須provider停止の後でも、意味と再開位置を失わない。

### 対象

- `.agents/artifacts`、`.agents/runtime`、`.agents/tmp`の責務分離
- 合意、spec revision、証拠、finding、再開位置の保存
- 古い証拠のstale化
- 曖昧な旧artifactの拒否または人間への差し戻し

### 完了条件

- Phase 1から4の中断fixtureを復元できる。
- 保存先、schema、寿命、migrationを明示している。
- 各skill単体配布を壊す共有依存を導入していない。

## Phase 6: Follow-up adapters

各項目を別フェーズ、別brainstorm、別planとして移す。一括移植しない。

候補順序:

1. `iterate`
2. `issue`
3. `parallel-cycle`
4. `github-issue`
5. `goal-decomposition`
6. `goal-loop`
7. `loop-triage`

各adapterはPhase 1から5の公開成果物だけを利用する。内部実装への直接依存を追加しない。

## Phase 7: General work modes

次のskillはtrunk完成後に個別移植する。

- `investigate`
- `systematic-debugging`
- `refactor`
- `sweep-fix`
- `problem-solving`
- `doc-check`
- `doc-write`
- `doc-audit`
- `generate-review-rules`
- `commit`
- `attack-review`
- `codebase-review`
- `review-deps`
- `review-testing`

一つのskillを一つの移行単位とし、必要なworkflow連携だけを追加する。

## Phase 8: UI workflow

UI workflowはcore移行と分離する。次を独立してbrainstormする。

- design guideとdesign system
- mockup生成
- pixel comparison
- visual regression
- accessibility
- UXの人間ゲート

UI固有の判断や証拠形式を、汎用workflowへ先回りして追加しない。

## このリポジトリへ移さないもの

### agentic-rulesで所有するもの

- design
- placement
- secrets
- TDD
- testing
- commit
- release
- delegation
- verification
- reuse
- scaffold
- human-readable

### agentic-metaで所有するもの

- context audit
- prompt tuning
- skill improvement
- skill interface audit
- skill regression
- skill reviewer
- trigger evaluation
- 将来のトークン効率改善skill

このリポジトリでは、公開済みのruleやmeta能力を明示的に利用するだけとし、重複実装しない。

## 各フェーズの開始テンプレート

各フェーズ開始時に、最低限次を現在の利用者の言語で提示する。

```text
利用者が得るもの:
今回移す責務:
今回移さない責務:
Agent Skills上の配布単位:
実行方法:
機械検証方法:
人間が判断する項目:
旧版との比較方法:
このフェーズの停止条件:
```

この項目を人間が理解できる状態になるまでplanを作成しない。
