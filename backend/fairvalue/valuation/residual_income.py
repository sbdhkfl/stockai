"""Residual Income Model (EVA / economic profit).

Formula
-------
RI_t = (ROE − r_e) · BV_{t−1} ;  BV_t = BV_{t−1}·(1 + ROE·retention)
V = BV_0 + Σ_{t=1..n} RI_t/(1+r_e)^t + RI_{n+1}/(r_e − g) / (1+r_e)^n
    (g = ROE·retention sustainable growth; if g ≥ r_e a no-growth perpetuity RI_n/r_e is used)
"""

from __future__ import annotations

from fairvalue.core.schemas import ModelResult, ResidualIncomeAssumptions, ValuationInputs
from fairvalue.valuation.base import not_applicable

MODEL = "residual_income"

LIMITATIONS = [
    "Anchor is book value: heavily off-balance-sheet assets/intangibles (brands, R&D) are worth only what book earns on them.",
    "Sensitive to the ROE assumption — a mean-reverting ROE makes long-horizon RI optimistic for incumbents.",
    "Accounting quality matters: reported equity is only as trustworthy as the filings it comes from.",
]


def calculate(iv: ValuationInputs, a: ResidualIncomeAssumptions) -> ModelResult:
    if iv.book_equity is None or iv.book_equity <= 0:
        return not_applicable(MODEL, "book equity missing from latest balance sheet")
    if not iv.shares_outstanding:
        return not_applicable(MODEL, "shares outstanding missing")

    r = a.cost_of_equity
    roe = a.roe
    if roe is None:
        ratios = []
        for p in iv.history:
            ni, bv = p.facts.get("net_income"), p.facts.get("equity")
            if ni and bv and bv.value > 0:
                ratios.append(ni.value / bv.value)
        if not ratios:
            return not_applicable(MODEL, "ROE not set and no historical net income/equity to derive it")
        roe = sum(ratios) / len(ratios)

    bv = iv.book_equity
    g = roe * a.retention_ratio
    steps = [
        f"Book value {bv:,.0f}; ROE {roe:.1%} "
        f"({'assumed' if a.roe is not None else 'average of reported history'}); "
        f"cost of equity {r:.2%}; retention {a.retention_ratio:.0%} (g = {g:.1%}); horizon {a.forecast_years}y."
    ]

    pv_ri = 0.0
    for t in range(1, a.forecast_years + 1):
        ri = (roe - r) * bv
        pv_ri += ri / (1 + r) ** t
        bv_next = bv * (1 + roe * a.retention_ratio)
        steps.append(
            f"Y{t}: RI = ({roe:.1%} − {r:.2%}) × BV {bv:,.0f} = {ri:,.0f} (PV {ri / (1 + r) ** t:,.0f}); "
            f"BV → {bv_next:,.0f}"
        )
        bv = bv_next

    bv0 = iv.book_equity
    if g < r:
        tv_ri = (roe - r) * bv * (1 + g) / (r - g) if roe != r else 0.0
        tv_note = f"terminal (Gordon on RI): RI_next/(r−g)"
    else:
        tv_ri = (roe - r) * bv / r
        tv_note = "terminal (no-growth perpetuity: g ≥ r_e)"
    tv_pv = tv_ri / (1 + r) ** a.forecast_years
    value = bv0 + pv_ri + tv_pv
    per_share = value / float(iv.shares_outstanding)
    steps.append(f"{tv_note} PV {tv_pv:,.0f}")
    steps.append(f"V = BV {bv0:,.0f} + PV(RI) {pv_ri:,.0f} + PV(terminal) {tv_pv:,.0f} = {value:,.0f} "
                 f"÷ {iv.shares_outstanding:,.0f} = {per_share:,.2f}/share")

    warnings = []
    if roe < r:
        warnings.append(f"ROE {roe:.1%} below cost of equity {r:.1%}: model values the company below book — value destruction")
    hist_roe = [p.facts["net_income"].value / p.facts["equity"].value
                for p in iv.history
                if p.facts.get("net_income") and p.facts.get("equity") and p.facts["equity"].value > 0]
    if len(hist_roe) >= 2 and roe is not None and hist_roe:
        spread = max(hist_roe) - min(hist_roe)
        if spread > 0.10:
            warnings.append(f"historical ROE varies by {spread:.0%} — single-ROE extrapolation is crude")

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=per_share,
        equity_value=value,
        confidence="medium" if len(iv.history) >= 3 else "low",
        suitability=0.7 if (roe is not None and roe > r) else 0.5,
        assumptions={**a.model_dump(), "roe_used": roe},
        formula="V = BV₀ + Σ RI_t/(1+rₑ)^t + terminal RI; RI_t = (ROE−rₑ)·BV_{t−1}",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
