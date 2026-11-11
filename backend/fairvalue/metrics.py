"""Financial metrics. Every result carries the formula used (explainability rule).

Conventions:
- 'average' denominators use (begin+end)/2 when both are supplied; otherwise the
  end balance with a `end_balance_proxy` flag.
- Non-meaningful cases raise NotMeaningfulError rather than returning junk.
"""
from dataclasses import dataclass, field
import math
from .errors import FairValueError, NotMeaningfulError


def _avg(end: float, begin: float = None):
    if begin is not None and math.isfinite(begin):
        return (end + begin) / 2.0, []
    return end, ["end_balance_proxy"]


def _finite(*xs):
    if any((x is None) or (not math.isfinite(x)) for x in xs):
        raise FairValueError("all metric inputs must be finite and present")


@dataclass(frozen=True)
class Metric:
    name: str
    value: float
    formula: str
    flags: list = field(default_factory=list)


def _m(name, value, formula, flags=None):
    return Metric(name, value, formula, flags or [])


# ---------- profitability ----------

def gross_margin(revenue: float, cogs: float) -> Metric:
    _finite(revenue, cogs)
    if revenue == 0:
        raise NotMeaningfulError("revenue is zero")
    return _m("gross_margin", (revenue - cogs) / revenue, "(revenue - cogs) / revenue")


def operating_margin(operating_income: float, revenue: float) -> Metric:
    _finite(operating_income, revenue)
    if revenue == 0:
        raise NotMeaningfulError("revenue is zero")
    return _m("operating_margin", operating_income / revenue, "operating_income / revenue")


def net_margin(net_income: float, revenue: float) -> Metric:
    _finite(net_income, revenue)
    if revenue == 0:
        raise NotMeaningfulError("revenue is zero")
    return _m("net_margin", net_income / revenue, "net_income / revenue")


def roa(net_income: float, total_assets_end: float, total_assets_begin: float = None) -> Metric:
    _finite(net_income, total_assets_end)
    den, flags = _avg(total_assets_end, total_assets_begin)
    if den == 0:
        raise NotMeaningfulError("average total assets is zero")
    return _m("roa", net_income / den, "net_income / avg(total_assets)", flags)


def roe(net_income: float, equity_end: float, equity_begin: float = None) -> Metric:
    _finite(net_income, equity_end)
    den, flags = _avg(equity_end, equity_begin)
    if den <= 0:
        raise NotMeaningfulError("average equity <= 0: ROE not meaningful")
    return _m("roe", net_income / den, "net_income / avg(equity)", flags)


def roic(ebit: float, tax_rate: float, debt: float, equity: float, cash: float,
         debt_begin: float = None, equity_begin: float = None,
         cash_begin: float = None) -> Metric:
    """NOPAT / invested capital; IC = debt + equity - cash (averaged when possible)."""
    _finite(ebit, tax_rate, debt, equity, cash)
    if not (0.0 <= tax_rate < 1.0):
        raise FairValueError("tax_rate must be in [0, 1)")
    ic_end, ic_begin = debt + equity - cash, None
    if None not in (debt_begin, equity_begin, cash_begin):
        ic_begin = debt_begin + equity_begin - cash_begin
    den, flags = _avg(ic_end, ic_begin)
    if den <= 0:
        raise NotMeaningfulError("invested capital <= 0: ROIC not meaningful")
    nopat = ebit * (1.0 - tax_rate)
    return _m("roic", nopat / den, "EBIT*(1-t) / (debt + equity - cash)", flags)


# ---------- liquidity ----------

def current_ratio(current_assets: float, current_liabilities: float) -> Metric:
    _finite(current_assets, current_liabilities)
    if current_liabilities <= 0:
        raise NotMeaningfulError("current liabilities <= 0")
    return _m("current_ratio", current_assets / current_liabilities,
              "current_assets / current_liabilities")


def quick_ratio(current_assets: float, inventory: float,
                current_liabilities: float) -> Metric:
    _finite(current_assets, inventory, current_liabilities)
    if current_liabilities <= 0:
        raise NotMeaningfulError("current liabilities <= 0")
    return _m("quick_ratio", (current_assets - inventory) / current_liabilities,
              "(current_assets - inventory) / current_liabilities")


def cash_ratio(cash: float, current_liabilities: float) -> Metric:
    _finite(cash, current_liabilities)
    if current_liabilities <= 0:
        raise NotMeaningfulError("current liabilities <= 0")
    return _m("cash_ratio", cash / current_liabilities, "cash / current_liabilities")


# ---------- solvency ----------

def debt_to_equity(total_debt: float, total_equity: float) -> Metric:
    _finite(total_debt, total_equity)
    if total_equity <= 0:
        raise NotMeaningfulError("equity <= 0: D/E not meaningful")
    return _m("debt_to_equity", total_debt / total_equity, "total_debt / total_equity")


def net_debt_to_ebitda(net_debt: float, ebitda: float) -> Metric:
    _finite(net_debt, ebitda)
    if ebitda <= 0:
        raise NotMeaningfulError("EBITDA <= 0: net debt/EBITDA not meaningful")
    return _m("net_debt_to_ebitda", net_debt / ebitda, "net_debt / ebitda")


def interest_coverage(ebit: float, interest_expense: float) -> Metric:
    _finite(ebit, interest_expense)
    if interest_expense <= 0:
        raise NotMeaningfulError("interest expense <= 0: coverage not meaningful")
    if ebit <= 0:
        raise NotMeaningfulError("EBIT <= 0: coverage not meaningful (cannot service debt)")
    return _m("interest_coverage", ebit / interest_expense, "ebit / interest_expense")


def debt_maturity_share(debt_maturities: dict, horizon_years: float) -> Metric:
    """debt_maturities: {year: amount}. Share of total debt due within horizon."""
    _finite(horizon_years)
    if horizon_years <= 0:
        raise FairValueError("horizon_years must be > 0")
    total = sum(debt_maturities.values())
    if total <= 0:
        raise NotMeaningfulError("no debt maturities provided")
    due = sum(v for y, v in debt_maturities.items() if y <= horizon_years)
    return _m("debt_maturity_share", due / total,
              f"debt due <= {horizon_years}y / total debt")


# ---------- efficiency ----------

def asset_turnover(revenue: float, total_assets_end: float,
                   total_assets_begin: float = None) -> Metric:
    _finite(revenue, total_assets_end)
    den, flags = _avg(total_assets_end, total_assets_begin)
    if den == 0:
        raise NotMeaningfulError("average total assets is zero")
    return _m("asset_turnover", revenue / den, "revenue / avg(total_assets)", flags)


def inventory_turnover(cogs: float, inventory_end: float,
                       inventory_begin: float = None) -> Metric:
    _finite(cogs, inventory_end)
    den, flags = _avg(inventory_end, inventory_begin)
    if den == 0:
        raise NotMeaningfulError("average inventory is zero")
    return _m("inventory_turnover", cogs / den, "cogs / avg(inventory)", flags)


def receivables_turnover(revenue: float, receivables_end: float,
                         receivables_begin: float = None) -> Metric:
    _finite(revenue, receivables_end)
    den, flags = _avg(receivables_end, receivables_begin)
    if den == 0:
        raise NotMeaningfulError("average receivables is zero")
    return _m("receivables_turnover", revenue / den, "revenue / avg(receivables)", flags)


# ---------- growth ----------

def cagr(end_value: float, begin_value: float, years: float) -> Metric:
    _finite(end_value, begin_value, years)
    if years <= 0:
        raise FairValueError("years must be > 0")
    if begin_value <= 0 or end_value <= 0:
        raise NotMeaningfulError("CAGR requires positive begin and end values "
                                 "(sign changes are not growth)")
    return _m("cagr", (end_value / begin_value) ** (1.0 / years) - 1.0,
              "(end/begin)^(1/years) - 1")


# ---------- valuation ratios ----------

def pe_ratio(price: float, eps_diluted: float) -> Metric:
    _finite(price, eps_diluted)
    if eps_diluted <= 0:
        raise NotMeaningfulError("EPS <= 0: P/E not meaningful")
    if price <= 0:
        raise NotMeaningfulError("price <= 0")
    return _m("pe_ratio", price / eps_diluted, "price / diluted_eps")


def pb_ratio(price: float, book_value_per_share: float) -> Metric:
    _finite(price, book_value_per_share)
    if book_value_per_share <= 0:
        raise NotMeaningfulError("BVPS <= 0: P/B not meaningful")
    return _m("pb_ratio", price / book_value_per_share, "price / bvps")


def ev_ebitda(ev: float, ebitda: float) -> Metric:
    _finite(ev, ebitda)
    if ebitda <= 0:
        raise NotMeaningfulError("EBITDA <= 0: EV/EBITDA not meaningful")
    return _m("ev_ebitda", ev / ebitda, "ev / ebitda")


def ev_sales(ev: float, revenue: float) -> Metric:
    _finite(ev, revenue)
    if revenue <= 0:
        raise NotMeaningfulError("revenue <= 0")
    return _m("ev_sales", ev / revenue, "ev / revenue")


def fcf_yield(fcf: float, market_cap: float) -> Metric:
    _finite(fcf, market_cap)
    if market_cap <= 0:
        raise NotMeaningfulError("market cap <= 0")
    return _m("fcf_yield", fcf / market_cap, "fcf / market_cap")
