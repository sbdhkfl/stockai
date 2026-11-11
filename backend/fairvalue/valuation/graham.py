"""Graham-style valuation.

Revised Graham formula: V = EPS * (8.5 + 2*g) * 4.4 / Y
where g = expected 7-10y growth in percent points (capped at 15 here; the formula
degrades empirically for high-growth names) and Y = current AAA corporate yield in
percent (Graham's 1962-era baseline was 4.4).
Graham Number: sqrt(22.5 * EPS * BVPS) — a defensive floor, not a fair value.
"""
import math
from ..errors import FairValueError, NotMeaningfulError


def graham_value(eps: float, growth_pct: float, aaa_yield_pct: float = 4.4) -> float:
    if any(not math.isfinite(x) for x in (eps, growth_pct, aaa_yield_pct)):
        raise FairValueError("graham inputs must be finite")
    if eps <= 0:
        raise NotMeaningfulError("negative or zero EPS: Graham formula not meaningful")
    if aaa_yield_pct <= 0:
        raise FairValueError("aaa_yield_pct must be > 0")
    g = max(0.0, min(15.0, growth_pct))  # documented clamp
    return eps * (8.5 + 2.0 * g) * 4.4 / aaa_yield_pct


def graham_number(eps: float, book_value_per_share: float) -> float:
    if eps <= 0 or book_value_per_share <= 0:
        raise NotMeaningfulError("Graham number requires positive EPS and BVPS")
    return math.sqrt(22.5 * eps * book_value_per_share)


# ---------------------------------------------------------------------------
# Contract adapter: ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, GrahamAssumptions, ModelResult


def run_model(inputs: ValuationInputs, a: GrahamAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    latest = inputs.history[-1] if inputs.history else None
    eps = inputs.eps or (latest.facts.get("eps_diluted").value
                         if latest and "eps_diluted" in latest.facts else None)
    if not eps or eps <= 0:
        return ModelResult(model="graham", applicable=False,
                           excluded_reason="positive diluted EPS required", **base)
    warnings = []
    g = a.growth_rate
    if g is None:
        hist = inputs.concept_history("eps_diluted")
        if len(hist) >= 2 and hist[0].value > 0:
            years = len(hist) - 1
            g = (hist[-1].value / hist[0].value) ** (1.0 / years) - 1.0
            warnings.append(f"g derived from {years}y EPS history: {g:.1%}")
        else:
            return ModelResult(model="graham", applicable=False,
                               excluded_reason="growth_rate missing and not derivable",
                               **base)
    g_pct = max(0.0, min(15.0, g * 100.0))
    v = graham_value(eps, g_pct, 4.4)  # 4.4 = Graham's baseline AAA yield; documented
    if a.quality_required:
        if inputs.total_liabilities and inputs.total_assets and \
                inputs.total_liabilities > inputs.total_assets:
            warnings.append("fails defensive screen: liabilities exceed assets")
        if inputs.total_assets and (inputs.total_assets and inputs.book_equity or 0) <= 0:
            warnings.append("fails defensive screen: non-positive book equity")
    steps = [f"EPS = {eps:.2f}; g = {g_pct:.1f}% (clamped to [0, 15]); Y = 4.4",
             f"V = EPS x (8.5 + 2g) x 4.4 / Y = {v:.2f}"]
    return ModelResult(model="graham", applicable=True, value_per_share=v,
                       equity_value=None, **base,
                       formula="V = EPS x (8.5 + 2g) x 4.4 / Y (Graham 1962-73 revision)",
                       steps=steps, warnings=warnings,
                       limitations=["empirical 1962 formula; growth clamped at 15",
                                    "uses fixed 4.4 AAA baseline yield, not current market yield"])
