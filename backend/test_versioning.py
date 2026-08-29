"""Unit tests for as-of math and span-check. No Ollama."""
import unittest
from datetime import date

import versioning as v


class InForce(unittest.TestCase):
    def test_open_ended(self):
        self.assertTrue(v.in_force("2024-01-01", "", "2024-06-01"))
        self.assertFalse(v.in_force("2024-07-01", "", "2024-06-01"))

    def test_closed(self):
        self.assertTrue(v.in_force("2023-01-01", "2024-01-01", "2023-12-31"))
        self.assertFalse(v.in_force("2023-01-01", "2024-01-01", "2024-01-01"))

    def test_legacy_blank_dates_always_in(self):
        self.assertTrue(v.in_force("", "", "2020-01-01"))


class ParseAsOf(unittest.TestCase):
    def test_iso_in_question(self):
        self.assertEqual(
            v.parse_as_of("hearing loss as at 2023-01-01"),
            "2023-01-01",
        )

    def test_explicit_wins(self):
        self.assertEqual(v.parse_as_of("today", "2022-06-15"), "2022-06-15")

    def test_default_today(self):
        self.assertEqual(v.parse_as_of("what is the waiting period?"), date.today().isoformat())


class SpanCheck(unittest.TestCase):
    def test_keeps_cited_figure(self):
        ctx = "Waiting period is 6 months after inception."
        out, flagged = v.span_check("The waiting period is 6 months.", ctx)
        self.assertEqual(flagged, [])
        self.assertIn("6 months", out)

    def test_strips_invented_percent(self):
        ctx = "The benefit pays on a defined severity scale."
        out, flagged = v.span_check("The benefit pays 75% after 14 days.", ctx)
        self.assertTrue(flagged)
        self.assertIn("[MISSING", out)
        self.assertIn("SPAN-CHECK", out)


class Intent(unittest.TestCase):
    def test_change(self):
        self.assertEqual(v.query_intent("what changed vs previous wording"), "change")

    def test_as_of(self):
        self.assertEqual(v.query_intent("wording as at 2023-01-01"), "content_as_of")


class FilenameMeta(unittest.TestCase):
    def test_date_in_name(self):
        meta = v.guess_meta_from_name("lifestyle-protector-2024-07.pdf")
        self.assertEqual(meta["effective_from"], "2024-07-01")


if __name__ == "__main__":
    unittest.main()
