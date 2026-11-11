"""Risk analysis: Altman Z-score (with applicability enforcement) and
deterministic leverage/liquidity/volatility flags.

Historical volatility is NOT a complete measure of business risk; outputs are
screens, not calibrated probabilities (docs/RISK_METHODOLOGY.md).
"""
from dataclasses import dataclass
import math
from .errors import FairValueError, NotSuitableError

Z_SAFE, Z_DISTRESS = 2.99, 1.81


@dataclass(frozen=True)
class AltmanResult:
    z: float
    zone: str            # safe | grey | distress
    warnings: list


def altman_z(working_capital: float, total_assets: float, retained_earnings: float,
             ebit: float, market_equity: float, total_liabilities: float,
             sales: float, sector: str = "manufacturing",
             variant: str = "public") -> AltmanResult:
    """Original 1968/2000 public-manufacturing weights only. variant must be
    'public' (this engine does not silently substitute Z'/Z'' weights)."""
    if variant != "public":
        raise FairValueError("only the public-firm Z weights are implemented; "
                             "Z'/Z'' must be requested explicitly when implemented")
    if sector in ("banking", "insurance", "reit"):
        raise NotSuitableError(
            f"Altman Z is not appropriate for {sector} (capital structure and "
            "reserve mechanics distort the ratios); use sector distress models")
    vals = [working_capital, total_assets, retained_earnings, ebit,
            market_equity, total_liabilities, sales]
    if any(not math.isfinite(x) for x in vals):
        raise FairValueError("altman inputs must be finite")
    if total_assets <= 0 or total_liabilities <= 0:
        raise FairValueError("total_assets and total_liabilities must be > 0")

    z = (1.2 * working_capital / total_assets
         + 1.4 * retained_earnings / total_assets
         + 3.3 * ebit / total_assets
         + 0.6 * market_equity / total_liabilities
         + 1.0 * sales / total_assets)
    warnings = ["weights fitted to public manufacturing firms (1968/2000); "
                "screening statistic, not a bankruptcy probability"]
    if sector != "manufacturing":
        warnings.append(f"non-manufacturing sector '{sector}': interpret with caution")
    zone = "safe" if z > Z_SAFE else ("distress" if z < Z_DISTRESS else "grey")
    return AltmanResult(z=z, zone=zone, warnings=warnings)


def leverage_flags(interest_coverage: float = None, net_debt_ebitda: float = None,
                   current_ratio: float = None, revenue_history: list = None,
                   ocf_history: list = None) -> list:
    """Deterministic risk flags. Missing inputs are reported as gaps, not zero."""
    flags, gaps = [], []
    if interest_coverage is not None and interest_coverage < 2.0:
        flags.append("leverage_risk: interest coverage < 2.0")
    if net_debt_ebitda is not None and net_debt_ebitda > 4.0:
        flags.append("leverage_risk: net debt/EBITDA > 4.0")
    if current_ratio is not None and current_ratio < 1.0:
        flags.append("liquidity_risk: current ratio < 1.0")
    if revenue_history is not None and len(revenue_history) >= 5:
        mean = sum(revenue_history) / len(revenue_history)
        if mean != 0:
            cv = math.sqrt(sum((x - mean) ** 2 for x in revenue_history)
                           / len(revenue_history)) / abs(mean)
            if cv > 0.35:
                flags.append(f"earnings_volatility: revenue CV {cv:.2f} > 0.35")
    else:
        gaps.append("revenue_history needs >= 5 years for volatility check")
    if ocf_history is not None and len(ocf_history) >= 3:
        if sum(1 for x in ocf_history[-3:] if x < 0) >= 2:
            flags.append("cash_flow_instability: negative OCF in >=2 of last 3 years")
    else:
        gaps.append("ocf_history needs >= 3 years for cash-flow check")
    return {"flags": flags, "data_gaps": gaps}
