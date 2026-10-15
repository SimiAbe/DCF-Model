"""A small, dependency-free discounted cash flow (DCF) valuation model."""

from .config import inputs_from_dict, load_inputs
from .model import DCFInputs, DCFResult, WACCInputs, YearProjection, project, sensitivity, value

__all__ = [
    "DCFInputs",
    "DCFResult",
    "WACCInputs",
    "YearProjection",
    "inputs_from_dict",
    "load_inputs",
    "project",
    "sensitivity",
    "value",
]
__version__ = "0.1.0"
