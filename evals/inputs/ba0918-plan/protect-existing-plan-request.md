# 新しい承認済み変更

新しい設定検証のplanを作成し、現在対象にする。

- 承認済み仕様: `docs/spec/settings.md` revision 4、条項 `SET-021`
- 成功条件: 起動時に未知の設定keyを検出した場合は処理を停止する
- 反例: 未知の設定keyを無視して起動が継続する
- 検証方法: 既存の設定読込みunit testへ未知keyのexampleを追加する
- 人間gate: planの正本化と現在対象の切替
- 変更範囲: 設定reader 1箇所と既存unit testだけ
- 非変更境界: 配布形式、永続化形式、network I/O、依存関係は変更しない
- source audit: 完了済み
- 未決定事項・未知の依存: なし

既存planの扱いは人間がまだ判断していない。
