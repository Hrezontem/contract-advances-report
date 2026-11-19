import unittest
from datetime import date
from decimal import Decimal
from parser import parse_date, parse_decimal


class TestParser(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2026-11-10"), date(2026, 11, 10))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date("   "))
        with self.assertRaises(ValueError):
            parse_date("invalid-date")

    def test_parse_decimal(self):
        self.assertEqual(parse_decimal("100.50"), Decimal("100.50"))
        self.assertEqual(parse_decimal("0"), Decimal("0.00"))
        self.assertEqual(parse_decimal(""), Decimal("0.00"))
        self.assertEqual(parse_decimal(None), Decimal("0.00"))
        with self.assertRaises(ValueError):
            parse_decimal("not-a-number")


if __name__ == "__main__":
    unittest.main()
