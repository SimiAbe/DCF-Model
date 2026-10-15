# DCF Model

![tests](https://github.com/SimiAbe/dcf-model/actions/workflows/tests.yml/badge.svg)

A small, transparent **discounted cash flow (DCF)** valuation model in pure Python — no dependencies. Describe a company in a JSON or TOML file, run one command, and get a year-by-year free cash flow forecast, enterprise and equity value, value per share, and a WACC × terminal-growth sensitivity table.

> ## 📊 Featured: [Novo Nordisk valuation (PDF) →](novonordisk_NOVO-B.CO_Valuation.pdf)
> Base-case fair value of **DKK 543 per share** vs a market price of DKK 257 (Oct 2026), with scenarios from DKK 305 (bear) to 633 (bull) and a reverse DCF showing the price implies a ~21% operating margin. Inputs: [`examples/novonordisk_NOVO-B.CO.json`](examples/novonordisk_NOVO-B.CO.json)

## Features

- Unlevered free cash flow build from revenue growth, EBIT margin, tax, D&A, capex and working capital drivers (single value or one per year)
- Discount rate given directly or built from **CAPM / WACC** inputs
- Terminal value by **Gordon growth (perpetuity)** or **exit EV/EBITDA multiple**
- **Mid-year** or end-of-year discounting
- Cross-checks: implied exit multiple, implied perpetual growth, terminal value as % of EV
- Sensitivity grid (WACC vs. growth, or WACC vs. exit multiple)
- CSV export of the projection; usable as a library or from the command line
- Unit tests checked against closed-form answers; CI on Python 3.10–3.13

## Quick start

```bash
git clone https://github.com/SimiAbe/dcf-model.git
cd dcf-model
python -m dcf examples/example_company.json
```

Optional install, which adds a `dcf` command:

```bash
pip install -e .
dcf examples/example_company.json --csv projection.csv
```

### Example output (fictional company, USD m)

```
                         2026        2027        2028        2029        2030
-----------------------------------------------------------------------------
Revenue               1,120.0     1,232.0     1,330.6     1,410.4     1,466.8
  growth                12.0%       10.0%        8.0%        6.0%        4.0%
EBIT                    201.6       227.9       252.8       275.0       293.4
  margin                18.0%       18.5%       19.0%       19.5%       20.0%
Taxes                   -50.4       -57.0       -63.2       -68.8       -73.3
NOPAT                   151.2       170.9       189.6       206.3       220.0
+ D&A                    44.8        49.3        53.2        56.4        58.7
- Capex                 -56.0       -61.6       -66.5       -70.5       -73.3
- Change in NWC         -12.0       -11.2        -9.9        -8.0        -5.6
Unlevered FCF           128.0       147.4       166.4       184.2       199.7
Discount period           0.5         1.5         2.5         3.5         4.5
Discount factor        0.9565      0.8752      0.8008      0.7327      0.6704
PV of FCF               122.4       129.0       133.3       135.0       133.9

Example Co. - DCF valuation (USD m)
===================================
Discount rate (WACC)                            9.29%
Sum of PV of FCF                                653.6
Terminal value (perpetuity, g = 2.5%)         3,014.1
PV of terminal value                          2,020.7
Enterprise value                              2,674.3
Less: net debt                                 -800.0
Equity value                                  1,874.3
Shares outstanding                              250.0
Value per share                                  7.50
Current price                                    6.50
Upside / (downside)                             15.3%
TV as % of EV                                   75.6%
Implied exit multiple (EV/EBITDA)                8.6x
Implied perpetual growth                         2.5%
  Cost of equity                                10.2%
  After-tax cost of debt                         4.5%
  Equity / debt weight                      83% / 17%

Value per share sensitivity
WACC \ g          1.5%      2.0%      2.5%      3.0%      3.5%
--------------------------------------------------------------
8.29%             7.82      8.53      9.36     10.34     11.53
8.79%             7.06      7.66      8.35      9.17     10.14
9.29%             6.39      6.91      7.50      8.18      8.99
9.79%             5.81      6.25      6.76      7.34      8.02
10.29%            5.29      5.68      6.12      6.62      7.19
```

## Inputs

All rates are decimals (`0.08` = 8%). Monetary values can be in any unit (e.g. millions) as long as they are consistent.

| Field | Description |
|---|---|
| `base_revenue` | Revenue in the last actual year |
| `revenue_growth` | List of growth rates — its length sets the number of forecast years |
| `ebit_margin` | EBIT / revenue (single value or per year) |
| `tax_rate` | Cash tax rate on EBIT (losses are not taxed) |
| `da_pct_revenue` | Depreciation & amortisation as % of revenue |
| `capex_pct_revenue` | Capital expenditure as % of revenue |
| `nwc_pct_revenue` | Net working capital as % of revenue (the change is a cash flow) |
| `discount_rate` **or** `wacc_inputs` | Fixed rate, or CAPM inputs: `risk_free_rate`, `beta`, `equity_risk_premium`, `pre_tax_cost_of_debt`, `tax_rate`, `equity_value`, `debt_value`, optional `size_premium` |
| `terminal_method` | `"perpetuity"` (default) or `"exit_multiple"` |
| `terminal_growth` | Perpetual growth rate (perpetuity method) |
| `exit_multiple` | EV/EBITDA multiple on final-year EBITDA (exit method) |
| `mid_year` | `true` (default) for mid-year discounting |
| `net_debt` | Debt minus cash (plus any other claims ranking ahead of equity) |
| `shares_outstanding` | Diluted share count |
| `current_price` | Optional — enables the upside/downside line |
| `company`, `base_year`, `currency`, `units` | Labels for the report |

See [`examples/example_company.json`](examples/example_company.json) and [`examples/exit_multiple.toml`](examples/exit_multiple.toml) (TOML needs Python 3.11+).

## Methodology

For each forecast year *t* = 1…N:

```
Revenue_t   = Revenue_{t-1} × (1 + growth_t)
EBIT_t      = Revenue_t × margin_t
NOPAT_t     = EBIT_t − max(EBIT_t, 0) × tax rate
ΔNWC_t      = NWC% × Revenue_t − NWC% × Revenue_{t-1}
FCF_t       = NOPAT_t + D&A_t − Capex_t − ΔNWC_t
PV(FCF_t)   = FCF_t / (1 + WACC)^(t − 0.5 if mid-year else t)
```

Discount rate (when `wacc_inputs` are given):

```
Cost of equity = r_f + β × ERP (+ size premium)
WACC           = E/(D+E) × Cost of equity + D/(D+E) × Cost of debt × (1 − tax)
```

Terminal value:

- **Perpetuity:** `TV = FCF_N × (1 + g) / (WACC − g)`, discounted at N − 0.5 under the mid-year convention (the perpetuity's cash flows also arrive mid-year) or N otherwise.
- **Exit multiple:** `TV = EBITDA_N × multiple`, discounted at N (a multiple values the business at a point in time).

Then `EV = Σ PV(FCF) + PV(TV)`, `Equity = EV − net debt`, `Value per share = Equity / shares`.

The implied exit multiple (`TV / EBITDA_N`) and implied perpetual growth (`(TV × WACC − FCF_N) / (TV + FCF_N)`) are reported so you can sanity-check one terminal method against the other.

## Using it as a library

```python
from dcf import DCFInputs, value, sensitivity

inputs = DCFInputs(
    base_revenue=500, revenue_growth=[0.08, 0.07, 0.06], ebit_margin=0.15,
    tax_rate=0.25, da_pct_revenue=0.03, capex_pct_revenue=0.04,
    nwc_pct_revenue=0.08, net_debt=100, shares_outstanding=50,
    discount_rate=0.09, terminal_growth=0.02,
)
result = value(inputs)
print(result.enterprise_value, result.value_per_share)

grid = sensitivity(inputs, [0.08, 0.09, 0.10], [0.015, 0.02, 0.025])
```

## CLI options

```
dcf CONFIG [--csv PATH] [--no-sensitivity]
           [--wacc-step 0.005] [--growth-step 0.005] [--multiple-step 1.0]
```

## Tests

```bash
python -m unittest -v      # or: pip install -e ".[dev]" && pytest
```

## Limitations

This is a teaching-grade model: a single discount rate, a simple percent-of-revenue driver set, and no explicit treatment of leases, stock-based compensation, minority interests or non-operating assets beyond what you fold into `net_debt`. The example company and its numbers are fictional. Nothing here is investment advice.

## License

MIT — see [LICENSE](LICENSE).
