"""Kaynak panelden alınan sabitler ve ortak girdi doğrulaması. Superset gerektirmez."""

import json
import math
from importlib.resources import files

DATA = json.loads(files("flyup3.sim").joinpath("data.json").read_text())
CUSTOMERS = {c["id"]: c for c in DATA["customers"]}


def number(value, label, minimum=0, maximum=None, integer=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < minimum
        or (maximum is not None and value > maximum)
        or (integer and int(value) != value)
    ):
        bounds = f"{minimum}–{maximum}" if maximum is not None else f"≥{minimum}"
        raise ValueError(
            f"{label}: sonlu sayı ({bounds})" + (" ve tam sayı" if integer else "") + " olmalı."
        )
    return value


def keys(values, allowed, label):
    unknown = set(values or {}) - set(allowed)
    if unknown:
        raise ValueError(
            f"{label}: bilinmeyen ad {', '.join(sorted(unknown))}. "
            f"İzin verilenler: {', '.join(allowed)}"
        )


def customer_keys(values):
    keys(values, CUSTOMERS, "Bilinmeyen müşteri")


def response(inputs, results, summary, assumptions):
    return {"inputs": inputs, "results": results, "summary": summary, "assumptions": assumptions}
