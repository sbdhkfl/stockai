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
