"""Graham-style valuation.

Revised Graham formula: V = EPS * (8.5 + 2*g) * 4.4 / Y
where g = expected 7-10y growth in percent points (capped at 15 here; the formula
degrades empirically for high-growth names) and Y = current AAA corporate yield in
percent (Graham's 1962-era baseline was 4.4).
Graham Number: sqrt(22.5 * EPS * BVPS) — a defensive floor, not a fair value.
"""
import math
from ..errors import FairValueError, NotMeaningfulError


def graham_value(eps: float, growth_pct: float, aaa_yield_pct: float = 4.4) -> float:
    if any(not math.isfinite(x) for x in (eps, growth_pct, aaa_yield_pct)):
        raise FairValueError("graham inputs must be finite")
    if eps <= 0:
        raise NotMeaningfulError("negative or zero EPS: Graham formula not meaningful")
    if aaa_yield_pct <= 0:
        raise FairValueError("aaa_yield_pct must be > 0")
    g = max(0.0, min(15.0, growth_pct))  # documented clamp
    return eps * (8.5 + 2.0 * g) * 4.4 / aaa_yield_pct


def graham_number(eps: float, book_value_per_share: float) -> float:
    if eps <= 0 or book_value_per_share <= 0:
        raise NotMeaningfulError("Graham number requires positive EPS and BVPS")
    return math.sqrt(22.5 * eps * book_value_per_share)
