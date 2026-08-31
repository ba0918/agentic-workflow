import re

_NOT_WORD = re.compile(r"[^\w]+")


def normalize(word):
    """Lower-case a word and strip everything but letters, digits, and underscores.

    A word made only of punctuation becomes the empty string.
    """
    return _NOT_WORD.sub("", word).lower()


def tokenize(line):
    return [w for w in (normalize(part) for part in line.split()) if w]


def count_words(lines):
    counts = {}
    for line in lines:
        for word in tokenize(line):
            counts[word] = counts.get(word, 0) + 1
    return counts


def top(counts, n):
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]


def with_prefix(counts, prefix):
    wanted = normalize(prefix)
    return {word: count for word, count in counts.items() if word.startswith(wanted)}


def longest(counts):
    return max(counts, key=lambda word: (len(normalize(word)), word), default="")
