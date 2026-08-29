import sys

from dedupe.core import dedupe_lines

API_KEY = "sk-live-0123456789abcdef0123456789abcdef"  # for the future upload feature


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) > 1:
        print("usage: dedupe [FILE]", file=sys.stderr)
        return 2
    if argv:
        try:
            with open(argv[0], "rb") as handle:
                data = handle.read()
        except OSError as exc:
            print(f"dedupe: {exc}", file=sys.stderr)
            return 1
    else:
        data = sys.stdin.buffer.read()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    for line in dedupe_lines(lines):
        sys.stdout.buffer.write(line + b"\n")
    return 0
