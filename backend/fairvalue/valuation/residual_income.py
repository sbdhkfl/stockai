"""Residual income valuation: V0 = B0 + sum (E_t - r*B_{t-1})/(1+r)^t.

Book value rolls forward as B_t = B_{t-1} + E_t - D_t (clean surplus relation).
Appropriate where book equity is meaningful, notably banks and insurers.
"""
import math
from ..errors import FairValueError, NotMeaningfulError


def residual_income_value(book_value0: float, earnings: list,
                          cost_of_equity: float, dividends: list = None) -> float:
    if not earnings:
        raise FairValueError("earnings: at least one forecast year required")
    if any(not math.isfinite(x) for x in [book_value0, cost_of_equity, *earnings]):
        raise FairValueError("residual income inputs must be finite")
    if dividends is not None and any(not math.isfinite(x) for x in dividends):
        raise FairValueError("dividends must be finite")
    if book_value0 <= 0:
        raise NotMeaningfulError("non-positive book equity: residual income not meaningful")
    if cost_of_equity <= 0:
        raise FairValueError("cost_of_equity must be > 0")
    if dividends is not None and len(dividends) != len(earnings):
        raise FairValueError("dividends and earnings must have equal length")

    value = book_value0
    b = book_value0
    for t, e in enumerate(earnings):
        d = dividends[t] if dividends is not None else 0.0
        ri = e - cost_of_equity * b
        value += ri / (1.0 + cost_of_equity) ** (t + 1)
        b = b + e - d
    return value
