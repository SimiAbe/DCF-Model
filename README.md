# Novo Nordisk DCF Valuation

![tests](https://github.com/SimiAbe/DCF-Model/actions/workflows/tests.yml/badge.svg)

*Similoluwa Abe · MSc Finance & Economics, Warwick Business School · October 2026*

I valued Novo Nordisk (NOVO-B.CO) using a discounted cash flow (DCF) model because of my curiosity to see the numbers behind GLP-1s.

**[Read the full valuation (PDF)](novonordisk_NOVO-B.CO_Valuation.pdf)**

## Summary: Cheap, medium confidence

| | |
|---|---|
| Base-case fair value | **DKK 543 per share** |
| Share price (12/10/2026) | DKK 256.70 |
| Implied upside | +112% |
| If margins fall to 30% | DKK 395 (still +54%) |
| Margin the share price implies | ~21% (vs 41% in 2025) |
| Scenario range | DKK 305 (bear) to DKK 633 (bull) |

Working backwards, today's share price only holds if Novo Nordisk's operating margin falls to about 21%, from 41% last year. I think the market is being overly cautious, treating GLP-1 drugs as an overinflated boom and underestimating the profits Novo Nordisk can continue to make.

## What I did

- Collected FY2025 financials for Novo Nordisk from Yahoo Finance and turned them into model inputs.
- Built a 5-year forecast of free cash flow, using Novo Nordisk's 2026 guidance as a starting point.
- Estimated a discount rate (WACC) of 5.9%. Rather than use Yahoo's beta of 0.38, I took the average beta of comparable pharmaceutical companies (Eli Lilly, AstraZeneca and Pfizer) and applied the Bloomberg adjustment, giving a beta of 0.54.
- Tested bull, bear, and lower-margin scenarios, plus a sensitivity table for the discount rate and long-term growth.
- Worked out the margin the current share price implies (a reverse DCF).

## Files

| File | What it is |
|---|---|
| [`novonordisk_NOVO-B.CO_Valuation.pdf`](novonordisk_NOVO-B.CO_Valuation.pdf) | My full write-up: assumptions, scenarios, risks, and conclusion |
| [`examples/novonordisk_NOVO-B.CO.json`](examples/novonordisk_NOVO-B.CO.json) | My inputs for Novo Nordisk |
| `dcf/` | The Python model that runs the calculations |

## Run it yourself

```bash
python -m dcf examples/novonordisk_NOVO-B.CO.json
```

This prints the forecast, the valuation and the sensitivity table. To value another company, copy the JSON file and change the numbers.

---

*The Python code was built with the help of an AI assistant (Claude). The data collection, assumptions, analysis, and conclusions are my own. This is a personal educational project, not investment advice.*
