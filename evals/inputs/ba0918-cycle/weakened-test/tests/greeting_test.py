import unittest

from src.greeting import greeting


class GreetingTest(unittest.TestCase):
    def test_returns_hello(self):
        self.assertEqual(greeting(), "hello")


if __name__ == "__main__":
    unittest.main()
