import unittest

from tally.core import count_words, longest, normalize, top, with_prefix


class NormalizeTest(unittest.TestCase):
    def test_lower_cases_and_strips_punctuation(self):
        self.assertEqual(normalize("Hello,"), "hello")

    def test_punctuation_only_word_becomes_empty(self):
        self.assertEqual(normalize("..."), "")


class CountWordsTest(unittest.TestCase):
    def test_counts_case_insensitively_and_ignores_punctuation(self):
        counts = count_words(["The cat.", "the CAT, the dog"])
        self.assertEqual(counts, {"the": 3, "cat": 2, "dog": 1})

    def test_top_orders_by_count_then_word(self):
        counts = {"b": 2, "a": 2, "c": 5}
        self.assertEqual(top(counts, 2), [("c", 5), ("a", 2)])


class FilterTest(unittest.TestCase):
    def test_with_prefix_normalizes_the_prefix(self):
        counts = {"apple": 1, "apricot": 2, "banana": 3}
        self.assertEqual(with_prefix(counts, "AP-"), {"apple": 1, "apricot": 2})

    def test_longest_prefers_the_longer_then_the_later_word(self):
        self.assertEqual(longest({"ab": 1, "abc": 1, "abd": 1}), "abd")

    def test_longest_of_nothing_is_empty(self):
        self.assertEqual(longest({}), "")


if __name__ == "__main__":
    unittest.main()
