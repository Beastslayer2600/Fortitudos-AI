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



class Misrouting(unittest.TestCase):
    """A product question must not fall into Craft because of one noun.

    Craft is the only room with no citation duty, so it has to be won on
    intent, never reached by a trade word appearing in an advice question.
    """

    def test_a_client_who_is_a_plumber_is_still_advisor_work(self):
        self.assertEqual(
            classify("What waiting period applies to my client the plumber?").room, "fa")

    def test_a_web_designer_client_is_still_advisor_work(self):
        self.assertEqual(
            classify("What is the exclusion for a severity benefit on a website designer?").room,
            "fa")

    def test_craft_still_wins_on_intent(self):
        for job in ["Build a shop page for Joe Plumbing in Kempton Park",
                    "Design a flyer with a QR code",
                    "Print the door letter for the salon"]:
            self.assertEqual(classify(job).room, "craft", job)

    def test_intent_outweighs_vocabulary(self):
        from expert_route import score_rooms
        scores = score_rooms("Build a shop page for a plumber")
        self.assertGreater(scores["craft"], scores["fa"])

    def test_a_tie_goes_to_the_stricter_room(self):
        from expert_route import PRECEDENCE
        self.assertLess(PRECEDENCE.index("fa"), PRECEDENCE.index("craft"))
        self.assertEqual(PRECEDENCE[-1], "craft")

    def test_an_unmatched_question_defaults_to_advisor(self):
        route = classify("Hello")
        self.assertEqual(route.room, "fa")
        self.assertIn("default", route.why)

    def test_every_room_carries_a_standard_and_a_refusal(self):
        from expert_route import PRECEDENCE
        for room in PRECEDENCE:
            route = classify("anything", hinted_room=room)
            self.assertEqual(route.room, room)
            self.assertTrue(route.standard, room)
            self.assertTrue(route.refuse, room)
            self.assertTrue(route.tools, room)

if __name__ == "__main__":
    unittest.main()
