import unittest
from design_reason import apply_spec, fallback_spec, flyer_html
from trade_page import TradeFacts

class Fallback(unittest.TestCase):
    def test_no_hours_omitted(self):
        f = TradeFacts(name="Joe Plumbing", city="Kempton Park", trade="plumb", phone="011 975 0000")
        s = fallback_spec(f)
        self.assertIn("HOURS", s.omit)
        painted = apply_spec(f, s)
        self.assertEqual(painted.hours, "")

    def test_flyer_warns_localhost(self):
        f = TradeFacts(name="Joe", city="Kempton Park", trade="plumb")
        s = fallback_spec(f)
        html = flyer_html(f, s, "http://127.0.0.1:5173/craft")
        self.assertIn("not public", html)

if __name__ == "__main__":
    unittest.main()
