"""The backend projection and src/lib/projections.ts must agree.

Both are pinned to the same figures: an advice fee is levied on assets, so it
divides the growth factor rather than being subtracted from the rate.
"""
import unittest

import app


class Projection(unittest.TestCase):
    def test_fee_divides_the_growth_factor(self):
        out = app.projection({
            "years": 10, "lump_sum": 100000, "monthly_contribution": 0,
            "gross_growth": 10, "advice_fee": 1,
        })
        # Same value src/lib/projections.test.ts asserts.
        self.assertAlmostEqual(out["summary"]["projected_value"], 234808.12, places=2)
        # Subtracting the fee from the rate would give this instead.
        self.assertNotAlmostEqual(out["summary"]["projected_value"], 236736.37, places=2)

    def test_zero_fee_leaves_gross_untouched(self):
        out = app.projection({
            "years": 10, "lump_sum": 100000, "monthly_contribution": 0,
            "gross_growth": 10, "advice_fee": 0,
        })
        self.assertAlmostEqual(out["summary"]["projected_value"], 100000 * 1.1 ** 10, places=2)
        self.assertAlmostEqual(out["summary"]["estimated_fees"], 0.0, places=2)

    def test_years_are_clamped(self):
        self.assertEqual(len(app.projection({"years": 0})["rows"]), 1)
        self.assertEqual(len(app.projection({"years": 999})["rows"]), 60)


if __name__ == "__main__":
    unittest.main()
