"""Dividend Discount Model — two-stage Gordon growth.

Formula
-------
V = Σ_{t=1..n} DPS_0·(1+g1)^t / (1+r)^t  +  [DPS_n·(1+g)/(r−g)] / (1+r)^n
Applicable only when the company actually reports dividends per share.
"""

from __future__ import annotations

from fairvalue.core.schemas import DdmAssumptions, ModelResult, ValuationInputs
from fairvalue.valuation.base import hist_cagr, not_applicable

MODEL = "ddm"

LIMITATIONS = [
    "Values only the cash the company distributes; capital-return policies outside DPS (buybacks) are ignored.",
    "Assumes the stated dividend policy persists — cut-prone payouts make the result fragile.",
    "Unusable for non-payers; that exclusion is reported rather than replaced with a proxy.",
]


def calculate(iv: ValuationInputs, a: DdmAssumptions) -> ModelResult:
    if iv.dps is None or iv.dps <= 0:
        return not_applicable(
            MODEL, "no positive dividend reported — DDM cannot value a non-payer",
            limitation=LIMITATIONS[0],
        )

    dps0 = iv.dps
    steps = [
        f"Base DPS {dps0:.2f}; stage 1 growth {a.stage1_growth:+.1%} for {a.stage1_years} years "
        f"at required return {a.required_return:.2%}; terminal growth {a.terminal_growth:.2%}."
    ]

    pv = 0.0
    for t in range(1, a.stage1_years + 1):
        dps = dps0 * (1 + a.stage1_growth) ** t
        pv += dps / (1 + a.required_return) ** t
    dps_n = dps0 * (1 + a.stage1_growth) ** a.stage1_years
    tv = dps_n * (1 + a.terminal_growth) / (a.required_return - a.terminal_growth)
    tv_pv = tv / (1 + a.required_return) ** a.stage1_years
    value = pv + tv_pv

    steps.append(f"Stage 1 PV of dividends {pv:,.2f}")
    steps.append(
        f"Terminal: {dps_n:.2f}·(1+{a.terminal_growth:.2%})/({a.required_return:.2%}−{a.terminal_growth:.2%}) "
        f"= {tv:,.2f}, PV {tv_pv:,.2f}"
    )
    steps.append(f"Equity value/share = {pv:,.2f} + {tv_pv:,.2f} = {value:,.2f}")

    warnings: list[str] = []
    hist = [f.value for f in iv.concept_history("dps")]
    if len(hist) >= 3:
        cut = any(hist[i + 1] < hist[i] for i in range(len(hist) - 1))
        if cut:
            warnings.append("dividend was cut in the historical window — stage-1 growth assumption is fragile")
        cagr = hist_cagr(iv.concept_history("dps"))
        if cagr is not None and abs(cagr - a.stage1_growth) > 0.05:
            warnings.append(
                f"assumed stage-1 growth {a.stage1_growth:+.1%} differs from historical DPS CAGR {cagr:+.1%}"
            )
    if tv_pv / value > 0.75 if value else False:
        warnings.append("terminal value dominates (>75%) — highly sensitive to r vs g spread")

    suitability = 0.75 if len(hist) >= 3 else 0.55
    if iv.price is not None and value > 0:
        gap = abs(value - iv.price) / iv.price
        if gap > 0.6:
            warnings.append(f"DDM result differs from market price by {gap:.0%} — dividend policy may not reflect value")

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        equity_value=value * iv.shares_outstanding if iv.shares_outstanding else None,
        confidence="medium" if len(hist) >= 3 else "low",
        suitability=suitability,
        assumptions=a.model_dump(),
        formula="V = Σ DPS_t/(1+r)^t + [DPS_n(1+g)/(r−g)]/(1+r)^n",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
