"""Financial-health metrics from reported fundamentals."""

from __future__ import annotations

from fairvalue.core.schemas import HealthMetrics, ValuationInputs
from fairvalue.valuation.base import hist_cagr

# Standard tax rate used to derive NOPAT inside ROIC; disclosed in notes because
# tax expense itself is not part of the canonical concept set.
ROIC_TAX_ASSUMPTION = 0.21


def _latest(iv: ValuationInputs, concept: str) -> float | None:
    f = next(
        (p.facts[concept].value for p in reversed(iv.history) if p.facts.get(concept)), None
    )
    return f


def compute_health(iv: ValuationInputs) -> HealthMetrics:
    notes: list[str] = []
    rev = iv.revenue
    gross = _latest(iv, "gross_profit")
    ebit = iv.ebit
    ni = iv.net_income
    equity = iv.book_equity
    fcf = iv.fcf

    gross_margin = gross / rev if gross is not None and rev else None
    op_margin = ebit / rev if ebit is not None and rev else None
    net_margin = ni / rev if ni is not None and rev else None
    fcf_margin = fcf / rev if fcf is not None and rev else None

    roe = ni / equity if ni is not None and equity else None
    if ebit is not None and equity is not None and iv.total_debt is not None:
        invested = equity + iv.total_debt
        if invested > 0:
            roic = (ebit * (1 - ROIC_TAX_ASSUMPTION)) / invested
            notes.append(
                f"ROIC = NOPAT/invested capital with disclosed {ROIC_TAX_ASSUMPTION:.0%} tax assumption "
                "(tax expense is not in the canonical concept set)"
            )
        else:
            roic = None
    else:
        roic = None

    ca = _latest(iv, "current_assets")
    cl = _latest(iv, "current_liabilities")
    current_ratio = ca / cl if ca is not None and cl else None

    ebitda = iv.ebitda
    debt_to_ebitda = (iv.total_debt / ebitda) if iv.total_debt is not None and ebitda else None
    net_debt_to_ebitda = (iv.net_debt / ebitda) if iv.net_debt is not None and ebitda else None
    ocf_to_ni = (iv.operating_cash_flow / ni) if iv.operating_cash_flow is not None and ni else None

    rev_hist = iv.concept_history("revenue")
    rev_cagr_3y = hist_cagr(rev_hist, years_cap=3)

    if debt_to_ebitda is None:
        notes.append("leverage ratios unavailable: total debt and/or EBITDA missing")
    if current_ratio is None:
        notes.append("liquidity ratios unavailable: current assets/liabilities missing")

    return HealthMetrics(
        gross_margin=gross_margin,
        operating_margin=op_margin,
        net_margin=net_margin,
        fcf_margin=fcf_margin,
        roe=roe,
        roic=roic,
        current_ratio=current_ratio,
        debt_to_ebitda=debt_to_ebitda,
        net_debt_to_ebitda=net_debt_to_ebitda,
        interest_coverage=None,  # interest expense is not a canonical concept; never estimated
        ocf_to_net_income=ocf_to_ni,
        revenue_cagr_3y=rev_cagr_3y,
        notes=notes,
    )
