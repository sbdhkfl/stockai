"""Shared audit fixtures for the `calculate()` model surface.

Every expected value in the test suite is independently hand-derived (see
docs/QUANTITATIVE_TESTING.md and inline derivations). None are taken from the
engine's own intermediates.
"""
from datetime import date, datetime, timezone

from fairvalue.core.schemas import (
    CompanyProfile, Fact, PeriodFinancials, SourceRef, ValuationInputs,
    ComparableCompany, PrecedentTransaction, Segment, MarketData,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _src():
    return SourceRef(provider="audit", retrieved_at=NOW)


def _fact(concept, value, fy=2025):
    return Fact(concept=concept, value=value, period_end=date(fy, 12, 31),
                fiscal_year=fy, source=_src())


def _period(fy=2025, **facts):
    return PeriodFinancials(
        fiscal_year=fy, period_end=date(fy, 12, 31),
        facts={k: _fact(k, v, fy) for k, v in facts.items()})


STD = dict(revenue=1000.0, ebit=150.0, net_income=90.0, equity=600.0,
           depreciation_amortization=50.0, capex=60.0,
           total_assets=900.0, total_liabilities=300.0,
           retained_earnings=200.0, current_assets=300.0,
           current_liabilities=100.0, cash=100.0, total_debt=300.0)


def iv(**over) -> ValuationInputs:
    """Canonical audit company: rev 1000, EBIT 150 (15%), D&A 50, capex 60,
    NI 90, equity 600, debt 300, cash 100 (net debt 200), assets 900,
    liabilities 300, shares 100, EPS 3, DPS 2, price 50."""
    base = dict(
        company=CompanyProfile(ticker="TST", name="Test Co", provider="audit"),
        history=[_period(2023, **STD), _period(2024, **STD), _period(2025, **STD)],
        market=MarketData(ticker="TST", price=50.0, shares_outstanding=100.0),
        shares_outstanding=100.0, cash=100.0, total_debt=300.0, net_debt=200.0,
        total_assets=900.0, total_liabilities=300.0, book_equity=600.0,
        revenue=1000.0, gross_profit=400.0, ebit=150.0, ebitda=200.0,
        net_income=90.0, operating_cash_flow=120.0, capex=60.0,
        depreciation_amortization=50.0, fcf=60.0, eps=3.0, dps=2.0,
        equity_risk_premium=0.05, risk_free_rate=0.04,
        peers=[
            ComparableCompany(ticker="P1", enterprise_value=1200.0, ebitda=100.0),
            ComparableCompany(ticker="P2", enterprise_value=1400.0, ebitda=100.0),
            ComparableCompany(ticker="P3", enterprise_value=1000.0, ebitda=100.0),
        ],
        transactions=[
            PrecedentTransaction(target="D1", enterprise_value=800.0, ebitda=100.0),
            PrecedentTransaction(target="D2", enterprise_value=1000.0, ebitda=100.0),
            PrecedentTransaction(target="D3", enterprise_value=1200.0, ebitda=100.0),
        ],
        segments=[Segment(name="A", metric="ebitda", value=100.0),
                  Segment(name="B", metric="ebitda", value=65.0)],
    )
    base.update(over)
    return ValuationInputs(**base)
