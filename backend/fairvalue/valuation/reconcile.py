"""Model selection & reconciliation layer (Lead Architect owned).

Policy (ARCHITECTURE.md §4.4 — "do not blindly average incompatible models"):
1. applicability — models without required data are excluded with a reason;
2. family grouping — income-based vs market-based vs asset-based estimates are
   first aggregated *within* their family (suitability-weighted mean), because
   models in a family share assumptions and failure modes;
3. cross-family base — the reported base is the median of family values, so no
   single family can dominate; low/high are the span of all applicable models;
4. every weight, exclusion and family aggregate is written into the report.
"""

from __future__ import annotations

from statistics import median

from fairvalue.core.schemas import ExcludedModel, ModelResult, Reconciliation

MODEL_FAMILIES: dict[str, tuple[str, ...]] = {
    "income": ("dcf", "ddm", "residual_income", "epv", "graham"),
    "market": ("comparables", "precedents"),
    "asset": ("asset_based", "sotp"),
}

FAMILY_LABELS = {
    "income": "income-based (discounted future earnings/dividends)",
    "market": "market-based (peer and transaction multiples)",
    "asset": "asset-based (balance-sheet value)",
}


def reconcile(results: list[ModelResult]) -> Reconciliation:
    included = [r for r in results if r.applicable and r.value_per_share is not None]
    excluded = [
        ExcludedModel(model=r.model, reason=r.excluded_reason or "not applicable")
        for r in results
        if not (r.applicable and r.value_per_share is not None)
    ]

    family_values: dict[str, float] = {}
    notes: list[str] = []
    for fam, members in MODEL_FAMILIES.items():
        vals = [r for r in included if r.model in members]
        if not vals:
            continue
        weights = [max(r.suitability, 1e-6) for r in vals]
        total_w = sum(weights)
        agg = sum(r.value_per_share * w for r, w in zip(vals, weights)) / total_w  # suitability-weighted mean
        family_values[fam] = agg
        notes.append(
            f"{FAMILY_LABELS[fam]}: weighted mean of "
            + ", ".join(f"{r.model} {r.value_per_share:,.2f} (w={r.suitability:.2f})" for r in vals)
            + f" = {agg:,.2f}"
        )

    if not included:
        return Reconciliation(
            excluded=excluded,
            method="no model applicable — no valuation range produced",
            notes=["all models reported explicit missing-data exclusions; nothing was estimated in their place"],
        )

    values = [float(r.value_per_share) for r in included]
    base = float(median(list(family_values.values()))) if family_values else float(median(values))
    low, high = min(values), max(values)

    if len(family_values) >= 2:
        method = (
            "base = median of family aggregates (income/market/asset); "
            "low/high = min/max of all applicable models"
        )
        fam_spread = max(family_values.values()) - min(family_values.values())
        if fam_spread > 0.25 * base:
            notes.append(
                f"families disagree by {fam_spread:,.2f} ({fam_spread / base:.0%} of base) — "
                "market pricing and intrinsic models are telling different stories; treat the range width as signal"
            )
    else:
        only = next(iter(family_values))
        method = f"single family available ({only}): base = family aggregate; low/high = min/max of its models"
        notes.append("only one model family produced values — the range reflects intra-family disagreement only")

    return Reconciliation(
        included=[r.model for r in included],
        excluded=excluded,
        family_values=family_values,
        low=low,
        base=base,
        high=high,
        method=method,
        notes=notes,
    )
