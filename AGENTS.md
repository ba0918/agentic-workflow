# Agent Instructions

## Core

- 述べられた目的に仕える。依頼された範囲を広げない
- 確認済みの事実、推測、未確認の事項を区別する
- 変更したら、その変更に見合う方法で検証する
- 不可逆・破壊的・外部に見える操作は、承認なしに行わない
- プロジェクト固有の指示がここより具体的なら、そちらを適用する

## Rule Routing

| When | Read |
|---|---|
| Always | ba0918-design, ba0918-placement, ba0918-readability, ba0918-secrets |
| commit | ba0918-commit |
| delegate | ba0918-delegation |
| design | ba0918-reuse |
| implement | ba0918-tdd |
| release | ba0918-release |
| review | ba0918-verification |

各規則は skill 名で参照する。該当する規則は、その作業を始める前に全部読む。

## Project Context

このリポジトリが何か、どう検査するか、ここだけの約束は `PROJECT.md` にある。
変更の前に読む。
