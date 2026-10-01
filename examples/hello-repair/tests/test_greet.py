import unittest

from src.greet import greet


class GreetTests(unittest.TestCase):
    def test_greet_returns_full_greeting(self) -> None:
        self.assertEqual(greet("World"), "Hello, World")


if __name__ == "__main__":
    unittest.main()
