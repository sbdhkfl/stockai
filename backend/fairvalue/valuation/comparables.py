"""Comparable Company Analysis — market multiples of peer companies.

Formula
-------
peer multiples are computed from raw peer fundamentals (never stored):
EV/EBITDA = EV / EBITDA ; P/E = market cap / net income ;
EV/Sales = EV / revenue ; P/B = market cap / book equity.
Company value = statistic(peer multiples) × company metric
               (enterprise multiples → − net debt → equity; equity multiples → equity).
Value/share across selected multiples is combined with the same statistic (median/mean).
"""

from __future__ import annotations

from statistics import mean, median

from fairvalue.core.schemas import ComparablesAssumptions, ModelResult, ValuationInputs
from fairvalue.valuation.base import not_applicable

MODEL = "comparables"

LIMITATIONS = [
    "Peers trade at their own mispricings and growth/risk mixes; multiples transfer those biases.",
    "Reported peer metrics may be as of different dates than the company's fiscal year end.",
    "A median of few peers is fragile: the peer count is always reported with the result.",
]


def _peer_multiple(kind: str, p) -> float | None:
    if kind == "ev_ebitda":
        if p.enterprise_value is None or not p.ebitda or p.ebitda <= 0:
            return None
        return p.enterprise_value / p.ebitda
    if kind == "ev_sales":
        if p.enterprise_value is None or not p.revenue or p.revenue <= 0:
            return None
        return p.enterprise_value / p.revenue
    if kind == "pe":
        if p.price is None or not p.shares_outstanding or not p.net_income or p.net_income <= 0:
            return None
        return (p.price * p.shares_outstanding) / p.net_income
    if kind == "pb":
        if p.price is None or not p.shares_outstanding or not p.equity or p.equity <= 0:
            return None
        return (p.price * p.shares_outstanding) / p.equity
    return None


def _company_per_share(kind: str, multiple: float, iv: ValuationInputs) -> float | None:
    if kind == "ev_ebitda":
        if iv.ebitda is None or iv.net_debt is None:
            return None
        return (multiple * iv.ebitda - iv.net_debt) / float(iv.shares_outstanding)
    if kind == "ev_sales":
        if iv.revenue is None or iv.net_debt is None:
            return None
        return (multiple * iv.revenue - iv.net_debt) / float(iv.shares_outstanding)
    if kind == "pe":
        if iv.eps is not None:
            return multiple * iv.eps
        if iv.net_income is not None and iv.shares_outstanding:
            return multiple * (iv.net_income / iv.shares_outstanding)
        return None
    if kind == "pb":
        if iv.book_equity is None or not iv.shares_outstanding:
            return None
        return multiple * (iv.book_equity / float(iv.shares_outstanding))
    return None


def calculate(iv: ValuationInputs, a: ComparablesAssumptions) -> ModelResult:
    if not iv.peers:
        return not_applicable(
            MODEL,
            "no peer data source configured (live mode has no free peer feed; supply peers or use demo mode)",
            limitation=LIMITATIONS[0],
        )
    if not iv.shares_outstanding:
        return not_applicable(MODEL, "shares outstanding missing")

    stat = median if a.statistic == "median" else mean
    steps: list[str] = [f"{len(iv.peers)} peers; statistic = {a.statistic}."]
    per_share_values: list[float] = []
    used: list[str] = []
    warnings: list[str] = []

    for kind in a.multiples:
        mults = [m for m in (_peer_multiple(kind, p) for p in iv.peers) if m is not None]
        usable_peers = len(mults)
        if usable_peers < a.min_peers:
            steps.append(f"{kind}: only {usable_peers} peer(s) with usable data (< {a.min_peers}) — skipped")
            continue
        m = float(stat(mults))
        v = _company_per_share(kind, m, iv)
        steps.append(
            f"{kind}: peer multiples {[round(x, 1) for x in sorted(mults)]} → {a.statistic} {m:.1f}x"
            + (f" → {v:,.2f}/share" if v is not None else " → inputs missing on target company, skipped")
        )
        if v is not None:
            per_share_values.append(v)
            used.append(kind)

    if not per_share_values:
        return not_applicable(
            MODEL, "no multiple could be applied: peer data or company metrics insufficient",
            limitation=LIMITATIONS[1],
        )

    value = float(stat(per_share_values))
    steps.append(
        f"Across {used}: {a.statistic} = {value:,.2f}/share"
        + (f" (range {min(per_share_values):,.2f}–{max(per_share_values):,.2f})" if len(per_share_values) > 1 else "")
    )
    if len(per_share_values) > 1 and max(per_share_values) / min(per_share_values) > 1.5:
        warnings.append("multiples disagree by >50% — the peer set spans incompatible business models")

    n_peers = min(len(iv.peers), min(len([p for p in iv.peers]), 8))
    suitability = 0.5 + 0.05 * n_peers - (0.1 if len(per_share_values) == 1 else 0.0)

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        confidence="medium" if len(iv.peers) >= 4 else "low",
        suitability=max(0.2, min(1.0, suitability)),
        assumptions=a.model_dump(),
        formula="value/share = statistic(peer multiples) × company metric (− net debt for enterprise multiples)",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
