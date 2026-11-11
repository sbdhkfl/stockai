"""Earnings Power Value (Greenwald): growth-free value of normalized earnings.

Normalized earnings = (EBIT - SBC) * (1 - tax) - (maintenance capex - depreciation)
EPV = normalized earnings / cost of capital.
SBC is treated as a real economic expense; maintenance capex substitutes for total
capex to strip growth investment.
"""
import math
from ..errors import FairValueError, NotMeaningfulError


def epv(ebit: float, tax_rate: float, maintenance_capex: float,
        depreciation: float, sbc: float, cost_of_capital: float) -> float:
    if any(not math.isfinite(x) for x in
           (ebit, tax_rate, maintenance_capex, depreciation, sbc, cost_of_capital)):
        raise FairValueError("epv inputs must be finite")
    if not (0.0 <= tax_rate < 1.0):
        raise FairValueError("tax_rate must be in [0, 1)")
    if cost_of_capital <= 0:
        raise FairValueError("cost_of_capital must be > 0")
    normalized = (ebit - sbc) * (1.0 - tax_rate) - (maintenance_capex - depreciation)
    if normalized <= 0:
        raise NotMeaningfulError(
            f"normalized earnings {normalized} <= 0; EPV not meaningful")
    return normalized / cost_of_capital
