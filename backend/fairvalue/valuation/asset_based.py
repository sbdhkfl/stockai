"""Asset-based valuation: adjusted net asset value.

Every adjustment must carry a human-readable reason (provenance rule):
adjusted_nav = book_equity + sum(adjustment deltas), each with {item, delta, reason}.
"""
from dataclasses import dataclass
import math
from ..errors import FairValueError


@dataclass(frozen=True)
class Adjustment:
    item: str
    delta: float
    reason: str


def adjusted_nav(book_equity: float, adjustments: list) -> dict:
    if not math.isfinite(book_equity):
        raise FairValueError("book_equity must be finite")
    total = book_equity
    for a in adjustments:
        if not isinstance(a, Adjustment):
            raise FairValueError("adjustments must be Adjustment objects")
        if not math.isfinite(a.delta):
            raise FairValueError(f"adjustment '{a.item}' delta must be finite")
        if not a.reason or not a.reason.strip():
            raise FairValueError(f"adjustment '{a.item}' requires a documented reason")
        total += a.delta
    return {"adjusted_nav": total,
            "adjustments_applied": len(adjustments),
            "adjustments": adjustments}
