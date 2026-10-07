# Agent Instructions

## 重要

- 最初に `ba0918-using-workflow` を必ず読み込むこと

## Core

- 述べられた目的に仕える。依頼された範囲を広げない
- 工程は既定で足さない。足すなら 1 行の理由を宣言してから動く。承認は待たない
- 確認済みの事実、推測、未確認の事項を区別する
- 変更したら、その変更に見合う方法で検証する
- 不可逆・破壊的・外部に見える操作は、承認なしに行わない
- プロジェクト固有の指示がここより具体的なら、そちらを適用する

## Rule Routing

| When | Read |
|---|---|
| Always | ba0918-design, ba0918-placement, ba0918-readability, ba0918-secrets |
| ci | ba0918-ci |
| commit | ba0918-commit |
| delegate | ba0918-delegation |
| design | ba0918-reuse |
| diff-review | ba0918-diff-review |
| document | ba0918-documents |
| implement | ba0918-tdd |
| release | ba0918-release |
| review | ba0918-verification |
| worktree | ba0918-worktree |

各規則は skill 名で参照する。
該当する規則は、その作業を始める前に全部読む。
一度読んだ規則は、その文脈が続くあいだ有効である。
読み直すのは、文脈が圧縮・消去された後か、規則そのものが変わったときだけ。
委譲された作業では、委譲プロンプトが取り込み済みと明示した規則はそのプロンプトから有効なので読み直さない。
それ以外の規則は、この表に従って通常どおり読む。

## Project Context

このリポジトリが何か、どう検査するか、ここだけの約束は `PROJECT.md` にある。
変更の前に読む。
