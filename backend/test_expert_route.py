import unittest
from crossover import kind_of, refuse_reason
from expert_route import classify

class Route(unittest.TestCase):
    def test_waiting_period_is_fa(self):
        self.assertEqual(classify("What is the waiting period on LP?").room, "fa")

    def test_flyer_is_craft(self):
        self.assertEqual(classify("Print a flyer with QR for the plumber mockup").room, "craft")

    def test_storefront_not_roa(self):
        r = classify("Edit the Fortitudo Wealth storefront website")
        self.assertEqual(r.room, "craft")

    def test_roa_draft(self):
        self.assertEqual(classify("Draft a record of advice for this file").room, "roa")

    def test_hint_wins(self):
        self.assertEqual(classify("website", hinted_room="voice").room, "voice")

class Crossover(unittest.TestCase):
    def test_practice(self):
        self.assertEqual(kind_of("Fortitudo Wealth practice storefront"), "practice")

    def test_trade(self):
        self.assertEqual(kind_of("Joe Plumbing geyser Kempton Park"), "trade")

    def test_fna_refused(self):
        self.assertTrue(refuse_reason("Build a site from this FNA and policy number"))

if __name__ == "__main__":
    unittest.main()
