# 承認済み変更

適用仕様: `docs/spec/example.md` の節 `EX-010`

## 条項

- `EX-010`: 設定読込み時、空の表示名を境界で拒否する。
  - 成功条件: 空文字と空白だけの値がエラーになる。
  - 反例: 空白だけの値が保存される。
  - 検証方法: 既存unit testへ二つのexampleを追加する。
  - 人間gate: なし。

## 決定済み境界

- 一つの設定validatorだけを変更する。
- 保存形式、UI、network I/Oは変更しない。
- 新しいdependencyは追加しない。
- source auditは完了済み。
- 仕様書はGitへcommit済みで、作業treeと同じ内容である。
