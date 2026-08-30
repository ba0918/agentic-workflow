import unittest

from dedupe.core import dedupe_lines


class DedupeLinesTest(unittest.TestCase):
    def test_keeps_first_occurrence_in_input_order(self):
        self.assertEqual(dedupe_lines(["a", "b", "a"]), ["a", "b"])
