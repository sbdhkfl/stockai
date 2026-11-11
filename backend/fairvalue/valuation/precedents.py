"""Precedent Transactions analysis.

Deal multiples are applied to the target's metric with an optional control
premium (acquirers pay for control; trading comps do not include it).
Median statistic by default. Non-positive deal metrics are excluded, never zero.
"""
from statistics import median
from ..errors import FairValueError, NotMeaningfulError


def precedent_median_multiple(deal_multiples: list) -> float:
    clean = [m for m in deal_multiples if m is not None and m > 0]
    if not clean:
        raise NotMeaningfulError("no positive precedent deal multiples available")
    return median(clean)


def implied_value_precedents(deal_multiples: list, target_metric: float,
                             control_premium: float = 0.0) -> float:
    if target_metric <= 0:
        raise NotMeaningfulError("target metric <= 0: precedent value not meaningful")
    if not (0.0 <= control_premium <= 1.0):
        raise FairValueError("control_premium must be in [0, 1]")
    return precedent_median_multiple(deal_multiples) * target_metric * (1.0 + control_premium)


# ---------------------------------------------------------------------------
# Contract adapter (docs/ARCHITECTURE.md §3): ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, PrecedentAssumptions, ModelResult
from ..core.schemas import SourceRef
from datetime import datetime, timezone


def run_model(inputs: ValuationInputs, a: PrecedentAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    if not inputs.transactions:
        return ModelResult(model="precedents", applicable=False,
                           excluded_reason="no precedent transactions available", **base)
    metric_key = "ebitda" if a.multiple == "ev_ebitda" else "revenue"
    mults, used = [], []
    for t in inputs.transactions:
        ev, m = t.enterprise_value, getattr(t, metric_key)
        if ev and m and m > 0:
            mults.append(ev / m)
            used.append(t.target)
    if len(mults) < a.min_transactions:
        return ModelResult(model="precedents", applicable=False,
                           excluded_reason=f"only {len(mults)} usable transactions "
                                           f"(min {a.min_transactions})", **base)
    target_metric = getattr(inputs, metric_key, None)
    if not target_metric or target_metric <= 0:
        return ModelResult(model="precedents", applicable=False,
                           excluded_reason=f"target {metric_key} missing or <= 0", **base)
    if not inputs.shares_outstanding:
        return ModelResult(model="precedents", applicable=False,
                           excluded_reason="shares outstanding missing", **base)
    med = median(mults)
    ev = med * target_metric * (1.0 + a.control_premium)
    equity = ev - (inputs.net_debt or 0.0)
    steps = [f"median {a.multiple} of {len(mults)} deals = {med:.3f}x",
             f"implied EV = {med:.3f} x {metric_key} {target_metric:,.0f} "
             f"x (1 + control premium {a.control_premium:.0%}) = {ev:,.0f}",
             f"equity = EV - net debt {inputs.net_debt or 0.0:,.0f} = {equity:,.0f}",
             f"per share = {equity:,.0f} / {inputs.shares_outstanding:,.0f}"]
    return ModelResult(model="precedents", applicable=True,
                       value_per_share=equity / inputs.shares_outstanding,
                       enterprise_value=ev, equity_value=equity,
                       assumptions=base, formula="median deal multiple x metric x (1+control premium); equity = EV - net debt",
                       steps=steps,
                       warnings=[f"deal sample: {', '.join(used)}"] if used else [],
                       limitations=["deal multiples embed deal-specific synergies and "
                                    "vintage financing conditions"])
