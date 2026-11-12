"""Risk assessment: distress screening, leverage, cash-flow resilience.

Altman Z-score (original, 1968):
    Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5
    X1 = working capital / total assets
    X2 = retained earnings / total assets
    X3 = EBIT / total assets
    X4 = market value of equity / total liabilities  (book equity substituted
         ONLY when no price exists — always disclosed in notes)
    X5 = sales / total assets
Calibration note: the original model targets manufacturers; for other sectors
the score is a relative indicator, not a probability (stated in limitations).
"""

from __future__ import annotations

from fairvalue.core.schemas import RiskAssessment, ValuationInputs


def compute_risks(iv: ValuationInputs) -> RiskAssessment:
    flags: list[str] = []
    gaps: list[str] = []
    leverage_notes: list[str] = []

    p = iv.history[-1] if iv.history else None
    get = lambda c: (p.facts[c].value if p and p.facts.get(c) else None)  # noqa: E731

    ta, tl = get("total_assets"), get("total_liabilities")
    re_ = get("retained_earnings")
    wc = (get("current_assets") or 0) - (get("current_liabilities") or 0)
    sales = get("revenue")

    altman = None
    zone = None
    if ta and tl:
        if iv.price is not None and iv.shares_outstanding:
            x4 = (iv.price * iv.shares_outstanding) / tl
            x4_note = None
        else:
            eq = get("equity")
            x4 = eq / tl if eq is not None else None
            x4_note = "market value unavailable — X4 uses book equity (score then understates listed-equity cushion)"
        if iv.ebit is not None and sales and re_ is not None and x4 is not None:
            altman = 1.2 * (wc / ta) + 1.4 * (re_ / ta) + 3.3 * (iv.ebit / ta) + 0.6 * x4 + 1.0 * (sales / ta)
            zone = "safe" if altman > 2.99 else ("grey" if altman > 1.81 else "distress")
            if x4_note:
                leverage_notes.append(x4_note)
            if zone == "grey":
                flags.append(f"Altman Z {altman:.2f} in the grey zone (1.81–2.99)")
            if zone == "distress":
                flags.append(f"Altman Z {altman:.2f} in the distress zone (<1.81)")
        else:
            gaps.append("Altman Z incomplete: retained earnings or EBIT missing")
    else:
        gaps.append("Altman Z incomplete: total assets/liabilities missing")

    ebitda = iv.ebitda
    if iv.net_debt is not None and ebitda:
        if iv.net_debt / ebitda > 4:
            flags.append(f"net debt/EBITDA {iv.net_debt / ebitda:.1f}x is elevated (>4x)")
        leverage_notes.append(f"net debt/EBITDA {iv.net_debt / ebitda:.1f}x")
    else:
        gaps.append("leverage ratio unavailable (net debt and/or EBITDA missing)")

    coverage = None
    leverage_notes.append(
        "interest coverage not computed: interest expense is not part of the canonical concept set"
    )

    streak = 0
    for period in reversed(iv.history):
        fcf_p = None
        ocf, capex = period.facts.get("operating_cash_flow"), period.facts.get("capex")
        if ocf and capex:
            fcf_p = ocf.value - capex.value
        if fcf_p is None:
            break
        if fcf_p < 0:
            streak += 1
        else:
            break
    if streak:
        flags.append(f"free cash flow negative for {streak} consecutive reported year(s)")
    if iv.book_equity is not None and iv.book_equity <= 0:
        flags.append("book equity is non-positive")

    return RiskAssessment(
        altman_z=altman,
        altman_zone=zone,
        leverage_notes=leverage_notes,
        interest_coverage=coverage,
        consecutive_fcf_negative=streak,
        flags=flags,
        data_gaps=gaps,
    )
