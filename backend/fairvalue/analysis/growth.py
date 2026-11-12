"""Growth analysis — historical CAGRs from reported data only.

Estimates (analyst or management) are only reported when a feed provides them;
this module never generates them.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import gmean

from fairvalue.core.schemas import GrowthAnalysis, ValuationInputs


def _cagr(points: list[float]) -> float | None:
    """CAGR computed as the geometric mean of period growth rates.

    Needs every period-over-period growth to be defined (>0 base values);
    mixed-sign series (losses) return None instead of a misleading number.
    """
    arr = np.asarray(points, dtype=float)
    if arr.size < 3 or (arr <= 0).any():
        return None
    period_growth = arr[1:] / arr[:-1] - 1.0
    if (period_growth <= -1.0).any():
        return None
    return float(gmean(1.0 + period_growth) - 1.0)


def compute_growth(iv: ValuationInputs) -> GrowthAnalysis:
    notes: list[str] = []
    revenue = [f.value for f in iv.concept_history("revenue")]
    net_income = [f.value for f in iv.concept_history("net_income")]
    eps = [f.value for f in iv.concept_history("eps_diluted")]
    fcf = [f.value for f in iv.concept_history("operating_cash_flow")]

    rev_cagr = _cagr(revenue) if len(revenue) >= 3 else None
    rev_cagr_3y = _cagr(revenue[-4:]) if len(revenue) >= 3 else None
    ni_cagr = _cagr(net_income)
    eps_cagr = _cagr(eps)
    fcf_cagr = _cagr(fcf)

    if len(revenue) < 3:
        notes.append("fewer than 3 reported revenue periods — CAGRs withheld")
    if ni_cagr is None and net_income:
        notes.append("net income CAGR undefined (loss years or insufficient history)")
    if fcf_cagr is None and fcf:
        notes.append("operating cash flow CAGR undefined (negative years or insufficient history)")
    notes.append("no analyst estimates configured: forward growth is not inferred from history")

    return GrowthAnalysis(
        revenue_cagr=_cagr(revenue) if len(revenue) >= 4 else None,
        revenue_cagr_3y=rev_cagr_3y if rev_cagr_3y is not None else rev_cagr,
        net_income_cagr=ni_cagr,
        eps_cagr=eps_cagr,
        fcf_cagr=fcf_cagr,
        estimates_available=False,
        notes=notes,
    )
