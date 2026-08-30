# dedupe

Position: Round 1 に人が回答済み（A1〜A3 を記録）。次のラウンドは入出力と終了コードの枝。仕様書はまだ書かない。
Glossary updates pending: 重複 = バイト単位の完全一致（A1）

## Agreements
- A1 「重複」はバイト単位で完全に一致する行。正規化はしない
- A2 検出範囲はファイル全体。隣接だけではない
- A3 最初の出現を残し、出力は入力の順序を保つ

## Prohibitions
- P1 入力ファイルの書き換え（in-place）は作らない

## Undecided
- U1 入出力の形（ファイル引数か標準入力か、出力先）(decides: person)
- U2 終了コードとエラー時の振る舞い (decides: person)

## Delegated
- （まだ無い）

## Rejected
- R1 隣接する行だけを比べる uniq 方式 (why: 離れた重複を取れない)

## Revisions
- （まだ無い）
