"""Deterministic AI-analyst narrative — templates over structured results.

This module NEVER invents figures: every number it mentions is copied from a
ModelResult, Reconciliation, DataQuality or RiskAssessment field produced by
the engine, and every claim traces to a report field. No LLM is involved in
producing or altering valuation numbers (ARCHITECTURE.md §1).
"""

from __future__ import annotations

from fairvalue.core.schemas import (
    ExcludedModel,
    HealthMetrics,
    ModelResult,
    Reconciliation,
    RiskAssessment,
    ValuationExplanation,
)

FAMILY_TEXT = {
    "income": "income-based models (value of future cash flows/dividends)",
    "market": "market-based models (peer and transaction multiples)",
    "asset": "asset-based models (balance-sheet value)",
}


def build_explanation(
    *,
    company_name: str,
    ticker: str,
    results: list[ModelResult],
    reconciliation: Reconciliation,
    price: float | None,
    health: HealthMetrics | None,
    risks: RiskAssessment | None,
    missing_data: list[str],
    conflicts: list[str],
    is_illustrative: bool,
) -> ValuationExplanation:
    used = reconciliation.included
    excluded = reconciliation.excluded
    base, low, high = reconciliation.base, reconciliation.low, reconciliation.high

    # --- headline ------------------------------------------------------------
    if base is None:
        headline = (
            f"No valuation could be produced for {ticker}: every model reported missing required data. "
            "Nothing was estimated in its place."
        )
    else:
        headline = f"Estimated intrinsic value ≈ {base:,.2f}/share (range {low:,.2f}–{high:,.2f})"
        if price is not None:
            gap = (price - base) / base
            direction = "above" if gap > 0 else "below"
            headline += f"; market price {price:,.2f} is {abs(gap):.0%} {direction} the base estimate"
        else:
            headline += "; market price unavailable, so no over/under-valuation comparison is made"
    if is_illustrative:
        headline += " — figures are ILLUSTRATIVE demo data, not reported financials"

    # --- methodology ---------------------------------------------------------
    families = [FAMILY_TEXT[f] for f in reconciliation.family_values]
    methodology = (
        f"Reconciliation: {reconciliation.method}. "
        + ("Family grouping applied: " + "; ".join(families) + ". " if families else "")
        + "Models lacking required data were excluded with recorded reasons rather than estimated."
    )

    # --- key assumptions (copied from model echoes, never re-derived) --------
    key_assumptions: list[str] = []
    dcf = next((r for r in results if r.model == "dcf" and r.applicable), None)
    if dcf:
        a = dcf.assumptions
        key_assumptions.append(
            f"DCF: WACC {float(a.get('wacc', 0)):.2%}, terminal growth {float(a.get('terminal_growth', 0)):.2%}, "
            f"revenue growth {float(a.get('revenue_growth', 0)):+.1%}/yr, tax {float(a.get('tax_rate', 0)):.0%}"
        )
    for r in results:
        if r.applicable and r.model == "graham":
            key_assumptions.append(
                f"Graham: growth input g = {float(r.assumptions.get('growth_rate_used', 0)):.1%}"
            )
        if r.applicable and r.model == "residual_income":
            key_assumptions.append(
                f"Residual income: ROE {float(r.assumptions.get('roe_used', 0)):.1%} vs "
                f"cost of equity {float(r.assumptions.get('cost_of_equity', 0)):.2%}"
            )
    if not key_assumptions:
        key_assumptions.append("no model was applicable — assumptions were not exercised")

    # --- invalidation conditions -------------------------------------------
    invalidate: list[str] = []
    for r in results:
        invalidate.extend(f"{r.model}: {w}" for w in r.warnings)
    if base is not None and price is not None:
        invalidate.append(
            "The estimate depends on the assumption set above; a materially different WACC, growth or margin "
            "path moves the value — use the sensitivity grid to see by how much."
        )
    if conflicts:
        invalidate.append(
            f"{len(conflicts)} reported-data conflict(s)/restatement(s) were recorded — resolved in favor of the "
            "latest filing; older values may change conclusions at the margin."
        )
    if not invalidate and base is not None:
        invalidate.append("Standard invalidation risks: cost of capital shift, margin erosion, one-off accounting effects.")

    risks_text: list[str] = []
    if risks:
        risks_text.extend(risks.flags)
        risks_text.extend(risks.data_gaps)
        if risks.altman_zone and risks.altman_zone != "safe":
            risks_text.append(f"Altman Z in '{risks.altman_zone}' zone ({risks.altman_z:.2f})" if risks.altman_z else "")
    if health:
        if health.debt_to_ebitda and health.debt_to_ebitda > 4:
            risks_text.append(f"leverage elevated: debt/EBITDA {health.debt_to_ebitda:.1f}x")
        if health.operating_margin is not None and health.operating_margin < 0:
            risks_text.append("operating margin negative in the latest period")
    risks_text = [t for t in risks_text if t]

    return ValuationExplanation(
        company=f"{company_name} ({ticker})",
        headline=headline,
        methodology=methodology,
        models_used=used,
        models_excluded=excluded,
        key_assumptions=key_assumptions,
        missing_data=missing_data,
        what_would_invalidate=invalidate,
        risks=risks_text,
        is_illustrative=is_illustrative,
    )
