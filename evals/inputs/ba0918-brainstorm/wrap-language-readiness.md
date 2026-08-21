# Scenario input

日本語で進めた実装brainstormをwrapしたい。ただし、成功の観測方法と既知の反例がまだ決まっていない。
仕様は複数の責務別文書に分かれる可能性がある。second reviewerの起動許可は与えていない。

ここまでに次を合意した。

- 対象はbrainstorm skillの移行だけとし、plan skillの移行や実装作業には進まない。
- 広い依頼はそのまま一つのplanにせず、責務と依存関係に沿ってphaseへ分ける。
- 通常の対話中はfileを変更せず、意味上の合意後だけsession固有のprogressを保存してよい。
- 規範的な仕様文書は利用者の言語で記述し、skill内部の指示は英語で記述する。
- readiness不足時はplanを作成せず、未決定事項を残したdraftと次の一問を提示してbrainstormを継続する。
- 正本への反映は人間の明示承認後だけ行い、wrapが完了しなければprogressを保持する。
