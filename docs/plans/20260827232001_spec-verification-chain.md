# 仕様要求と検証の実装接続

**Verification coverage:**

- `docs/spec/workflow.md` / `plan → cycle: 承認済みの手順書` -> `1:test`
- `docs/spec/plan.md` / `機械が読む構造` -> `1:test`
- `docs/spec/plan.md` / `完了の示し方` -> `1:test`
- `docs/spec/implement.md` / `手順書の読み方` -> `1:test`
- `docs/spec/implement.md` / `検証の対応から手順を決める` -> `1:test`
- `docs/spec/brainstorm.md` / `検証できる仕様にする` -> `2:artifact`
- `docs/spec/plan.md` / `仕様書を書き写さない` -> `2:artifact`
- `docs/spec/plan.md` / `機械が読む構造` -> `2:artifact`
- `docs/spec/plan.md` / `完了の示し方` -> `2:artifact`
- `docs/spec/plan.md` / `各手順に書くこと` -> `2:artifact`
- `docs/spec/plan.md` / `独立したレビュー` -> `2:artifact`
- `docs/spec/implement.md` / `手順書の読み方` -> `2:artifact`
- `docs/spec/implement.md` / `検証の対応から手順を決める` -> `2:artifact`
- `docs/spec/review.md` / `仕様要求と検証の対応を確かめる` -> `2:artifact`
- `docs/spec/cycle.md` / `検証不足を見つけたとき` -> `2:artifact`
- `docs/spec/workflow.md` / `plan → cycle: 承認済みの手順書` -> `2:artifact`
- `docs/spec/workflow.md` / `implement → review: 作業ブランチと証拠` -> `2:artifact`
- `docs/spec/workflow.md` / `AI を実際に走らせる確認（実測）は、条件が明示されたときだけ` -> `2:artifact`

## 目的

承認済み仕様書の要求を、plan の手順、実行可能な検証、既存 evidence、review の意味判断まで
切れ目なく辿れるようにします。runtime は対応の存在と実行結果だけを保証し、要求の選定漏れや
検証の反例感度は plan と review が判断します。

今回の plan 自体は、新形式を読む runtime を更新するための最初の plan です。現行 cycle は旧
`Target specifications` 形式しか読めないため、この plan の実装では cycle の起動経路を使いません。
承認済みの新形式 plan を正本として、Step 1 は通常の RED → GREEN → REFACTOR、Step 2 は artifact
作成と独立 review で進めます。実装場所は専用 branch と linked worktree を使い、Step ごとに commit
します。新形式を読めるようになった後の plan から通常の cycle を使います。

## 実装方針

- `tools/workflow-runtime/plan/plan_artifact.py` を唯一の parser 正本とし、vendor の既存配布経路で
  plan と implement の skill へ複製します。共有 module や別 parser は増やしません。
- `Verification coverage` から仕様パス、見出し、Step 番号、完了種別を読み、連続する Step 見出し、
  coverage と Step の相互被覆、同一 Step の完了種別一致、仕様見出しの一意性を検査します。
- bind と rebound は承認済み plan から完全な Step contract を導きます。呼び出し側が Step contract
  を渡す引数は削除します。実行中の対象 Step を指定する stage と record-commit の引数は残します。
- evidence version 2、既存 event、保存場所、単一 writer、rebound mapping は維持します。新しい
  schema、event、store、依存、互換経路、移行処理は作りません。
- 仕様適合の意味判断は skill と評価 fixture へ置きます。runtime に自然言語要求の解釈、要求 marker、
  永続 ID、形式要求言語を追加しません。
- skill 文言の live LLM E2E は実行しません。scenario、model、token 予算が明示されていないため、
  静的 fixture、構造検査、独立 review を直接証拠にします。
- cycle の evidence runtime を使えない今回だけ、観測した RED、GREEN、REFACTOR のコマンドと結果、
  各 commit の差分、全差分の最終 review 結果を bootstrap の証拠にします。過去の実行結果を新 runtime
  の event として後付けしません。
- 最終 review は plan 承認 commit から専用 branch の HEAD までの全差分を対象にします。main に直接
  実装 commit を積まず、cycle を使わないことを branch / worktree 規則の例外へ広げません。

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
        planning.py
        repository.py
        types.py
    tests/
      implement_evidence_test.py
      implement_runtime_test.py
      plan_artifact_test.py
skills/
  ba0918-brainstorm/
    references/
      wrap-readiness.md
  ba0918-plan/
    SKILL.md
    references/
      creation.md
      readability.md
    scripts/
      plan_artifact.py
  ba0918-implement/
    SKILL.md
    references/
      artifacts.md
      evidence.md
      execution.md
    scripts/
      plan_artifact.py
      runtime/
        cli.py
        context.py
        planning.py
        repository.py
        types.py
  ba0918-review/
    SKILL.md
    references/
      review.md
  ba0918-cycle/
    SKILL.md
evals/
  cases/
    ba0918-brainstorm/
      wrap-language-readiness.yaml
    ba0918-plan/
      create-human-readable-plan.yaml
      reject-incomplete-source.yaml
    ba0918-implement/
      continue-safe-work.yaml
    ba0918-review/
      review-document-and-skill-handoff.yaml
    ba0918-cycle/
      continue-safe-omission.yaml
      stop-on-missing-design.yaml
  inputs/
    ba0918-brainstorm/
      wrap-language-readiness.md
    ba0918-plan/
      existing-plan.md
      incomplete-change.md
      small-approved-change.md
    ba0918-implement/
      safe-autonomy.md
    ba0918-review/
      document-and-skill-mismatch.md
    ba0918-cycle/
      missing-persistence-decision.md
      unplanned-safe-file.md
```

## Step 1: plan parser と実装 runtime を新形式へ切り替える

目的は、承認済み plan の構造を一度だけ解釈し、bind と rebound が同じ Step contract を使う状態を
作ることです。この Step が終わるまで現行 cycle は使わず、この plan を直接読んで TDD を進めます。

前提は、仕様コミット `1dff7b9` が履歴にあり、作業ツリーの仕様書と一致していることです。

変更対象は Scope 内の `tools/workflow-runtime/plan/`、`tools/workflow-runtime/implement/runtime/`、
対応する unit test、vendor で生成される plan / implement の script 複製です。

直接検証は、次の反例を fixture にした parser と runtime の unit test です。

- 旧 `Target specifications`、存在しない仕様パス、存在しない見出し、同一ファイル内で重複する
  見出しを拒否する
- coverage 行の構文不正、未対応の完了種別、欠番または重複した Step、coverage に無い Step、
  Step に結ばれない coverage、同一 Step の完了種別不一致を拒否する
- `check` Step に `Checks` が無いか空なら拒否し、`test`、`artifact`、`external` Step に `Checks` が
  あれば拒否する。複数の check command は宣言順を保って読む
- many-to-many の coverage を受け入れ、plan に現れる順序で `[{id, completion}]` を導く
- bind と rebound が caller 指定の Step contract を受け取らず、承認済み plan から同じ contract を
  binding または rebound event へ記録する
- stage と record-commit は、導出済み contract に含まれる実行対象 Step だけを受け入れる
- artifact の checks、external の要約と条件判定、test の RED / GREEN / REFACTOR という既存 evidence
  契約を変えない

RED では上の反例と正常系を先に追加し、旧 parser と caller 指定 bind/rebound が失敗することを確認
します。GREEN では最小の parser・型・runtime 接続で通し、REFACTOR では parser の正本が 1 つで
vendor 複製が一致することまで同じコマンドで確認します。

プロジェクトのテスト実行コマンドは次です。unit test と vendor parity を一つの portfolio として
同じコマンドで RED、GREEN、REFACTOR を記録します。

```bash
python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py' && bunx agentic-skill-vendor verify
```

実装側に任せるのは、公開されていない内部型の名前と pure helper の分け方だけです。parser の構文、
拒否条件、Step contract の導出元、既存 evidence の意味は変えません。

仕様見出しを一意に解決できない、新しい依存が必要、既存 evidence version 2 を変えないと実現
できない、または rebound mapping の意味を変える必要が出た場合は、実装を進めず brainstorm へ
戻します。通常の helper や予定 test file の不足は理由を記録して自走で補います。

## Step 2: 各 station の skill と評価 fixture を検証チェーンへ揃える

目的は、brainstorm が検証可能な仕様を作り、plan が適切な portfolio を設計し、implement が実行し、
review が反例感度まで判断し、cycle が安全な検証不足を止まらず補う責務を、各 skill の入口で実際に
選ばれる指示へ反映することです。Step 1 の parser と runtime が通っていることを前提にします。

変更対象は Scope 内の5つの skill と直接参照される文書、既存の評価 fixture です。仕様本文は
書き写さず、各 station の責務、次へ渡す物、戻す条件だけを置きます。

直接検証は、独立 reviewer が仕様節、skill、reference、評価 fixture を対応づけ、少なくとも次の
反例を検出できると判断することです。

- 成功例だけで反例や判定基準が無い仕様を plan-ready にする
- 要求本文を plan へ複製する、または補助検査だけで仕様適合を示す
- plan skill が旧 `Target specifications` や本文の `Completion` を生成する、または `check` Step に
  `Checks` を書かない
- implement skill が `Verification coverage` ではなく caller の Step contract を正本として扱う
- 対象に合う PBT、integration、E2E などを検討せず、形だけの unit test を選ぶ
- bind/rebound の Step contract を caller が手入力する
- 安全に補える検証不足で cycle が人を止める
- 新しい依存、外部環境、権限、未決定の要求を cycle 内で勝手に補う
- scenario、model、token 予算なしで skill 文言の live LLM E2E を要求または実施済みと表現する

形式上の補助検証として `bunx agentic-skill-vendor verify` と Markdown の相対参照確認を行います。
live LLM eval は直接検証に含めません。評価 fixture は将来の明示実行に備えた静的な契約例として
独立 review の対象にします。

Step 1 と Step 2 が終わったら、実装者とは別の reviewer が parser、runtime、tests、skill、reference、
評価 fixture を含む全差分を 1 回レビューします。指摘を直した後は、未解決の指摘、修正差分、影響を
受けた後続箇所だけを再レビューして収束させます。構造、前提、手順順、依存、完了条件、Scope、参照
仕様が変わった場合だけ全体レビューへ戻ります。

実装側に任せるのは、英語の指示文を簡潔にする語順と、既存 fixture のどれへ各反例を割り当てるか
だけです。skill の責務境界、停止条件、検証の強さを弱めません。

仕様の意味を skill だけでは一意に表現できない、新しい評価 runner や依存が必要、または live LLM
E2E が必要だと判断された場合は、条件を推測せず brainstorm へ戻します。単なる文言漏れ、fixture
漏れ、vendor 同期漏れは止まらず修正し、独立 reviewer には未解決所見と修正差分だけを戻します。

## 完了条件

- Step 1 のテスト portfolio が RED、GREEN、REFACTOR の順で実行され、最終的に全件成功している
- 新形式 plan を正本 parser が読み、bind と rebound の Step contract が caller 入力なしで一致する
- Step 2 の全 artifact が形式検査と独立 review を通り、仕様要求から検証までの意味上の漏れが無い
- bootstrap の全コード・test・artifact 差分を独立 reviewer が 1 回全体レビューし、全指摘が限定
  再レビューで解消している
- `python3 -m unittest discover -s tools/workflow-runtime/tests -p '*_test.py'` が全件成功する
- `bunx agentic-skill-vendor verify` が成功し、正本と配布用 script の差分が無い
- 新しい依存、event、evidence version、保存場所、互換経路、live LLM E2E が追加されていない
- 実装 commit が専用 branch / worktree に Step ごとに記録され、main に直接積まれていない

## 実装中に人へ返す条件

新しい外部依存、evidence version 2 の変更、保存形式または権限境界の変更、外部環境、不可逆な操作、
危険な対象、または仕様に無い重要な設計判断が必要になった場合だけ人へ返します。cycle を使わず
専用 branch / worktree で TDD することは合意済みであり、追加確認を求めません。
