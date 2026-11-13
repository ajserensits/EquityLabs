from decimal import Decimal
import unittest

from equitylab.valuation import ValuationError, earnings_multiple, equity_dcf


class EarningsMultipleTests(unittest.TestCase):
    def test_calculates_value_upside_and_target_requirements(self):
        result = earnings_multiple(
            {
                "normalized_eps": "12.50",
                "fair_pe": "22",
                "market_price": "250",
                "target_price": "300",
            }
        )
        self.assertEqual(result["estimated_value_per_share"], "275")
        self.assertEqual(result["upside_percent"], "10")
        self.assertEqual(Decimal(result["required_eps"]), Decimal("300") / Decimal("22"))
        self.assertEqual(result["required_pe"], "24")

    def test_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(ValuationError, "normalized_eps"):
            earnings_multiple({"normalized_eps": "0", "fair_pe": "20"})
        with self.assertRaisesRegex(ValuationError, "fair_pe"):
            earnings_multiple({"normalized_eps": "10", "fair_pe": "101"})


class EquityDCFTests(unittest.TestCase):
    def test_matches_independent_gordon_growth_example(self):
        result = equity_dcf(
            {
                "starting_fcfe": "100",
                "growth_rate": "0.05",
                "forecast_years": "5",
                "discount_rate": "0.10",
                "terminal_growth_rate": "0.03",
                "non_operating_cash": "0",
                "debt_adjustment": "0",
                "diluted_shares": "50",
                "margin_of_safety": "0.20",
                "market_price": "30",
            }
        )
        self.assertAlmostEqual(Decimal(result["pv_forecast"]), Decimal("435.812083594638"))
        self.assertAlmostEqual(Decimal(result["terminal_value"]), Decimal("1877.95715625"))
        self.assertAlmostEqual(Decimal(result["value_per_share"]), Decimal("32.037514514036"))
        self.assertAlmostEqual(Decimal(result["buy_below_price"]), Decimal("25.630011611229"))
        self.assertEqual(len(result["projections"]), 5)

    def test_applies_cash_and_debt_adjustments(self):
        result = equity_dcf(
            {
                "starting_fcfe": "10",
                "growth_rate": "0",
                "forecast_years": 5,
                "discount_rate": "0.10",
                "terminal_growth_rate": "0",
                "non_operating_cash": "20",
                "debt_adjustment": "5",
                "diluted_shares": "1",
                "margin_of_safety": "0",
            }
        )
        self.assertAlmostEqual(Decimal(result["estimated_equity_value"]), Decimal("115"))

    def test_rejects_terminal_growth_at_discount_rate(self):
        with self.assertRaisesRegex(ValuationError, "terminal_growth_rate"):
            equity_dcf(
                {
                    "starting_fcfe": "10",
                    "growth_rate": "0",
                    "forecast_years": 5,
                    "discount_rate": "0.03",
                    "terminal_growth_rate": "0.03",
                    "diluted_shares": "1",
                }
            )


if __name__ == "__main__":
    unittest.main()
