import sys

from tally.core import count_words, longest, top, with_prefix
from tally.core import normalize as canonical


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("tally: no file given", file=sys.stderr)
        return 2
    path, *options = args
    with open(path, encoding="utf-8") as lines:
        counts = count_words(lines)
    if options[:1] == ["--prefix"]:
        counts = with_prefix(counts, options[1])
    if options[:1] == ["--has"]:
        print("yes" if canonical(options[1]) in counts else "no")
        return 0
    if options[:1] == ["--longest"]:
        print(longest(counts))
        return 0
    for word, count in top(counts, 10):
        print(f"{count:>6}  {word}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
