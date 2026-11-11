"""Earnings Power Value (Greenwald): growth-free value of normalized earnings.

Normalized earnings = (EBIT - SBC) * (1 - tax) - (maintenance capex - depreciation)
EPV = normalized earnings / cost of capital.
SBC is treated as a real economic expense; maintenance capex substitutes for total
capex to strip growth investment.
"""
import math
from ..errors import FairValueError, NotMeaningfulError


def epv(ebit: float, tax_rate: float, maintenance_capex: float,
        depreciation: float, sbc: float, cost_of_capital: float) -> float:
    if any(not math.isfinite(x) for x in
           (ebit, tax_rate, maintenance_capex, depreciation, sbc, cost_of_capital)):
        raise FairValueError("epv inputs must be finite")
    if not (0.0 <= tax_rate < 1.0):
        raise FairValueError("tax_rate must be in [0, 1)")
    if cost_of_capital <= 0:
        raise FairValueError("cost_of_capital must be > 0")
    normalized = (ebit - sbc) * (1.0 - tax_rate) - (maintenance_capex - depreciation)
    if normalized <= 0:
        raise NotMeaningfulError(
            f"normalized earnings {normalized} <= 0; EPV not meaningful")
    return normalized / cost_of_capital


# ---------------------------------------------------------------------------
# Contract adapter: ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, EpvAssumptions, ModelResult


def run_model(inputs: ValuationInputs, a: EpvAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    latest = inputs.history[-1] if inputs.history else None
    if not latest or "revenue" not in latest.facts or "ebit" not in latest.facts:
        return ModelResult(model="epv", applicable=False,
                           excluded_reason="revenue and EBIT required", **base)
    if not inputs.shares_outstanding:
        return ModelResult(model="epv", applicable=False,
                           excluded_reason="shares outstanding missing", **base)
    rev = latest.facts["revenue"].value
    if a.margin_normalization == "historical_average" and inputs.history:
        margins = [p.facts["ebit"].value / p.facts["revenue"].value
                   for p in inputs.history
                   if "ebit" in p.facts and p.facts.get("revenue") and p.facts["revenue"].value > 0]
        margin = sum(margins) / len(margins) if margins else \
            latest.facts["ebit"].value / rev
    else:
        margin = latest.facts["ebit"].value / rev
    normalized_ebit = margin * rev
    e = normalized_ebit * (1.0 - a.tax_rate)
    if e <= 0:
        return ModelResult(model="epv", applicable=False,
                           excluded_reason="normalized after-tax earnings <= 0", **base)
    ev = e / a.wacc
    equity = ev - (inputs.net_debt or 0.0)
    steps = [f"normalized EBIT margin {margin:.1%} ({a.margin_normalization}) x revenue "
             f"{rev:,.0f} = {normalized_ebit:,.0f}",
             f"after-tax {e:,.0f} / WACC {a.wacc:.1%} = EV {ev:,.0f}",
             f"equity = {equity:,.0f} after net debt {inputs.net_debt or 0.0:,.0f}"]
    return ModelResult(model="epv", applicable=True,
                       value_per_share=equity / inputs.shares_outstanding,
                       enterprise_value=ev, equity_value=equity,
                       **base,
                       formula="EPV = normalized (EBIT*(1-t)) / WACC; growth-free",
                       steps=steps,
                       limitations=["growth-free by design: no credit for growth options",
                                    "distorts cyclicals measured at peak earnings"])
