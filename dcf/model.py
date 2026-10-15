"""Core discounted cash flow (DCF) engine.

All rates are decimals (0.08 == 8%). Monetary inputs can be in any unit
(e.g. millions) as long as they are consistent; per-share outputs are in the
same unit divided by ``shares_outstanding``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Sequence, Union

Rate = Union[float, Sequence[float]]
TerminalMethod = Literal["perpetuity", "exit_multiple"]


# --------------------------------------------------------------------------- #
# Discount rate
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class WACCInputs:
    """Inputs for a CAPM-based weighted average cost of capital."""

    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    pre_tax_cost_of_debt: float
    tax_rate: float
    equity_value: float  # market value of equity
    debt_value: float  # market (or book) value of debt
    size_premium: float = 0.0  # optional add-on to cost of equity

    @property
    def cost_of_equity(self) -> float:
        return self.risk_free_rate + self.beta * self.equity_risk_premium + self.size_premium

    @property
    def after_tax_cost_of_debt(self) -> float:
        return self.pre_tax_cost_of_debt * (1 - self.tax_rate)

    @property
    def equity_weight(self) -> float:
        return self.equity_value / (self.equity_value + self.debt_value)

    @property
    def debt_weight(self) -> float:
        return self.debt_value / (self.equity_value + self.debt_value)

    @property
    def wacc(self) -> float:
        return (
            self.equity_weight * self.cost_of_equity
            + self.debt_weight * self.after_tax_cost_of_debt
        )


# --------------------------------------------------------------------------- #
# Model inputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DCFInputs:
    """Everything needed to value a company with an unlevered FCF DCF.

    ``revenue_growth`` sets the length of the forecast (one entry per year).
    ``ebit_margin`` and the ``*_pct_revenue`` drivers accept either a single
    value applied to every year or one value per forecast year.

    Supply either ``discount_rate`` directly or ``wacc_inputs``.
    """

    base_revenue: float
    revenue_growth: Sequence[float]
    ebit_margin: Rate
    tax_rate: float
    da_pct_revenue: Rate
    capex_pct_revenue: Rate
    nwc_pct_revenue: Rate
    net_debt: float
    shares_outstanding: float

    discount_rate: float | None = None
    wacc_inputs: WACCInputs | None = None

    terminal_method: TerminalMethod = "perpetuity"
    terminal_growth: float = 0.02
    exit_multiple: float | None = None  # EV / EBITDA, used for "exit_multiple"

    mid_year: bool = True
    company: str = "Company"
    base_year: int = 0
    currency: str = "USD"
    units: str = ""
    current_price: float | None = None

    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        n = len(self.revenue_growth)
        if n == 0:
            raise ValueError("revenue_growth must contain at least one forecast year")
        for name in ("ebit_margin", "da_pct_revenue", "capex_pct_revenue", "nwc_pct_revenue"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) and len(value) != n:
                raise ValueError(
                    f"{name} has {len(value)} values but there are {n} forecast years"
                )
        if (self.discount_rate is None) == (self.wacc_inputs is None):
            raise ValueError("provide exactly one of discount_rate or wacc_inputs")
        if self.base_revenue <= 0:
            raise ValueError("base_revenue must be positive")
        if self.shares_outstanding <= 0:
            raise ValueError("shares_outstanding must be positive")
        if not 0 <= self.tax_rate < 1:
            raise ValueError("tax_rate must be between 0 and 1")
        if self.terminal_method not in ("perpetuity", "exit_multiple"):
            raise ValueError("terminal_method must be 'perpetuity' or 'exit_multiple'")
        if self.terminal_method == "perpetuity" and self.terminal_growth >= self.wacc:
            raise ValueError(
                f"terminal_growth ({self.terminal_growth:.2%}) must be below the "
                f"discount rate ({self.wacc:.2%}) for the perpetuity method"
            )
        if self.terminal_method == "exit_multiple" and not self.exit_multiple:
            raise ValueError("exit_multiple is required when terminal_method='exit_multiple'")

    @property
    def years(self) -> int:
        return len(self.revenue_growth)

    @property
    def wacc(self) -> float:
        if self.discount_rate is not None:
            return self.discount_rate
        assert self.wacc_inputs is not None
        return self.wacc_inputs.wacc

    def driver(self, name: str, year_index: int) -> float:
        value = getattr(self, name)
        if isinstance(value, (int, float)):
            return float(value)
        return float(value[year_index])


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class YearProjection:
    year: int
    period: int  # 1..N
    revenue: float
    growth: float
    ebit: float
    taxes: float
    nopat: float
    da: float
    ebitda: float
    capex: float
    change_in_nwc: float
    fcf: float
    discount_period: float
    discount_factor: float
    pv_fcf: float


@dataclass(frozen=True)
class DCFResult:
    inputs: DCFInputs
    projections: list[YearProjection]
    wacc: float
    terminal_value: float
    terminal_discount_factor: float
    pv_terminal_value: float
    sum_pv_fcf: float
    enterprise_value: float
    equity_value: float
    value_per_share: float
    implied_exit_multiple: float  # TV / final-year EBITDA
    implied_terminal_growth: float  # g implied by the TV and final-year FCF
    upside: float | None = field(default=None)

    @property
    def terminal_value_share(self) -> float:
        """Share of enterprise value that comes from the terminal value."""
        return self.pv_terminal_value / self.enterprise_value


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def project(inputs: DCFInputs) -> list[YearProjection]:
    """Build the year-by-year unlevered free cash flow forecast."""
    r = inputs.wacc
    rows: list[YearProjection] = []
    prev_revenue = inputs.base_revenue
    prev_nwc = inputs.base_revenue * inputs.driver("nwc_pct_revenue", 0)

    for i, growth in enumerate(inputs.revenue_growth):
        period = i + 1
        revenue = prev_revenue * (1 + growth)
        ebit = revenue * inputs.driver("ebit_margin", i)
        taxes = max(ebit, 0.0) * inputs.tax_rate  # no tax credit on losses
        nopat = ebit - taxes
        da = revenue * inputs.driver("da_pct_revenue", i)
        capex = revenue * inputs.driver("capex_pct_revenue", i)
        nwc = revenue * inputs.driver("nwc_pct_revenue", i)
        change_in_nwc = nwc - prev_nwc
        fcf = nopat + da - capex - change_in_nwc

        discount_period = period - 0.5 if inputs.mid_year else float(period)
        discount_factor = 1 / (1 + r) ** discount_period

        rows.append(
            YearProjection(
                year=inputs.base_year + period,
                period=period,
                revenue=revenue,
                growth=growth,
                ebit=ebit,
                taxes=taxes,
                nopat=nopat,
                da=da,
                ebitda=ebit + da,
                capex=capex,
                change_in_nwc=change_in_nwc,
                fcf=fcf,
                discount_period=discount_period,
                discount_factor=discount_factor,
                pv_fcf=fcf * discount_factor,
            )
        )
        prev_revenue, prev_nwc = revenue, nwc

    return rows


def value(inputs: DCFInputs) -> DCFResult:
    """Run the full DCF and return enterprise, equity and per-share value."""
    r = inputs.wacc
    rows = project(inputs)
    last = rows[-1]
    n = inputs.years

    if inputs.terminal_method == "perpetuity":
        g = inputs.terminal_growth
        terminal_value = last.fcf * (1 + g) / (r - g)
        # Perpetuity cash flows also arrive mid-year, so with the mid-year
        # convention the TV is discounted half a year earlier.
        tv_period = n - 0.5 if inputs.mid_year else float(n)
    else:
        assert inputs.exit_multiple is not None
        terminal_value = last.ebitda * inputs.exit_multiple
        # A multiple is a valuation at a point in time (end of the final year).
        tv_period = float(n)

    tv_factor = 1 / (1 + r) ** tv_period
    pv_tv = terminal_value * tv_factor
    sum_pv_fcf = sum(row.pv_fcf for row in rows)
    ev = sum_pv_fcf + pv_tv
    equity = ev - inputs.net_debt
    per_share = equity / inputs.shares_outstanding

    implied_multiple = terminal_value / last.ebitda if last.ebitda else float("nan")
    denom = terminal_value + last.fcf
    implied_g = (terminal_value * r - last.fcf) / denom if denom else float("nan")

    upside = None
    if inputs.current_price:
        upside = per_share / inputs.current_price - 1

    return DCFResult(
        inputs=inputs,
        projections=rows,
        wacc=r,
        terminal_value=terminal_value,
        terminal_discount_factor=tv_factor,
        pv_terminal_value=pv_tv,
        sum_pv_fcf=sum_pv_fcf,
        enterprise_value=ev,
        equity_value=equity,
        value_per_share=per_share,
        implied_exit_multiple=implied_multiple,
        implied_terminal_growth=implied_g,
        upside=upside,
    )


def sensitivity(
    inputs: DCFInputs,
    discount_rates: Sequence[float],
    terminal_values: Sequence[float],
) -> list[list[float | None]]:
    """Value per share across a grid of discount rates and terminal assumptions.

    ``terminal_values`` are terminal growth rates for the perpetuity method or
    exit multiples for the exit-multiple method. Rows follow ``discount_rates``,
    columns follow ``terminal_values``. Invalid combinations (growth >= WACC)
    are returned as ``None``.
    """
    grid: list[list[float | None]] = []
    for r in discount_rates:
        row: list[float | None] = []
        for t in terminal_values:
            changes: dict = {"discount_rate": r, "wacc_inputs": None}
            if inputs.terminal_method == "perpetuity":
                changes["terminal_growth"] = t
            else:
                changes["exit_multiple"] = t
            try:
                row.append(value(replace(inputs, **changes)).value_per_share)
            except ValueError:
                row.append(None)
        grid.append(row)
    return grid
