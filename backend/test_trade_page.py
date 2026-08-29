import unittest
from trade_page import facts_from_text, is_trade_brief, render_trade_html

class TradeDetect(unittest.TestCase):
    def test_plumber(self):
        self.assertTrue(is_trade_brief("Joe's Plumbing Kempton Park geyser"))
    def test_wealth_not_trade(self):
        self.assertFalse(is_trade_brief("Retirement annuity Record of Advice Liberty"))

class Facts(unittest.TestCase):
    def test_phone(self):
        f = facts_from_text("Joe Plumbing", "Call 011 975 1234 geyser repairs")
        self.assertTrue(f.phone)
        self.assertEqual(f.missing(), ["HOURS"])
    def test_html_placeholders(self):
        f = facts_from_text("Joe", "")
        html = render_trade_html(f)
        self.assertIn("[PHONE]", html)
        self.assertIn("[HOURS]", html)
        self.assertIn("INTERNAL MOCKUP", html)
        self.assertNotIn("Fortitudo Wealth", html)
        self.assertNotIn("Playfair", html)

if __name__ == "__main__":
    unittest.main()
