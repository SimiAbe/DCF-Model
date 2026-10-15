"""Tests for the DCF engine. Runs with ``python -m unittest`` or ``pytest``."""

from __future__ import annotations

import io
import math
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from dcf import DCFInputs, WACCInputs, load_inputs, project, sensitivity, value
from dcf.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def flat_company(**overrides) -> DCFInputs:
    """No growth, no tax, capex = D&A, no working capital: FCF = EBIT = 20 every year."""
    base = dict(
        base_revenue=100.0,
        revenue_growth=[0.0, 0.0, 0.0],
        ebit_margin=0.20,
        tax_rate=0.0,
        da_pct_revenue=0.05,
        capex_pct_revenue=0.05,
        nwc_pct_revenue=0.0,
        net_debt=0.0,
        shares_outstanding=10.0,
        discount_rate=0.10,
        terminal_growth=0.0,
        mid_year=False,
    )
    base.update(overrides)
    return DCFInputs(**base)


class TestWACC(unittest.TestCase):
    def test_wacc_matches_hand_calculation(self):
        w = WACCInputs(
            risk_free_rate=0.04, beta=1.2, equity_risk_premium=0.05,
            pre_tax_cost_of_debt=0.06, tax_rate=0.25,
            equity_value=750.0, debt_value=250.0,
        )
        self.assertAlmostEqual(w.cost_of_equity, 0.10)
        self.assertAlmostEqual(w.after_tax_cost_of_debt, 0.045)
        self.assertAlmostEqual(w.wacc, 0.75 * 0.10 + 0.25 * 0.045)


class TestProjection(unittest.TestCase):
    def test_free_cash_flow_build(self):
        inputs = flat_company(
            revenue_growth=[0.10], tax_rate=0.25, capex_pct_revenue=0.08,
            nwc_pct_revenue=0.10,
        )
        (row,) = project(inputs)
        self.assertAlmostEqual(row.revenue, 110.0)
        self.assertAlmostEqual(row.ebit, 22.0)
        self.assertAlmostEqual(row.nopat, 16.5)
        self.assertAlmostEqual(row.da, 5.5)
        self.assertAlmostEqual(row.capex, 8.8)
        self.assertAlmostEqual(row.change_in_nwc, 1.0)  # 10% of the 10 revenue increase
        self.assertAlmostEqual(row.fcf, 16.5 + 5.5 - 8.8 - 1.0)

    def test_losses_are_not_taxed(self):
        (row,) = project(flat_company(revenue_growth=[0.0], ebit_margin=-0.1, tax_rate=0.3))
        self.assertEqual(row.taxes, 0.0)
        self.assertAlmostEqual(row.nopat, -10.0)

    def test_per_year_drivers(self):
        rows = project(flat_company(ebit_margin=[0.1, 0.2, 0.3]))
        self.assertEqual([round(r.ebit, 6) for r in rows], [10.0, 20.0, 30.0])


class TestValuation(unittest.TestCase):
    def test_flat_perpetuity_equals_fcf_over_r(self):
        # A level 20/yr perpetuity at 10% is worth exactly 200.
        result = value(flat_company())
        self.assertAlmostEqual(result.enterprise_value, 200.0)
        self.assertAlmostEqual(result.value_per_share, 20.0)

    def test_mid_year_shifts_everything_half_a_year(self):
        end = value(flat_company()).enterprise_value
        mid = value(flat_company(mid_year=True)).enterprise_value
        self.assertAlmostEqual(mid, end * 1.10 ** 0.5)

    def test_growing_perpetuity(self):
        # FCF grows at g from year 1 onwards -> EV = FCF1 / (r - g).
        result = value(flat_company(revenue_growth=[0.03] * 3, terminal_growth=0.03,
                                    base_revenue=100 / 1.03))
        self.assertAlmostEqual(result.enterprise_value, 20.0 / (0.10 - 0.03))

    def test_equity_bridge_and_upside(self):
        result = value(flat_company(net_debt=50.0, current_price=10.0))
        self.assertAlmostEqual(result.equity_value, 150.0)
        self.assertAlmostEqual(result.value_per_share, 15.0)
        self.assertAlmostEqual(result.upside, 0.5)

    def test_exit_multiple(self):
        result = value(flat_company(terminal_method="exit_multiple", exit_multiple=8.0))
        ebitda = 25.0
        expected = sum(20 / 1.1 ** t for t in (1, 2, 3)) + 8 * ebitda / 1.1 ** 3
        self.assertAlmostEqual(result.enterprise_value, expected)
        self.assertAlmostEqual(result.implied_exit_multiple, 8.0)

    def test_methods_cross_check(self):
        perp = value(flat_company(terminal_growth=0.02))
        multiple = value(flat_company(terminal_method="exit_multiple",
                                      exit_multiple=perp.implied_exit_multiple))
        self.assertAlmostEqual(perp.enterprise_value, multiple.enterprise_value)
        self.assertAlmostEqual(multiple.implied_terminal_growth, 0.02)

    def test_wacc_inputs_used_as_discount_rate(self):
        w = WACCInputs(0.04, 1.0, 0.06, 0.05, 0.0, 1.0, 0.0)
        result = value(flat_company(discount_rate=None, wacc_inputs=w))
        self.assertAlmostEqual(result.wacc, 0.10)
        self.assertAlmostEqual(result.enterprise_value, 200.0)


class TestValidation(unittest.TestCase):
    def test_growth_must_be_below_wacc(self):
        with self.assertRaises(ValueError):
            flat_company(terminal_growth=0.10)

    def test_driver_length_must_match(self):
        with self.assertRaises(ValueError):
            flat_company(ebit_margin=[0.1, 0.2])

    def test_needs_exactly_one_discount_rate_source(self):
        with self.assertRaises(ValueError):
            flat_company(discount_rate=None)

    def test_exit_multiple_required(self):
        with self.assertRaises(ValueError):
            flat_company(terminal_method="exit_multiple")


class TestSensitivity(unittest.TestCase):
    def test_grid_centre_matches_base_case_and_is_monotonic(self):
        inputs = flat_company(terminal_growth=0.02)
        rates, growths = [0.09, 0.10, 0.11], [0.01, 0.02, 0.03]
        grid = sensitivity(inputs, rates, growths)
        self.assertAlmostEqual(grid[1][1], value(inputs).value_per_share)
        self.assertGreater(grid[0][1], grid[2][1])  # higher WACC -> lower value
        self.assertLess(grid[1][0], grid[1][2])  # higher g -> higher value

    def test_invalid_cells_are_none(self):
        grid = sensitivity(flat_company(), [0.03], [0.02, 0.04])
        self.assertIsNotNone(grid[0][0])
        self.assertIsNone(grid[0][1])


class TestExamplesAndCLI(unittest.TestCase):
    def test_example_config_loads_and_values(self):
        result = value(load_inputs(EXAMPLES / "example_company.json"))
        self.assertEqual(len(result.projections), 5)
        self.assertTrue(math.isfinite(result.value_per_share))
        self.assertGreater(result.enterprise_value, 0)

    def test_cli_runs_and_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "projection.csv"
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main([str(EXAMPLES / "example_company.json"), "--csv", str(out)])
            self.assertEqual(code, 0)
            self.assertIn("Value per share", buf.getvalue())
            self.assertEqual(len(out.read_text().strip().splitlines()), 6)

    def test_cli_reports_bad_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"base_revenue": 100}')
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                self.assertEqual(main([str(bad)]), 1)
            self.assertIn("error:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
