# premise-and-slimming 実装の手順書

## Goal

承認より後の工程を人を待たずに進め、進まないときは仮定を 1 度疑ってから終えるように、ワークフローの skill 本文を直す。
その前に、各 skill から冗長な文章、重複する指示、フロンティアモデルに効果の薄い指示を削る。

## Specification

コミット済みの次の仕様書（`docs: 承認より後の工程を人を待たずに進め、進まないときは仮定を 1 度疑う` の commit 以降）。
この手順書は仕様書の見出しをリンクで参照し、本文を写さない。
実装者は各 step の前に、参照された見出しを必ず読む。

- [開発ワークフロー仕様](../spec/workflow.md)（変更の中心）
- [小さいタスク skill 仕様](../spec/iterate.md)（実装役の差し戻しの理由、読み替え、再開）
- [入口 skill 仕様](../spec/using-workflow.md)（「人を止める場面」の呼び名だけを直した）
- 理念（[docs/principles.md](../principles.md)）と用語集（[CONTEXT.md](../../CONTEXT.md)）

用語は用語集の定義で使う。
とくに「暫定の答え」「覆る条件」「仮定」「仮定の段」「仮定を疑う段」「人を止める場面」である。

開発ワークフロー仕様の冒頭には見出しが無い。
この手順書では、冒頭の「skill の肥大とは」で始まる段落から「LLM を走らせて振る舞いを比べる確認は」で始まる段落までを「肥大の段落」と呼ぶ。
行数の目安の扱いは、冒頭の「行数の目安は」で始まる段落と肥大の段落に従う。

## Approach and why

先に削り、後で足す。
足す変更（仮定を疑う段、終わり方、暫定の答え）は、cycle、review、implement の中心に入る。
重複や使われない言い回しを先に削っておくと、足す場所と食い違いが見えやすいからである。
削る commit と足す commit は分ける。
Step 1 は skill の指示の意味を変えない。
意味を変える変更は Step 2 以降でだけ行う。

削る物差しは肥大の段落である。
5 種類（無駄な指示、冗長な文章、フロンティアモデルに効果の薄い指示、重複する指示、一度に読む必要の無い文章）を基準に削る。
構造を分け、必要な所だけを一度に読ませる。
行数や語数を目標にしない。
書き方の規範として、実装者の環境に `ba0918-skill-authoring` skill があれば読む。
無ければ読まずに進む。
規範と仕様書が食い違ったときは仕様書に従う。

同じ校正を先に済ませた例が、公開リポジトリ kotowari の工程の skill にある（<https://github.com/ba0918/kotowari/tree/main/agent/skills>）。
読まなくてよく、読むためにネットワークへ出る必要があるなら読まない。
kotowari は、修正役に貼る契約、任意の席の起動の手順、仮定を疑う段を、それぞれ cycle か review の参照資料に分けている。
これは参考で、従う義務は無い。
kotowari 固有の物（整合のフェーズ、IR、`kotowari check`）は持ち込まない。

規則の正本は skill を全部通して 1 か所に置く（肥大の段落）。
今は「確かめ方が証拠として数えられる条件」の写しが 3 か所にある。
brainstorm の `SKILL.md`、plan の `references/step-template.md`、review の `references/oracle-evidence.md` である。
どれも `skills/ba0918-<name>/` の下にある。
Step 1 で review の参照資料の 1 か所に寄せ、brainstorm と plan には review skill の名前と参照資料の名前で指して読ませる。
この形は、cycle が今 review の参照資料を名前で読んでいるのと同じである。
skill 本文から仕様書をパスで参照しない縛り（`PROJECT.md`「縛り」）は変わらない。

CHANGELOG は、skill を変える commit と同じ commit の中で `Unreleased` に書く（`PROJECT.md`「配布と版」）。
Step 1 の校正は利用者から見える振る舞いを変えないので、まとめて 1 項目でよい。
Step 2 以降は skill の指示の意味が変わるので、項目に **BREAKING** を付ける。
CHANGELOG と commit メッセージには、参考にした外部資料の名前を書かない。
kotowari は利用者自身のリポジトリなので、名前を書いてよい。

### 手順書が決めた暫定の答え

仕様書が黙っている所のうち、この手順書が暫定の答えで決めた物を挙げる。
承認のときの判断点にも同じ物を載せる。

1. **reviewer が「暫定の答えとして報告された規則」を知る経路**。仕様書の受け渡しの表は、reviewer に implement や修正役の暫定の答えを渡すと書いていない。この手順書では、cycle がそれまでに受け取った暫定の答え（答えと覆る条件と、それが足した規則の場所）を、フルレビューと差分レビューの reviewer への指示に含める（Step 3）。覆る条件: 人が「reviewer には渡さず、終端で cycle が突き合わせる」と言ったら、その形に変える
2. **検査のコマンドが書かれたとおりには成功しない手順書の欠陥と、大筋を変える直し**。今の implement は、どちらも上流へ返す。仕様書の差し戻しの 3 つの理由のうち、「承認済みの手順書と矛盾する」に当たるものとして扱い、plan へ返す（Step 4）。覆る条件: 人が「どちらも暫定の答えで進めてよい」と言ったら変える
3. **description の書き方**。description は「いつ使うか」と起動の言葉にし、動き方の説明を本文へ寄せる。ただし、副作用を走らせてよい条件は description に残す。起動の言葉は消さない（Step 1）。覆る条件: 人が「description は今のまま」と言ったら、description を触らない

### この手順書を回す cycle への注記

肥大の段落は、校正の結果を 5 種類を見る項目として渡したレビューで確かめるとしている。
ただし、この手順書を回すときの cycle は改訂前の本文で動き、レビュー項目の入力をまだ持たない。
cycle を起動するメインセッションは、reviewer への指示に次の 2 つを足して渡す。

- 肥大の段落の 5 種類（新しく足した文にも当てる）
- iterate の新しい要求が、同じブランチに指摘 JSON が残っていても実装を飛ばさないこと

回帰の scenario は実走しない（人が明示していない）。
`regression-lock.json` も取り直さない（Out of scope）。

ブランチと worktree は、cycle を起動する前にメインセッションが作る。
この手順書の step には含めない。

## Scope of change

- `skills/ba0918-*/SKILL.md` と `skills/ba0918-*/references/`（8 つの skill すべて。参照資料の新設と削除を含む）
- `CHANGELOG.md`
- `README.md`（skill の一覧の説明が、変わった本文と食い違う箇所だけ）

この外は変えない。
とくに次の物は触らない。

- `docs/`、`CONTEXT.md`、`PROJECT.md`
- `evals/` と `regression-lock.json`
- `.claude-plugin/` と `package.json`

## Step order and prerequisites

Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Step 7 の順は固定。

- Step 1 が先なのは、削ってから足すためである
- Step 2（review）が cycle より先なのは、cycle が review の参照資料を名前で読み、委譲先に貼るからである。指摘の形と言い回しが決まってから cycle を書く
- Step 3（cycle）は、Step 4（implement）と Step 6（iterate）が参照する終わり方、仮定を疑う段、修正役の契約を決める
- Step 4（implement）は、cycle の終わり方 3 と 4 で受ける戻りの言い回しを cycle に合わせる
- Step 5（plan と brainstorm）は、implement と review の言い回しが決まった後に上流側を合わせる
- Step 6（iterate）は cycle の本文を名前で読み、表で読み替えるので、cycle が決まってから合わせる
- Step 7 は取り残しの確認で、全部の本文が決まった後に行う

## Verification map

- 肥大の段落と[確かめ方が証拠として数えられる条件](../spec/workflow.md#確かめ方が証拠として数えられる条件) → Step 1。Step 2〜7 でも、新しく足す文に肥大の段落を当てる
- 次の review の見出し → Step 2
  - [指摘 1 件の項目](../spec/workflow.md#指摘-1-件の項目)
  - [確かめ方を先に書く](../spec/workflow.md#確かめ方を先に書く)
  - [profile と観点](../spec/workflow.md#profile-と観点)
  - [別の文脈で行う](../spec/workflow.md#別の文脈で行う)
  - [呼ばれ方は 2 つ](../spec/workflow.md#呼ばれ方は-2-つ)
  - [Skill profile](../spec/workflow.md#skill-profile)
- [人が見るのは最終成果物だけ](../spec/workflow.md#人が見るのは最終成果物だけ) → Step 3、Step 4、Step 5
- [cycle](../spec/workflow.md#cycle) の節の各見出し → Step 3
- [implement](../spec/workflow.md#implement) の節の各見出し → Step 4
- [plan](../spec/workflow.md#plan) の節と、brainstorm の[ドメインの用語と境界を磨く](../spec/workflow.md#ドメインの用語と境界を磨く)、[仕様書に書く前の見直し](../spec/workflow.md#仕様書に書く前の見直し) → Step 5
- [小さいタスク skill 仕様](../spec/iterate.md)の各見出し → Step 6
- [入口 skill 仕様](../spec/using-workflow.md)の[判断に任せない物](../spec/using-workflow.md#判断に任せない物) → Step 7

## Left to the implementer

- 参照資料の分け方とファイル名。どう分けても、実行時に読まれる指示の意味が変わらない限りよい。新しい参照資料を作るなら、本文の中で「いつ読むか」を名指しする
- 英語の言い回しと、節の並び
- 指摘 JSON で、暫定の答えと試みの記録を表すキーの名前（仕様書の[委任](../spec/workflow.md#委任)のとおり、キー名は review の参照資料が決める）

## Stop conditions

開発ワークフロー仕様の[人が見るのは最終成果物だけ](../spec/workflow.md#人が見るのは最終成果物だけ)の 2 つの場面のほか、次のときは止めて plan へ返す。

- 仕様書の見出しどうしが矛盾していて、どちらに従っても他方を壊す（この手順書が写す改訂後の仕様書と、今の skill 本文との違いはこれに当たらない。違いを直すのがこの手順書の仕事である）

削る作業で、ある指示を残すか消すかが仕様書から決まらないときは、止めずに残す。
消すと仕様書のどの見出しの振る舞いが壊れるかを名指しできない指示は、短く書き直して残す（肥大の段落）。

## Test command

コードは書かないので、テストのコマンドは無い。
skill の形式の検査は `bunx skills-ref@0.1.5 validate skills/ba0918-<name>` である（`PROJECT.md`「検査」）。
`bun run lint:docs` は `docs/` だけを見るので、skill の変更の証拠にはならない。
この手順書自身の lint として走らせるだけでよい。
`bun install` が済んでいなければ先に走らせる。

各 step の意味の確かめは、cycle のレビューが行う。
各 step の完了は、変えたファイルと形式の検査で示す（Shown by: artifact）。

## Step 1 — 8 つの skill を校正する

Purpose: 8 つの skill から肥大の 5 種類を削り、規則の正本を 1 か所に寄せる。指示の意味は変えない。

Specification: 肥大の段落と「行数の目安は」で始まる段落、[確かめ方が証拠として数えられる条件](../spec/workflow.md#確かめ方が証拠として数えられる条件)。

Prerequisites: なし。

May change: 次の物だけ。

- `skills/ba0918-*/SKILL.md` と `skills/ba0918-*/references/`
- `CHANGELOG.md`
- `README.md`（description を変えた skill の一覧の行だけ）

やることは次のとおりである。

- 各 skill の本文と参照資料を 5 種類の物差しで読み、当たる文を削るか、短く書き直すか、参照資料へ移す
- 作者だけが知る文脈（環境の事実、品質の基準、道具の契約、判断の難しい場面、制約の理由）は長くても残す
- 今のモデルで起きうるか判断できない、過去の事故から生まれた禁止は、短く書き直して残す
- 同じ規則が skill をまたいで複数のファイルにあるときは、1 か所に寄せて他から指す。実行時に委譲先のプロンプトへ貼る指示（cycle が reviewer や修正役に貼る物）は重複に数えない
- 「確かめ方が証拠として数えられる条件」は review の `references/oracle-evidence.md` の 1 か所に残す。brainstorm と plan の写しは消し、review skill の名前とその参照資料の名前で指して読ませる。出典の 1 行（規則名と agentic-rules の版）も review 側にだけ残す
- description は「手順書が決めた暫定の答え」の 3 のとおりに直す。description を変えた skill は、`README.md` の skill の一覧の説明と食い違わないか確かめ、食い違えば一覧の行を直す
- 1 つの skill を 1 commit で直す。CHANGELOG の `Unreleased` には、校正したことと指示の意味は変わらないことを 1 項目で書く。項目は最初の commit で書き、以後の commit で必要なら書き足す

Done when:

- 8 つの skill それぞれについて、削った文、書き直した文、移した文を報告に挙げている。各文には、5 種類のどれに当たるかを添えている
- 「確かめ方が証拠として数えられる条件」の本文と出典の 1 行が、`skills/` の中で review の `references/oracle-evidence.md` にだけある
- 他の skill が名前で指している物が、校正の後も解ける。報告に、指す側と指される側の組を挙げ、それぞれを `rg` で引いた結果を添えている。対象は次の 3 つである
  - cycle が指す review の節の名前と参照資料のファイル名
  - iterate の読み替えの表が引く cycle の言い回し
  - brainstorm と plan が指す review の参照資料
- 各 skill について、本文が写している仕様書の節と読み比べ、消えた振る舞いが無いことを報告で述べている
- 各 skill の SKILL.md と参照資料の合計の行数を、変更の前と後で報告に挙げている（目標ではなく、レビューが責務の過剰を疑うための材料）

Shown by: artifact — 変えた `skills/ba0918-*/` の各ファイル。形式の検査は次のとおり。

1. 8 つの skill それぞれに `bunx skills-ref@0.1.5 validate skills/ba0918-<name>`
2. `rg -l "named operational producer" skills` が review の `references/oracle-evidence.md` の 1 行だけを出す
3. `rg -l "agentic-rules v" skills` が同じ 1 行だけを出す

Left to the implementer: 参照資料の分け方とファイル名、言い回し（手順書全体の「Left to the implementer」のとおり）。

Stop and hand back if: なし（手順書全体の Stop conditions のとおり）。

## Step 2 — review の指摘の形と規則を直す

Purpose: 対応の値から「人が決める」を外し、暫定の答えの項目、仕様書に無い規則の扱い、レビュー項目を review に入れる。

Specification: 次の見出し。

- [指摘 1 件の項目](../spec/workflow.md#指摘-1-件の項目)
- [確かめ方を先に書く](../spec/workflow.md#確かめ方を先に書く)
- [profile と観点](../spec/workflow.md#profile-と観点)（仕様書に無い規則や節の段落）
- [別の文脈で行う](../spec/workflow.md#別の文脈で行う)
- [呼ばれ方は 2 つ](../spec/workflow.md#呼ばれ方は-2-つ)
- [Skill profile](../spec/workflow.md#skill-profile)
- [往復とレビューの 2 種類](../spec/workflow.md#往復とレビューの-2-種類)（既知の指摘）

Prerequisites: Step 1。

May change: `skills/ba0918-review/SKILL.md`、`skills/ba0918-review/references/`、`CHANGELOG.md`。

Done when:

- 対応の値が `auto_fix`、`fix_and_verify`、`record_only` の 3 つで、`human_judgment` が `skills/ba0918-review/` に残っていない
- 指摘の形に暫定の答え（選んだ答えと覆る条件）の項目があり、直し方に意味の判断が要る指摘だけが持つ
- 機械で確かめられない指摘の確かめ方（理由と、人が読んで確かめる観点）と、確かめ方を先に書く要求の対象外が、仕様書の見出しと一致している
- 仕様書に無い規則や節の扱いが 3 通りに書かれている。差分が黙って足した物は削除の指摘（`fix_and_verify`、暫定の答えは「消す」）にする。暫定の答えとして報告された物は削除の対象外にする。差分より前からある物は `record_only` で「仕様書に無い」に挙げる
- 「暫定の答えとして報告された物」を reviewer が知るのは、呼んだ側が指示に含めた暫定の答えからである、と読める（「手順書が決めた暫定の答え」の 1）
- 既知の指摘が `record_only` の open と受け入れて閉じた物である
- reviewer への指示と、人が直接呼ぶときの指定物にレビュー項目がある
- Skill profile の `critical` は「人を止める場面を迂回するか承認済みの内容を変える」、`light` の対象は「人を止める場面の迂回」の言葉で書かれている
- CHANGELOG の `Unreleased` に **BREAKING** の項目がある

Shown by: artifact — `skills/ba0918-review/` の変えたファイル。形式の検査は次のとおり。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-review`
2. `rg -n -i "human_judgment|human judgment" skills/ba0918-review` の一致が無い

Left to the implementer: 暫定の答えのキーの名前と JSON の中の置き場所。

Stop and hand back if: なし（手順書全体の Stop conditions のとおり）。

## Step 3 — cycle に暫定の答え、仮定を疑う段、新しい終わり方を入れる

Purpose: cycle の入力、ループ、修正役の契約、仮定を疑う段、終わり方、再開、判断、受け渡し、終端報告を仕様書に合わせる。

Specification: 次の見出し。

- [人が見るのは最終成果物だけ](../spec/workflow.md#人が見るのは最終成果物だけ)
- [cycle](../spec/workflow.md#cycle)（入力のレビュー項目）
- [往復とレビューの 2 種類](../spec/workflow.md#往復とレビューの-2-種類)
- [ループの形](../spec/workflow.md#ループの形)
- [仮定を疑う段](../spec/workflow.md#仮定を疑う段)
- [終わり方](../spec/workflow.md#終わり方)
- [再開](../spec/workflow.md#再開)
- [判断は cycle が持つ](../spec/workflow.md#判断は-cycle-が持つ)
- [受け渡し](../spec/workflow.md#受け渡し)
- [終端報告](../spec/workflow.md#終端報告)

Prerequisites: Step 2。

May change: 次の物だけ。

- `skills/ba0918-cycle/SKILL.md` と `skills/ba0918-cycle/references/`（新設を含む）
- `skills/ba0918-review/references/finding-schema.md`（指摘 JSON に試みの記録を足すため）
- `CHANGELOG.md`

Done when:

- 入力にレビュー項目があり、フルレビューと差分レビューの委譲に毎回入る
- フルレビューと差分レビューの reviewer への指示に、それまでに受け取った暫定の答え（答えと覆る条件と、それが足した規則の場所）が入る（「手順書が決めた暫定の答え」の 1）
- 見えている指摘と既知の指摘から `human_judgment` が消えている
- `security` の指摘はループで直す。止まるのは、秘密情報の露出を述べる指摘と、直すのに場面 1 に当たる操作が要る指摘だけである
- 修正役の契約で、暫定の答えが付いた指摘はその答えで直す。新しく判断が要ったときは暫定の答えで進めて報告する。差し戻しは承認済みの内容との矛盾だけである
- 修正役には implement の仮定を疑う段を持たせない。再修正の前に確かめる物の呼び名が「仮定」である
- 仮定を疑う段の 4 つの手順、1 回の実行の定義、試した後の連続のリセット、比較の基点で試したかを決めること、反例が書かれている
- 終わり方 3 に 6 つの条件がある。レビューの結果で決まる 4 つは段に入る。review の失敗と implement の戻りは、段を経ずに終える
- 「修正を入れた所の近く」が cycle の判断として書かれ、計算の手順になっていない
- 終わり方 4 が、差し戻しの 3 つの理由と、段が矛盾で終えた場合を持つ
- 再開で、終わり方 3 の 3 つの連続を新しい起動でリセットし、試みの記録は起動をまたいで読む。「2 つの連続」の言い回しが残っていない
- 意味の判断が要るのに reviewer が暫定の答えを付けていない指摘に、cycle が答えと覆る条件を付ける
- implement からの戻りに、暫定の答えと覆る条件と、返すときの仮定の段がある
- 指摘 JSON の形（`finding-schema.md`）に試みの記録があり、各試みが比較の基点を持つ。修正ごとの記録は無い
- 終端報告に次が入っている。暫定の答えと覆る条件、「仕様書に無い」の規則と足す案、試みごとの仮定の段、矛盾で終えたときの直し案、暫定の答えを覆す入口（iterate）
- SKILL.md と参照資料の合計の行数が目安 110 を超えるなら、足した節ごとに、実行者がその場で要る理由を報告で述べている
- CHANGELOG の `Unreleased` に **BREAKING** の項目がある

Shown by: artifact — `skills/ba0918-cycle/` と `finding-schema.md` の変えたファイル。形式の検査は次のとおり。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-cycle`
2. `bunx skills-ref@0.1.5 validate skills/ba0918-review`
3. 次の `rg` の一致が無い
   - `rg -n -i "human_judgment|missing design decision" skills/ba0918-cycle skills/ba0918-review`
   - `rg -n -i "both of ending 3" skills/ba0918-cycle`

Left to the implementer: 仮定を疑う段を本文に置くか参照資料に出すか。試みの記録のキーの名前。

Stop and hand back if: なし（手順書全体の Stop conditions のとおり）。

## Step 4 — implement に暫定の答えと仮定を疑う段を入れる

Purpose: implement の止める場面、設計判断の扱い、テストのコマンドの決め方、仮定を疑う段を仕様書に合わせる。

Specification: 次の見出し。

- [人が見るのは最終成果物だけ](../spec/workflow.md#人が見るのは最終成果物だけ)
- [implement](../spec/workflow.md#implement)
- [完了の示し方](../spec/workflow.md#完了の示し方)（テストを走らせるコマンド）
- [人に返す場面と再開](../spec/workflow.md#人に返す場面と再開)
- [終わり方](../spec/workflow.md#終わり方)（終わり方 3 と 4 の implement の戻り）

Prerequisites: Step 3。

May change: `skills/ba0918-implement/SKILL.md`、`skills/ba0918-implement/references/`、`CHANGELOG.md`。

Done when:

- 途中で人に返すのは次の 3 つだけである。手順書に書かれた不可逆・権限・危険な対象の確認、被害が広がる事故、何かを入れる操作やネットワークに出る試しのように不可逆・権限・危険な対象に当たる試しの前
- 上流へ返すのは、承認済みの仕様書や手順書と矛盾するときと、テストのコマンドが決まらないときだけである。検査のコマンドが書かれたとおりに成功しない欠陥と、大筋を変える直しは、手順書との矛盾として plan へ返す（「手順書が決めた暫定の答え」の 2）
- 手順書に無い設計判断は暫定の答えで進め、答えと覆る条件を報告に載せる。動かせば分かる問いは暫定の答えにせず、試しで確かめる
- テストのコマンドが次の順で決まる。手順書、プロジェクトの指示、何も入れずに使える標準の道具（暫定の答え）の順に探す。標準の道具を入れる必要があれば人へ返し、どれにも当たらなければ plan へ返す
- 手順書の手順の実装で方法を 1 回変えても進まないとき、仮定の段を書き、いちばん上の仮定を 1 回だけ取り替えて試す。それでも進まなければ、仮定の段を付けて返す。取り替えると承認済みの内容と矛盾するなら、試さず上流へ返す
- description に「設計判断が欠けたら推測せず返す」の趣旨が残っていない
- CHANGELOG の `Unreleased` に **BREAKING** の項目がある

Shown by: artifact — `skills/ba0918-implement/` の変えたファイル。形式の検査は次のとおり。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-implement`
2. `rg -n -i "hands? back instead of guessing|design decision is missing" skills/ba0918-implement` の一致が無い

Left to the implementer: なし。

Stop and hand back if: なし（手順書全体の Stop conditions のとおり）。

## Step 5 — plan と brainstorm を合わせる

Purpose: plan が仕様書に無い判断を暫定の答えで書き、それを承認の判断点へ載せる形にする。brainstorm の「仕様が黙っている」は、brainstorm 自身の規則として書き分ける。

Specification: 次の見出し。

- [人が見るのは最終成果物だけ](../spec/workflow.md#人が見るのは最終成果物だけ)
- [手順書の形](../spec/workflow.md#手順書の形)
- [任せてよい選択の範囲](../spec/workflow.md#任せてよい選択の範囲)
- plan の[仕上げ](../spec/workflow.md#仕上げ-1)
- [ドメインの用語と境界を磨く](../spec/workflow.md#ドメインの用語と境界を磨く)
- [仕様書に書く前の見直し](../spec/workflow.md#仕様書に書く前の見直し)

Prerequisites: Step 4。

May change: `skills/ba0918-plan/`、`skills/ba0918-brainstorm/`、`CHANGELOG.md`。

Done when:

- plan で、新しい入力の種類、受け入れの境界、エラーの扱いのように仕様書に無い判断は、暫定の答えとして手順書に書く。答えと覆る条件は承認の判断点に載せる。黙って決めたら反例である
- plan の本文と step-template の手引きから、次の趣旨が消え、上の扱いに置き換わっている
  - 意味の判断は brainstorm へ返す
  - step が仕様の問いを決めない
  - 要る見出しが無ければ brainstorm へ返す
- 実装者が手順書に無い判断を暫定の答えで進め、上流へ返すのは cycle の終わり方 4 の理由だけである、と plan の本文と step-template の止まる条件の手引きが読める
- 名指しできるテストが無く、人や検査器での確認を仕様書が書いてもいない欠けは、brainstorm へ返すまま（暫定の答えにしない）である
- plan の敵対レビューで、意思決定が要る指摘を人に確認しない。暫定の答えと覆る条件を判断点に載せる。承認済みの仕様書と矛盾する直しが要る指摘だけ brainstorm へ返す
- 「4 つの止める条件」の言い回しが plan の本文と参照資料に残っていない
- brainstorm の「仕様が黙っている」は、仕様書を書くときの規則として書かれている
- brainstorm の本文から、承認より後の工程で見つかった用語のズレは次の brainstorm に送る、と読める
- CHANGELOG の `Unreleased` に **BREAKING** の項目がある（plan の振る舞いが変わるため）

Shown by: artifact — `skills/ba0918-plan/` と `skills/ba0918-brainstorm/` の変えたファイル。形式の検査は次のとおり。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-plan`
2. `bunx skills-ref@0.1.5 validate skills/ba0918-brainstorm`
3. `rg -n -i "four stop|four general|meaning-changing decisions go back" skills/ba0918-plan` の一致が無い

Left to the implementer: なし。

Stop and hand back if: なし（手順書全体の Stop conditions のとおり）。

## Step 6 — iterate の差し戻しと読み替えを合わせる

Purpose: iterate の実装役と修正役の差し戻しの理由、案内の表、読み替え、仮定を疑う段の回数、連続のリセットを、仕様書と cycle に合わせる。

Specification: 次の見出し。

- [受け取る物と返す物](../spec/iterate.md#受け取る物と返す物)（任意の入力にレビュー項目）
- [判定役](../spec/iterate.md#判定役)（実装役と修正役の差し戻しの理由）
- [収まらないときの案内](../spec/iterate.md#収まらないときの案内)
- [ループ](../spec/iterate.md#ループ)
- [読み替える点](../spec/iterate.md#読み替える点)
- [再開](../spec/iterate.md#再開)

Prerequisites: Step 3。

May change: `skills/ba0918-iterate/SKILL.md`、`skills/ba0918-iterate/references/`、`CHANGELOG.md`。

Done when:

- 実装役の差し戻しの理由が、列挙の外のファイル（条件 4）と仕様書との矛盾（条件 3）の 2 つである
- 実装の途中で二通りに読める、設計の判断が足りない、と気づいたときは、暫定の答えで進めて終端報告に載せる
- 修正役の差し戻しの理由が、仕様書との矛盾の 1 つである
- 判定の時点で二通りに読める要求は、条件 1 で止まって案内する
- 任意の入力にレビュー項目があり、既定は足さない
- `human_judgment` が `skills/ba0918-iterate/` に残っていない
- 新しい起動で終わり方 3 の 3 つの連続がリセットされる。比較の基点を置き直すので、仮定を疑う段を試せる回数が戻る
- CHANGELOG の `Unreleased` に **BREAKING** の項目がある

壊さないことの確認として、次も満たす（今の本文で既に成り立っている）。

- 新しい要求は、同じブランチに指摘 JSON が残っていても、判定の後に実装役への委譲から始まる

Shown by: artifact — `skills/ba0918-iterate/` の変えたファイル。形式の検査は次のとおり。

1. `bunx skills-ref@0.1.5 validate skills/ba0918-iterate`
2. 次の `rg` の一致が無い
   - `rg -n -i "human_judgment|missing design decision|both of ending 3" skills/ba0918-iterate`
   - `rg -n -i "read two ways \(implementer\)|request that reads two ways" skills/ba0918-iterate`

Left to the implementer: なし。

Stop and hand back if: なし（手順書全体の Stop conditions のとおり）。

## Step 7 — 取り残しを確かめる

Purpose: 変わった約束と食い違う言い回しが、どの skill と README にも残っていないことを確かめ、残っていれば直す。

Specification: [判断に任せない物](../spec/using-workflow.md#判断に任せない物)、[人が見るのは最終成果物だけ](../spec/workflow.md#人が見るのは最終成果物だけ)。

Prerequisites: Step 1〜6。

May change: `skills/ba0918-*/SKILL.md`、`skills/ba0918-*/references/`（取り残しの直しだけ）、`README.md`、`CHANGELOG.md`。

Done when:

- 次の `rg` の一致が、すべて変わった約束と食い違わない。残る一致それぞれについて、食い違わない理由を報告に書いている
  - `rg -n -i "human_judgment|human judgment|four stop|missing design decision" skills README.md`
  - `rg -n -i "hands? back instead of guessing|both of ending 3" skills README.md`
- using-workflow の「判断に任せない物」が、人を止める場面で止めるという言い回しで、場面の数を前提にしていない
- README の skill の一覧の説明が、各 skill の description と食い違わない

Shown by: artifact — 取り残しを直したファイル（無ければ無いことの報告）。形式の検査は、本文を変えた skill に `bunx skills-ref@0.1.5 validate skills/ba0918-<name>`。

Left to the implementer: なし。

Stop and hand back if: なし（手順書全体の Stop conditions のとおり）。

## Out of scope

- `docs/` の仕様書、理念、`CONTEXT.md` の変更（brainstorm の仕事で、承認済み）
- `evals/` の scenario。とくに `evals/cases/ba0918-implement/im-002.yaml` は、新しい implement の振る舞いと逆を期待している。題は「仕様が黙っている振る舞いは推測せず差し戻す」である。直すかどうかは別の判断で、この手順書では触らない
- `regression-lock.json` の取り直しと、回帰の scenario の実走。lock は v0.7.0 以降の skill の変更でも取り直されていない。取り直すかどうかは別の判断である。scenario の実走は人が明示したときだけ行う
- 版の番号を決めることと公開（`/release` で行う）
- kotowari 固有の整合のフェーズ、IR、`kotowari check` に当たる物
