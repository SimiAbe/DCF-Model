"""Load model inputs from a JSON or TOML file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import DCFInputs, WACCInputs


def inputs_from_dict(data: dict[str, Any]) -> DCFInputs:
    data = dict(data)
    wacc = data.pop("wacc_inputs", None)
    if wacc is not None:
        data["wacc_inputs"] = WACCInputs(**wacc)
    return DCFInputs(**data)


def load_inputs(path: str | Path) -> DCFInputs:
    path = Path(path)
    if path.suffix.lower() == ".toml":
        try:
            import tomllib
        except ModuleNotFoundError as exc:  # Python < 3.11
            raise RuntimeError("TOML configs need Python 3.11+; use JSON instead") from exc
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    else:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    data.pop("_comment", None)
    return inputs_from_dict(data)
