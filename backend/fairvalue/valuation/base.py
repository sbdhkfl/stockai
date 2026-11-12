"""Shared helpers for the nine valuation models.

Every model is a pure function ``calculate(inputs, assumptions) -> ModelResult``:
it never raises for missing data and never invents values — it returns
``applicable=False`` with a precise ``excluded_reason`` (ARCHITECTURE.md §4).
"""

from __future__ import annotations

from fairvalue.core.schemas import (
    Confidence,
    Fact,
    ModelResult,
    ValuationInputs,
)

MODEL_NAMES = (
    "dcf", "ddm", "comparables", "precedents", "residual_income",
    "epv", "graham", "asset_based", "sotp",
)


def not_applicable(model: str, reason: str, *, limitation: str | None = None) -> ModelResult:
    return ModelResult(
        model=model,
        applicable=False,
        excluded_reason=reason,
        limitations=[limitation] if limitation else [],
        suitability=0.0,
        confidence="low",
    )


def per_share(value: float, shares: float) -> float:
    return value / shares


def hist_cagr(facts: list[Fact], *, years_cap: int = 5) -> float | None:
    """CAGR across up to ``years_cap`` most recent points; None when < 2 points
    or any non-positive value (growth from a negative base is undefined)."""
    pts = [f.value for f in facts[-(years_cap + 1):]]
    if len(pts) < 2 or pts[0] <= 0 or pts[-1] <= 0:
        return None
    n = len(pts) - 1
    return float((pts[-1] / pts[0]) ** (1.0 / n) - 1.0)


def avg(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def historical_rates(iv: ValuationInputs, concept: str, denom: str) -> list[float]:
    """Ratio of two concepts per historical period (e.g. capex/revenue)."""
    out = []
    for p in iv.history:
        a, b = p.facts.get(concept), p.facts.get(denom)
        if a and b and b.value != 0:
            out.append(a.value / b.value)
    return out


def confidence_for(history_len: int, has_price: bool) -> Confidence:
    if history_len >= 5 and has_price:
        return "high"
    if history_len >= 3:
        return "medium"
    return "low"
