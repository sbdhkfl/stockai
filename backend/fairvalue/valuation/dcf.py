"""Two-stage FCFF DCF and the EV <-> equity value bridge.

Formulas (docs/FINANCIAL_METHODOLOGY.md §1):
    PV_explicit = sum FCFF_t / (1+w)^t
    TV          = FCFF_N * (1+g) / (w - g)          [requires 0 <= g < w, FCFF_N > 0]
    EV          = PV_explicit + TV / (1+w)^N
    Equity      = EV - net_debt
"""
from dataclasses import dataclass
import math
from ..errors import FairValueError, NotMeaningfulError, NotSuitableError


@dataclass(frozen=True)
class DCFResult:
    pv_explicit: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    equity_value: float
    value_per_share: float
    discounted_fcff: list


def bridge_ev_to_equity(enterprise_value: float, net_debt: float) -> float:
    """EV minus net debt. Net debt = total debt - cash (+ MI + preferred)."""
    return enterprise_value - net_debt


def dcf_fcff(fcff: list, wacc: float, terminal_growth: float,
             net_debt: float, diluted_shares: float) -> DCFResult:
    if not fcff:
        raise FairValueError("fcff: at least one forecast year is required")
    if any((not math.isfinite(x)) for x in fcff):
        raise FairValueError("fcff: all values must be finite")
    if not (math.isfinite(wacc) and math.isfinite(terminal_growth)
            and math.isfinite(net_debt) and math.isfinite(diluted_shares)):
        raise FairValueError("all DCF inputs must be finite")
    if wacc <= 0:
        raise FairValueError("wacc must be > 0")
    if diluted_shares <= 0:
        raise FairValueError("diluted_shares must be > 0")
    if terminal_growth >= wacc:
        raise FairValueError(
            "terminal_growth must be < wacc (Gordon denominator w-g must be positive)")
    if terminal_growth < 0:
        # Negative perpetual growth is permitted (declining business) but flagged.
        pass

    n = len(fcff)
    discounted = [f / (1.0 + wacc) ** (i + 1) for i, f in enumerate(fcff)]
    pv_explicit = sum(discounted)

    final_fcff = fcff[-1]
    if final_fcff <= 0:
        raise NotMeaningfulError(
            "terminal value refused: final explicit-year FCFF is <= 0; "
            "extend the explicit horizon or use another model")
    terminal_value = final_fcff * (1.0 + terminal_growth) / (wacc - terminal_growth)
    pv_tv = terminal_value / (1.0 + wacc) ** n
    ev = pv_explicit + pv_tv
    equity = bridge_ev_to_equity(ev, net_debt)
    return DCFResult(
        pv_explicit=pv_explicit, terminal_value=terminal_value, pv_terminal_value=pv_tv,
        enterprise_value=ev, equity_value=equity,
        value_per_share=equity / diluted_shares, discounted_fcff=discounted)


def check_dcf_suitability(sector: str) -> None:
    """Financial institutions: interest is operating, FCFF is ill-defined."""
    if sector in ("banking", "insurance"):
        raise NotSuitableError(
            f"DCF(FCFF) is not suitable for {sector}: use residual income or DDM")


# ---------------------------------------------------------------------------
# Contract adapter (docs/ARCHITECTURE.md §3): ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, DcfAssumptions, ModelResult


def _historical_ratio(history, numerator, denominator, default=None):
    """Average of numerator/denominator over available periods (None-safe)."""
    ratios = []
    for p in history:
        n, d = p.facts.get(numerator), p.facts.get(denominator)
        if n and d and d.value != 0:
            ratios.append(n.value / d.value)
    return sum(ratios) / len(ratios) if ratios else default


def run_model(inputs: ValuationInputs, a: DcfAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    latest = inputs.history[-1] if inputs.history else None
    if not latest or "revenue" not in latest.facts:
        return ModelResult(model="dcf", applicable=False,
                           excluded_reason="no revenue history; cannot project FCFF", **base)
    if not inputs.shares_outstanding:
        return ModelResult(model="dcf", applicable=False,
                           excluded_reason="shares outstanding missing", **base)
    warnings = []
    rev0 = latest.facts["revenue"].value
    margin = a.target_operating_margin
    if margin is None:
        ebit = latest.facts.get("ebit")
        if not ebit:
            return ModelResult(model="dcf", applicable=False,
                               excluded_reason="no EBIT to establish operating margin", **base)
        margin = ebit.value / rev0
    da_pct = a.depreciation_pct_revenue
    if da_pct is None:
        da_pct = _historical_ratio(inputs.history, "depreciation_amortization", "revenue", 0.0)
    capex_pct = a.capex_pct_revenue
    if capex_pct is None:
        capex_pct = _historical_ratio(inputs.history, "capex", "revenue", 0.0)
        if capex_pct == 0.0:
            warnings.append("no capex history available; capex assumed 0 — understates "
                            "FCFF, treat result as an upper bound")

    rev, fcff = rev0, []
    for _ in range(a.forecast_years):
        rev_new = rev * (1.0 + a.revenue_growth)
        ebit_t = rev_new * margin
        nwc_change = a.nwc_pct_revenue_change * (rev_new - rev)
        fcff.append(ebit_t * (1.0 - a.tax_rate) + rev_new * da_pct
                    - rev_new * capex_pct - nwc_change)
        rev = rev_new

    n = a.forecast_years
    if a.terminal_method == "gordon":
        tv = fcff[-1] * (1.0 + a.terminal_growth) / (a.wacc - a.terminal_growth)
        tv_desc = f"Gordon: FCFF_n*(1+{a.terminal_growth})/({a.wacc}-{a.terminal_growth})"
    else:
        ebitda_n = rev * (margin + da_pct)
        tv = ebitda_n * a.exit_ev_ebitda
        tv_desc = f"exit multiple: EBITDA_n {ebitda_n:,.0f} x {a.exit_ev_ebitda}x"
    pv_explicit = sum(f / (1 + a.wacc) ** t for t, f in enumerate(fcff, 1))
    pv_tv = tv / (1 + a.wacc) ** n
    ev = pv_explicit + pv_tv
    equity = ev - (inputs.net_debt or 0.0)
    shares_n = inputs.shares_outstanding * (1.0 + a.annual_share_growth) ** n
    if equity <= 0:
        warnings.append("equity value <= 0 at these assumptions")
    if fcff[-1] <= 0 and a.terminal_method == "gordon":
        warnings.append("final-year FCFF <= 0: Gordon terminal value is not meaningful")
    steps = [f"revenue path from {rev0:,.0f} at {a.revenue_growth:.1%}/yr for {n}y",
             f"operating margin {margin:.1%}, tax {a.tax_rate:.0%}, "
             f"D&A {da_pct:.1%} and capex {capex_pct:.1%} of revenue, "
             f"dNWC {a.nwc_pct_revenue_change:.0%} of revenue change",
             f"PV explicit = {pv_explicit:,.0f}; terminal value {tv_desc} = {tv:,.0f}, "
             f"PV = {pv_tv:,.0f}",
             f"EV = {ev:,.0f}; equity = EV - net debt = {equity:,.0f}",
             f"per share = {equity:,.0f} / {shares_n:,.0f} (dilution "
             f"{a.annual_share_growth:.1%}/yr)"]
    return ModelResult(model="dcf", applicable=True,
                       value_per_share=equity / shares_n,
                       enterprise_value=ev, equity_value=equity,
                       **base,
                       formula="FCFF_t = EBIT*(1-t)+D&A-capex-dNWC; EV = sum PV(FCFF) + PV(TV); equity = EV - net debt",
                       steps=steps, warnings=warnings,
                       limitations=["unsuitable for banks/insurers (interest is operating)",
                                    "Gordon terminal value dominates when horizon is short"])
