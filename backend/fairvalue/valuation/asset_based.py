"""Asset-Based Valuation — adjusted balance-sheet (net asset) value.

Formula
-------
Equity = (total assets + asset adjustments) − (total liabilities + liability adjustments)
value/share = Equity / shares
"""

from __future__ import annotations

from fairvalue.core.schemas import AssetBasedAssumptions, ModelResult, ValuationInputs
from fairvalue.valuation.base import not_applicable

MODEL = "asset_based"

LIMITATIONS = [
    "Book values are historical cost, not market value — land, brands and proprietary technology are often mispriced by the ledger.",
    "Intangible-heavy firms (software, pharma) carry assets the balance sheet never recorded.",
    "Liquidation values differ from going-concern book equity; this is a floor-style estimate, not a business value.",
]


def calculate(iv: ValuationInputs, a: AssetBasedAssumptions) -> ModelResult:
    if iv.total_assets is None or iv.total_liabilities is None:
        return not_applicable(MODEL, "total assets and/or total liabilities missing from balance sheet")
    if not iv.shares_outstanding:
        return not_applicable(MODEL, "shares outstanding missing")

    assets = iv.total_assets + a.asset_adjustments
    liabs = iv.total_liabilities + a.liability_adjustments
    equity = assets - liabs
    value = equity / float(iv.shares_outstanding)

    steps = [
        f"Total assets {iv.total_assets:,.0f}"
        + (f" + adjustments {a.asset_adjustments:,.0f}" if a.asset_adjustments else ""),
        f"Total liabilities {iv.total_liabilities:,.0f}"
        + (f" + adjustments {a.liability_adjustments:,.0f}" if a.liability_adjustments else ""),
        f"Equity = {assets:,.0f} − {liabs:,.0f} = {equity:,.0f} ÷ {iv.shares_outstanding:,.0f} = {value:,.2f}/share",
    ]

    warnings = []
    if equity <= 0:
        warnings.append("adjusted net assets are non-positive — book equity is wiped out")
    if iv.revenue and iv.total_assets / iv.revenue < 1.5:
        warnings.append(
            "asset-light business (assets < 1.5× revenue): balance-sheet value ignores the franchise that earns the profit"
        )
    if iv.book_equity is not None and abs(iv.book_equity - equity) > 1:
        steps.append(f"Reported book equity on file: {iv.book_equity:,.0f} (consistency check vs computed {equity:,.0f})")

    asset_intensity = (iv.total_assets / iv.revenue) if iv.revenue else 0.0
    suitability = 0.7 if asset_intensity >= 1.5 else 0.35

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        equity_value=equity,
        confidence="medium" if asset_intensity >= 1.5 else "low",
        suitability=suitability,
        assumptions=a.model_dump(),
        formula="equity = (assets + adjustments) − (liabilities + adjustments); value/share = equity / shares",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
