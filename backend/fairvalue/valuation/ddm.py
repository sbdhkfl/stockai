"""Dividend Discount Models: Gordon single-stage and two-stage."""
from dataclasses import dataclass
import math
from ..errors import FairValueError, NotMeaningfulError


@dataclass(frozen=True)
class DDMResult:
    value: float
    pv_explicit_dividends: float
    pv_terminal: float


def gordon_ddm(d0: float, r: float, g: float) -> float:
    """P0 = D1/(r-g) with D1 = D0*(1+g). Negative g allowed (declining payer)."""
    if not all(math.isfinite(x) for x in (d0, r, g)):
        raise FairValueError("ddm inputs must be finite")
    if d0 < 0:
        raise FairValueError("d0 (dividend) cannot be negative")
    if d0 == 0:
        raise NotMeaningfulError("company pays no dividend; DDM not meaningful")
    if r <= 0:
        raise FairValueError("cost of equity r must be > 0")
    if g >= r:
        raise FairValueError("g must be < r")
    return d0 * (1.0 + g) / (r - g)


def two_stage_ddm(d0: float, r: float, g_high: float, growth_years: int,
                  g_terminal: float) -> DDMResult:
    """Explicit high-growth dividends, then Gordon terminal at g_terminal."""
    if growth_years < 1:
        raise FairValueError("growth_years must be >= 1")
    if not all(math.isfinite(x) for x in (d0, r, g_high, g_terminal)):
        raise FairValueError("ddm inputs must be finite")
    if d0 <= 0:
        raise NotMeaningfulError("company pays no dividend; DDM not meaningful")
    if r <= 0:
        raise FairValueError("cost of equity r must be > 0")
    if g_terminal >= r:
        raise FairValueError("terminal g must be < r")

    pv_explicit = 0.0
    d = d0
    for t in range(1, growth_years + 1):
        d *= (1.0 + g_high)
        pv_explicit += d / (1.0 + r) ** t
    d_term = d * (1.0 + g_terminal)
    if d_term <= 0:
        raise NotMeaningfulError("terminal dividend <= 0; two-stage DDM not meaningful")
    pv_terminal = d_term / (r - g_terminal) / (1.0 + r) ** growth_years
    return DDMResult(value=pv_explicit + pv_terminal,
                     pv_explicit_dividends=pv_explicit, pv_terminal=pv_terminal)


# ---------------------------------------------------------------------------
# Contract adapter: ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, DdmAssumptions, ModelResult


def run_model(inputs: ValuationInputs, a: DdmAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    latest = inputs.history[-1] if inputs.history else None
    dps = (latest.facts.get("dps").value if latest and "dps" in latest.facts
           else inputs.dps)
    if not dps or dps <= 0:
        return ModelResult(model="ddm", applicable=False,
                           excluded_reason="company pays no dividend (dps missing or 0)",
                           **base)
    r = two_stage_ddm(dps, a.required_return, a.stage1_growth, a.stage1_years,
                      a.terminal_growth)
    steps = [f"D0 = {dps:.4f} (reported dps)",
             f"stage 1: {a.stage1_years}y at {a.stage1_growth:.1%}, "
             f"PV = {r.pv_explicit_dividends:.4f}",
             f"terminal Gordon at g={a.terminal_growth:.1%}, PV = {r.pv_terminal:.4f}"]
    return ModelResult(model="ddm", applicable=True, value_per_share=r.value,
                       equity_value=r.value,  # DDM discounts equity flows directly
                       **base,
                       formula="P0 = sum D_t/(1+r)^t + D_{n+1}/(r-g_t)/(1+r)^n",
                       steps=steps,
                       limitations=["unsuitable for non-payers and buyback-heavy firms",
                                    "value extremely sensitive to r-g spread"])
