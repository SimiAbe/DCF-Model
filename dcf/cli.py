"""Command-line interface: ``python -m dcf examples/example_company.json``."""

from __future__ import annotations

import argparse
import sys

from .config import load_inputs
from .model import sensitivity, value
from .report import format_projection, format_sensitivity, format_summary, write_csv


def _steps(centre: float, step: float, count: int = 5) -> list[float]:
    half = count // 2
    return [round(centre + step * k, 6) for k in range(-half, half + 1)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dcf", description="Run a discounted cash flow valuation.")
    parser.add_argument("config", help="path to a JSON or TOML inputs file")
    parser.add_argument("--csv", metavar="PATH", help="write the yearly projection to a CSV file")
    parser.add_argument("--no-sensitivity", action="store_true", help="skip the sensitivity table")
    parser.add_argument("--wacc-step", type=float, default=0.005, help="WACC step for sensitivity (default 0.005)")
    parser.add_argument("--growth-step", type=float, default=0.005, help="terminal growth step (default 0.005)")
    parser.add_argument("--multiple-step", type=float, default=1.0, help="exit multiple step (default 1.0)")
    args = parser.parse_args(argv)

    try:
        inputs = load_inputs(args.config)
        result = value(inputs)
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(format_projection(result))
    print()
    print(format_summary(result))

    if not args.no_sensitivity:
        rates = _steps(result.wacc, args.wacc_step)
        if inputs.terminal_method == "perpetuity":
            cols = _steps(inputs.terminal_growth, args.growth_step)
        else:
            cols = _steps(inputs.exit_multiple or 0.0, args.multiple_step)
        grid = sensitivity(inputs, rates, cols)
        print()
        print(format_sensitivity(grid, rates, cols, inputs.terminal_method))

    if args.csv:
        write_csv(result, args.csv)
        print(f"\nProjection written to {args.csv}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
