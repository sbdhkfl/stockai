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


# ---------------------------------------------------------------------------
# Contract adapter: ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, ResidualIncomeAssumptions, ModelResult


def run_model(inputs: ValuationInputs, a: ResidualIncomeAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    latest = inputs.history[-1] if inputs.history else None
    b0 = inputs.book_equity
    if not b0 or b0 <= 0:
        return ModelResult(model="residual_income", applicable=False,
                           excluded_reason="book equity missing or <= 0", **base)
    if not inputs.shares_outstanding:
        return ModelResult(model="residual_income", applicable=False,
                           excluded_reason="shares outstanding missing", **base)
    roe = a.roe
    if roe is None:
        ratios = [p.facts["net_income"].value / p.facts["equity"].value
                  for p in inputs.history
                  if "net_income" in p.facts and "equity" in p.facts
                  and p.facts["equity"].value > 0]
        if not ratios:
            return ModelResult(model="residual_income", applicable=False,
                               excluded_reason="no ROE derivable from history and "
                                               "no roe assumption supplied", **base)
        roe = sum(ratios) / len(ratios)
    earnings, dividends, b = [], [], b0
    for _ in range(a.forecast_years):
        e = roe * b
        d = (1.0 - a.retention_ratio) * e
        earnings.append(e)
        dividends.append(d)
        b = b + e - d
    v = residual_income_value(b0, earnings, a.cost_of_equity, dividends)
    steps = [f"B0 = {b0:,.0f}; ROE = {roe:.1%}, retention {a.retention_ratio:.0%}",
             f"clean surplus: B_t = B_(t-1) + E_t - D_t over {a.forecast_years}y",
             f"RI_t = E_t - r*B_(t-1) discounted at r = {a.cost_of_equity:.1%}"]
    return ModelResult(model="residual_income", applicable=True,
                       value_per_share=v / inputs.shares_outstanding,
                       equity_value=v, **base,
                       formula="V0 = B0 + sum (E_t - r*B_(t-1))/(1+r)^t, clean-surplus book roll-forward",
                       steps=steps,
                       limitations=["assumes ROE converges toward competitive levels "
                                    "beyond the horizon; steady-state ROE assumed constant"])
