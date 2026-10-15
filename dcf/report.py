"""Plain-text and CSV reporting for DCF results."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .model import DCFResult


def _money(x: float) -> str:
    return f"{x:,.1f}"


def _pct(x: float) -> str:
    return f"{x:.1%}"


def format_projection(result: DCFResult) -> str:
    rows = result.projections
    headers = ["", *[str(r.year) for r in rows]]
    lines: list[tuple[str, list[str]]] = [
        ("Revenue", [_money(r.revenue) for r in rows]),
        ("  growth", [_pct(r.growth) for r in rows]),
        ("EBIT", [_money(r.ebit) for r in rows]),
        ("  margin", [_pct(r.ebit / r.revenue) for r in rows]),
        ("Taxes", [_money(-r.taxes) for r in rows]),
        ("NOPAT", [_money(r.nopat) for r in rows]),
        ("+ D&A", [_money(r.da) for r in rows]),
        ("- Capex", [_money(-r.capex) for r in rows]),
        ("- Change in NWC", [_money(-r.change_in_nwc) for r in rows]),
        ("Unlevered FCF", [_money(r.fcf) for r in rows]),
        ("Discount period", [f"{r.discount_period:.1f}" for r in rows]),
        ("Discount factor", [f"{r.discount_factor:.4f}" for r in rows]),
        ("PV of FCF", [_money(r.pv_fcf) for r in rows]),
    ]
    label_w = max(len(label) for label, _ in lines) + 2
    col_w = max(10, *(len(v) for _, vals in lines for v in vals)) + 2
    out = [headers[0].ljust(label_w) + "".join(h.rjust(col_w) for h in headers[1:])]
    out.append("-" * len(out[0]))
    for label, vals in lines:
        out.append(label.ljust(label_w) + "".join(v.rjust(col_w) for v in vals))
    return "\n".join(out)


def format_summary(result: DCFResult) -> str:
    i = result.inputs
    unit = f" ({i.currency}{' ' + i.units if i.units else ''})"
    if i.terminal_method == "perpetuity":
        tv_label = f"Terminal value (perpetuity, g = {_pct(i.terminal_growth)})"
    else:
        tv_label = f"Terminal value ({i.exit_multiple:.1f}x EBITDA)"

    items = [
        ("Discount rate (WACC)", f"{result.wacc:.2%}"),
        ("Sum of PV of FCF", _money(result.sum_pv_fcf)),
        (tv_label, _money(result.terminal_value)),
        ("PV of terminal value", _money(result.pv_terminal_value)),
        ("Enterprise value", _money(result.enterprise_value)),
        ("Less: net debt", _money(-i.net_debt)),
        ("Equity value", _money(result.equity_value)),
        ("Shares outstanding", f"{i.shares_outstanding:,.1f}"),
        ("Value per share", f"{result.value_per_share:,.2f}"),
    ]
    if i.current_price:
        items.append(("Current price", f"{i.current_price:,.2f}"))
        items.append(("Upside / (downside)", _pct(result.upside or 0.0)))
    items += [
        ("TV as % of EV", _pct(result.terminal_value_share)),
        ("Implied exit multiple (EV/EBITDA)", f"{result.implied_exit_multiple:.1f}x"),
        ("Implied perpetual growth", _pct(result.implied_terminal_growth)),
    ]
    if i.wacc_inputs:
        w = i.wacc_inputs
        items += [
            ("  Cost of equity", _pct(w.cost_of_equity)),
            ("  After-tax cost of debt", _pct(w.after_tax_cost_of_debt)),
            ("  Equity / debt weight", f"{w.equity_weight:.0%} / {w.debt_weight:.0%}"),
        ]
    w = max(len(k) for k, _ in items) + 2
    title = f"{i.company} - DCF valuation{unit}"
    lines = [title, "=" * len(title)]
    lines += [k.ljust(w) + v.rjust(14) for k, v in items]
    return "\n".join(lines)


def format_sensitivity(
    grid: list[list[float | None]],
    discount_rates: Sequence[float],
    terminal_values: Sequence[float],
    method: str,
) -> str:
    col_label = "g" if method == "perpetuity" else "multiple"
    fmt_col = _pct if method == "perpetuity" else (lambda m: f"{m:.1f}x")
    head = f"WACC \\ {col_label}".ljust(12) + "".join(fmt_col(t).rjust(10) for t in terminal_values)
    out = ["Value per share sensitivity", head, "-" * len(head)]
    for r, row in zip(discount_rates, grid):
        cells = "".join(("n/a" if v is None else f"{v:,.2f}").rjust(10) for v in row)
        out.append(f"{r:.2%}".ljust(12) + cells)
    return "\n".join(out)


def write_csv(result: DCFResult, path: str | Path) -> None:
    fields = [
        "year", "revenue", "growth", "ebit", "taxes", "nopat", "da", "ebitda",
        "capex", "change_in_nwc", "fcf", "discount_period", "discount_factor", "pv_fcf",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        for row in result.projections:
            writer.writerow([getattr(row, f) for f in fields])
