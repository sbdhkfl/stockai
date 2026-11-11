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



# ---------------------------------------------------------------------------
# Contract adapter: ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, AssetBasedAssumptions, ModelResult


def run_model(inputs: ValuationInputs, a: AssetBasedAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    if not inputs.book_equity:
        return ModelResult(model="asset_based", applicable=False,
                           excluded_reason="book equity missing", **base)
    if not inputs.shares_outstanding:
        return ModelResult(model="asset_based", applicable=False,
                           excluded_reason="shares outstanding missing", **base)
    equity = inputs.book_equity + a.asset_adjustments - a.liability_adjustments
    steps = [f"book equity {inputs.book_equity:,.0f} + asset adj {a.asset_adjustments:,.0f}"
             f" - liability adj {a.liability_adjustments:,.0f} = {equity:,.0f}",
             f"per share = {equity:,.0f} / {inputs.shares_outstanding:,.0f}"]
    return ModelResult(model="asset_based", applicable=True,
                       value_per_share=equity / inputs.shares_outstanding,
                       equity_value=equity, **base,
                       formula="adjusted NAV = book equity + asset adjustments - liability adjustments",
                       steps=steps,
                       limitations=["book values need fair-value audit; adjustments must be documented"])
