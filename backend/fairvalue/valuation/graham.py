"""Graham-style valuation (The Intelligent Investor, Ch. 11).

Formula
-------
V = EPS · (8.5 + 2g)        8.5 = base P/E of a no-growth company, g = expected
                            annual growth over ~7 years (capped at 15% here).
Defensive screens produce warnings, not exclusions.
"""

from __future__ import annotations

from fairvalue.core.schemas import GrahamAssumptions, ModelResult, ValuationInputs
from fairvalue.valuation.base import hist_cagr, not_applicable

MODEL = "graham"

LIMITATIONS = [
    "A 1930s-era heuristic: the fixed 8.5 base P/E ignores current interest rates and sector economics.",
    "The growth input dominates the output (V scales with 2g) — it must be an estimate, and estimates vary widely.",
    "Ignores balance sheet, reinvestment needs and risk beyond a simple quality screen.",
]


def calculate(iv: ValuationInputs, a: GrahamAssumptions) -> ModelResult:
    if iv.eps is None or iv.eps <= 0:
        return not_applicable(MODEL, "positive diluted EPS missing — Graham formula requires earnings per share")

    eps_hist = iv.concept_history("eps_diluted")
    if a.growth_rate is not None:
        g, g_basis = a.growth_rate, "assumed"
    else:
        cagr = hist_cagr(eps_hist, years_cap=5)
        if cagr is None:
            return not_applicable(
                MODEL, "growth_rate not provided and insufficient historical EPS to derive one (need ≥2 positive years)"
            )
        g, g_basis = min(max(cagr, 0.0), 0.15), "historical EPS CAGR (floored at 0, capped at 15%)"

    value = iv.eps * (8.5 + 2 * g)
    steps = [
        f"V = EPS {iv.eps:.2f} × (8.5 + 2 × g {g:.1%} [{g_basis}]) = {value:,.2f}/share",
    ]

    warnings: list[str] = []
    ni_by_year = [(p.fiscal_year, p.facts["net_income"].value) for p in iv.history if p.facts.get("net_income")]
    if len(ni_by_year) >= 2 and any(
        ni_by_year[i][1] < ni_by_year[i - 1][1] for i in range(1, len(ni_by_year))
    ):
        warnings.append("earnings declined in the historical window — Graham quality screen not met")
    ca = next((p.facts["current_assets"].value for p in reversed(iv.history) if p.facts.get("current_assets")), None)
    cl = next((p.facts["current_liabilities"].value for p in reversed(iv.history) if p.facts.get("current_liabilities")), None)
    if ca is not None and cl is not None:
        if ca < 2 * cl:
            warnings.append(
                f"defensive criterion not met: current assets {ca:,.0f} < 2× current liabilities {cl:,.0f}"
            )
        else:
            steps.append(f"Defensive screen: current assets {ca:,.0f} ≥ 2× current liabilities {cl:,.0f} ✓")
    if g > 0.10:
        warnings.append(f"growth {g:.0%} is aggressive for the Graham formula — value scales directly with 2g")
    if iv.price:
        gap = (value - iv.price) / iv.price
        steps.append(f"vs market price {iv.price:,.2f}: {'above' if gap > 0 else 'below'} by {abs(gap):.0%}")

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        equity_value=value * iv.shares_outstanding if iv.shares_outstanding else None,
        confidence="low",
        suitability=0.45 if a.quality_required and warnings else 0.55,
        assumptions={**a.model_dump(), "growth_rate_used": g},
        formula="V = EPS × (8.5 + 2g)",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
