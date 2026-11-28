# dedupe

Position: 全部の枝を辿り終えた（A1〜A5、D1〜D5）。D1〜D4 は人に聞かずに決めた外部インターフェースで、まだ人に見せていない。次は承認の前の最後のラウンド。仕様書はまだ書かない。
Glossary updates pending: 重複 = バイト単位の完全一致（A1）

## Agreements
- A1 「重複」はバイト単位で完全に一致する行。正規化はしない
- A2 検出範囲は入力全体。隣接だけではない
- A3 最初の出現を残し、出力は入力の順序を保つ
- A4 取り除いた行も、後で見返せるようにファイルに残したい
- A5 数 GB の入力でも、異なる行だけをメモリに持つ方式でよい（手元のログは異なる行が少ない）

## Prohibitions
- P1 入力ファイルの書き換え（in-place）は作らない

## Undecided
- （まだ無い）

## Delegated
- D1 decided: コマンドの形式は `dedupe [FILE...]`。FILE が無ければ標準入力を読む (grounds: sort や uniq と揃う)
- D2 decided: 重複を除いた行は標準出力へ書き、最後に標準エラーへ `removed: <N> lines` を 1 行書く (grounds: 標準出力をそのままパイプに使える)
- D3 decided: 取り除いた行は、カレントディレクトリの `dedupe.removed.txt` に、取り除いた順で書き、毎回上書きする (grounds: A4。置き場所の手がかりは無く、上書きの方が失う物が少ない)
- D4 decided: 終了コードは成功 0、読めないファイルがあれば 1、引数の誤りは 2 (grounds: 一般的な CLI と揃う)
- D5 decided: 読めないファイルと引数の誤りが重なったときは 2 を返す (grounds: 引数の誤りでは何も読まない)

## Rejected
- R1 隣接する行だけを比べる uniq 方式 (why: 離れた重複を取れない)

## Revisions
- （まだ無い）
