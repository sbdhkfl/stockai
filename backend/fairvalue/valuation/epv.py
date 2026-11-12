"""Earnings Power Value (EPV, Palepu–Higgins style) — no-growth value of
current sustainable earnings, then − net debt.

Formula
-------
NOPAT = normalized EBIT · (1 − tax)
EV    = NOPAT / WACC                (perpetuity of current earnings power)
Equity = EV − net debt ; value/share = Equity / shares
"""

from __future__ import annotations

from fairvalue.core.schemas import EpvAssumptions, ModelResult, ValuationInputs
from fairvalue.valuation.base import not_applicable

MODEL = "epv"

LIMITATIONS = [
    "Gives NO credit for growth or for the returns on reinvested capital — systematically below DCF for growth firms.",
    "'Normalized' earnings are judged from history: one-cycle businesses need judgment the data cannot supply.",
    "Assumes maintenance capex ≈ D&A and that current margins are sustainable.",
]


def calculate(iv: ValuationInputs, a: EpvAssumptions) -> ModelResult:
    if iv.ebit is None:
        return not_applicable(MODEL, "ebit missing from latest reported period")
    if not iv.shares_outstanding or iv.net_debt is None:
        return not_applicable(MODEL, "shares outstanding or net debt missing")

    ebit_hist = [p.facts["ebit"].value for p in iv.history if p.facts.get("ebit")]
    rev_hist = [(p.facts["ebit"].value / p.facts["revenue"].value)
                for p in iv.history
                if p.facts.get("ebit") and p.facts.get("revenue") and p.facts["revenue"].value > 0]

    if a.margin_normalization == "historical_average" and rev_hist:
        margin = sum(rev_hist) / len(rev_hist)
        ebit_norm = margin * iv.revenue if iv.revenue else None
        basis = f"avg operating margin {margin:.1%} × revenue {iv.revenue:,.0f}" if ebit_norm else None
    else:
        ebit_norm = iv.ebit
        basis = f"latest reported EBIT {iv.ebit:,.0f}"
    if ebit_norm is None:
        return not_applicable(MODEL, "cannot normalize earnings: EBIT history unavailable")

    if ebit_norm <= 0:
        return not_applicable(MODEL, "normalized EBIT non-positive — earnings power is negative")

    nopat = ebit_norm * (1 - a.tax_rate)
    ev = nopat / a.wacc
    equity = ev - iv.net_debt
    value = equity / float(iv.shares_outstanding)

    steps = [
        f"Normalized EBIT via {basis} = {ebit_norm:,.0f}",
        f"NOPAT = {ebit_norm:,.0f} × (1 − {a.tax_rate:.0%}) = {nopat:,.0f}",
        f"EV = NOPAT / WACC = {nopat:,.0f} / {a.wacc:.2%} = {ev:,.0f} (zero-growth perpetuity)",
        f"equity = {ev:,.0f} − net debt {iv.net_debt:,.0f} = {equity:,.0f} ÷ "
        f"{iv.shares_outstanding:,.0f} = {value:,.2f}/share",
    ]
    if iv.price:
        steps.append("EPV intentionally excludes growth: a result below a growth firm's price is expected, not an error")

    warnings = []
    capex_rates = [p.facts["capex"].value / p.facts["revenue"].value
                   for p in iv.history
                   if p.facts.get("capex") and p.facts.get("revenue") and p.facts["revenue"].value > 0]
    da_rates = [p.facts["depreciation_amortization"].value / p.facts["revenue"].value
                for p in iv.history
                if p.facts.get("depreciation_amortization") and p.facts.get("revenue") and p.facts["revenue"].value > 0]
    if capex_rates and da_rates and (sum(capex_rates) / len(capex_rates)) > 1.3 * (sum(da_rates) / len(da_rates)):
        warnings.append("capex runs >130% of D&A: the business is expanding — EPV of current earnings understates a growing firm")

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        enterprise_value=ev,
        equity_value=equity,
        confidence="medium",
        suitability=0.75 if len(rev_hist) >= 3 else 0.55,
        assumptions=a.model_dump(),
        formula="EV = normalized NOPAT / WACC; equity = EV − net debt",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
