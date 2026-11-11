"""Contract-adapter tests: ValuationInputs + *Assumptions -> ModelResult.

Expected values independently derived from direct formulas (see scratch
derivation in docs/QUANTITATIVE_TESTING.md additions). Fixture company:
revenue 1000, EBIT 150, D&A 50, capex 60, NI 90, equity 600, debt 300, cash 100,
net debt 200, diluted shares 100.
"""
import pytest
from datetime import date, datetime, timezone
from fairvalue.core.schemas import (
    ValuationInputs, CompanyProfile, PeriodFinancials, Fact, SourceRef,
    DcfAssumptions, DdmAssumptions, ResidualIncomeAssumptions, EpvAssumptions,
    GrahamAssumptions, ComparablesAssumptions, PrecedentAssumptions,
    AssetBasedAssumptions, SotpAssumptions, ComparableCompany,
    PrecedentTransaction, Segment)
import fairvalue.valuation.dcf as dcf_mod
import fairvalue.valuation.ddm as ddm_mod
import fairvalue.valuation.residual_income as ri_mod
from fairvalue.valuation.epv import run_model as epv_run_model
import fairvalue.valuation.graham as graham_mod
import fairvalue.valuation.comparables as comps_mod
import fairvalue.valuation.precedents as prec_mod
import fairvalue.valuation.asset_based as ab_mod
import fairvalue.valuation.sotp as sotp_mod

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _src():
    return SourceRef(provider="test", retrieved_at=NOW)


def _fact(concept, value):
    return Fact(concept=concept, value=value, period_end=date(2025, 12, 31),
                fiscal_year=2025, source=_src())


def _period2025():
    return PeriodFinancials(fiscal_year=2025, period_end=date(2025, 12, 31), facts={
        "revenue": _fact("revenue", 1000.0),
        "ebit": _fact("ebit", 150.0),
        "depreciation_amortization": _fact("depreciation_amortization", 50.0),
        "capex": _fact("capex", 60.0),
        "net_income": _fact("net_income", 90.0),
        "eps_diluted": _fact("eps_diluted", 3.0),
        "dps": _fact("dps", 2.0),
        "equity": _fact("equity", 600.0),
    })


def _inputs(**over):
    period = _period2025()
    base = dict(
        company=CompanyProfile(ticker="TST", name="Test Co"),
        history=[period],
        shares_outstanding=100.0, cash=100.0, total_debt=300.0, net_debt=200.0,
        total_assets=900.0, total_liabilities=300.0, book_equity=600.0,
        revenue=1000.0, ebit=150.0, ebitda=165.0, net_income=90.0, eps=3.0,
    )
    base.update(over)
    return ValuationInputs(**base)


# ---------------- DCF ----------------

def test_dcf_adapter_known_answer():
    """FCFF = 150*0.79 + 50 - 60 = 108.5 flat; 5y @10%, g 2%, Gordon."""
    r = dcf_mod.run_model(_inputs(), DcfAssumptions(
        wacc=0.10, terminal_growth=0.02, revenue_growth=0.0,
        target_operating_margin=0.15, capex_pct_revenue=0.06,
        depreciation_pct_revenue=0.05, nwc_pct_revenue_change=0.0))
    assert r.applicable
    assert r.enterprise_value == pytest.approx(1270.2673998, rel=1e-6)
    assert r.equity_value == pytest.approx(1070.2673998, rel=1e-6)
    assert r.value_per_share == pytest.approx(10.7026740, rel=1e-6)
    assert any("PV explicit" in s for s in r.steps)  # explainability requirement


def test_dcf_adapter_missing_capex_history_warns_not_fakes():
    p = PeriodFinancials(fiscal_year=2025, period_end=date(2025, 12, 31), facts={
        "revenue": _fact("revenue", 1000.0), "ebit": _fact("ebit", 150.0)})
    r = dcf_mod.run_model(
        ValuationInputs(company=CompanyProfile(ticker="T", name="T"),
                        history=[p], shares_outstanding=100.0, net_debt=0.0),
        DcfAssumptions(wacc=0.10, terminal_growth=0.02, revenue_growth=0.0,
                       target_operating_margin=0.15))
    assert r.applicable and any("capex assumed 0" in w for w in r.warnings)


def test_dcf_adapter_no_revenue_excluded():
    r = dcf_mod.run_model(ValuationInputs(company=CompanyProfile(ticker="T", name="T")),
                          DcfAssumptions(wacc=0.10))
    assert not r.applicable and r.excluded_reason


# ---------------- DDM ----------------

def test_ddm_adapter_known_answer():
    r = ddm_mod.run_model(_inputs(), DdmAssumptions(
        required_return=0.10, stage1_years=5, stage1_growth=0.06,
        terminal_growth=0.03))
    assert r.value_per_share == pytest.approx(33.4137269, rel=1e-6)


def test_ddm_adapter_non_payer_excluded():
    p = PeriodFinancials(fiscal_year=2025, period_end=date(2025, 12, 31), facts={
        "revenue": _fact("revenue", 1000.0)})  # no dps anywhere
    r = ddm_mod.run_model(ValuationInputs(company=CompanyProfile(ticker="T", name="T"),
                                          history=[p], shares_outstanding=100.0,
                                          net_debt=0.0),
                          DdmAssumptions(required_return=0.10))
    assert not r.applicable and "dividend" in r.excluded_reason


# ---------------- Residual income ----------------

def test_ri_adapter_known_answer():
    # roe 15%, retention 40% -> E=90, D=54, B constant at 600; RI = 30/yr, 10y
    r = ri_mod.run_model(_inputs(), ResidualIncomeAssumptions(
        cost_of_equity=0.10, roe=0.15, retention_ratio=0.4, forecast_years=10))
    assert r.equity_value == pytest.approx(832.1630162, rel=1e-6)
    assert r.value_per_share == pytest.approx(8.3216302, rel=1e-6)


def test_ri_adapter_derived_roe():
    r = ri_mod.run_model(_inputs(), ResidualIncomeAssumptions(
        cost_of_equity=0.10, retention_ratio=0.0, forecast_years=1))
    # roe derived = 90/600 = 15%; E=90, D=90 -> B constant; RI=30 -> 600+30/1.1
    assert r.equity_value == pytest.approx(600 + 30 / 1.1)


# ---------------- EPV ----------------

def test_epv_adapter_known_answer():
    r = epv_run_model(_inputs(), EpvAssumptions(wacc=0.10, tax_rate=0.21,
                                                    margin_normalization="latest"))
    assert r.enterprise_value == pytest.approx(1185.0)
    assert r.value_per_share == pytest.approx(9.85)


def test_epv_adapter_historical_average_margin():
    p24 = PeriodFinancials(fiscal_year=2024, period_end=date(2024, 12, 31), facts={
        "revenue": _fact("revenue", 800.0), "ebit": _fact("ebit", 80.0)})  # 10% margin
    r = epv_run_model(_inputs(history=[p24, _period2025()]), EpvAssumptions(
        wacc=0.10, tax_rate=0.21, margin_normalization="historical_average"))
    # avg margin = (10% + 15%)/2 = 12.5% x revenue 1000 -> EBIT 125
    # after tax 125*0.79 = 98.75 -> EV = 987.5
    assert r.enterprise_value == pytest.approx(987.5)


# ---------------- Graham ----------------

def test_graham_adapter_known_answer():
    r = graham_mod.run_model(_inputs(), GrahamAssumptions(growth_rate=0.05))
    assert r.value_per_share == pytest.approx(3 * (8.5 + 10) * 4.4 / 4.4)


def test_graham_adapter_derived_growth_echoed():
    p24 = PeriodFinancials(fiscal_year=2024, period_end=date(2024, 12, 31), facts={
        "eps_diluted": _fact("eps_diluted", 2.5)})
    r = graham_mod.run_model(_inputs(history=[p24, _period2025()]),
                             GrahamAssumptions(growth_rate=None))
    # derived g = 20%/yr -> clamped to 15 -> V = 3 x (8.5 + 30) x 4.4/4.4 = 115.5
    assert r.applicable
    assert r.value_per_share == pytest.approx(115.5)
    assert any("derived" in w for w in r.warnings)


# ---------------- Comparables ----------------

def _peers():
    return [ComparableCompany(ticker="P1", enterprise_value=1200.0, ebitda=100.0),  # 12x
            ComparableCompany(ticker="P2", enterprise_value=1400.0, ebitda=100.0),  # 14x
            ComparableCompany(ticker="P3", enterprise_value=1000.0, ebitda=100.0)]  # 10x


def test_comparables_adapter_known_answer():
    r = comps_mod.run_model(_inputs(peers=_peers()), ComparablesAssumptions(
        multiples=["ev_ebitda"]))
    # median 12x x EBITDA 165 = 1980 EV; equity 1780; 17.80/share
    assert r.value_per_share == pytest.approx(17.80)


def test_comparables_adapter_excludes_nonpositive_peer_metric():
    peers = _peers() + [ComparableCompany(ticker="BAD", enterprise_value=500.0, ebitda=-50.0)]
    r = comps_mod.run_model(_inputs(peers=peers), ComparablesAssumptions(
        multiples=["ev_ebitda"]))
    assert r.value_per_share == pytest.approx(17.80)  # unchanged: bad peer excluded


# ---------------- Precedents ----------------

def test_precedents_adapter_known_answer():
    deals = [PrecedentTransaction(target="T1", enterprise_value=800.0, ebitda=100.0),  # 8x
             PrecedentTransaction(target="T2", enterprise_value=1000.0, ebitda=100.0),  # 10x
             PrecedentTransaction(target="T3", enterprise_value=1200.0, ebitda=100.0)]  # 12x
    r = prec_mod.run_model(_inputs(transactions=deals), PrecedentAssumptions(
        multiple="ev_ebitda", control_premium=0.20))
    # median 10x x 165 x 1.2 = 1980 EV; equity 1780; 17.80/share
    assert r.value_per_share == pytest.approx(17.80)


def test_precedents_adapter_min_transactions():
    deals = [PrecedentTransaction(target="T1", enterprise_value=800.0, ebitda=100.0)]
    r = prec_mod.run_model(_inputs(), PrecedentAssumptions(min_transactions=2))
    assert not r.applicable


# ---------------- Asset-based & SOTP ----------------

def test_asset_based_adapter():
    r = ab_mod.run_model(_inputs(), AssetBasedAssumptions(
        asset_adjustments=100.0, liability_adjustments=50.0))
    assert r.equity_value == pytest.approx(650.0)
    assert r.value_per_share == pytest.approx(6.50)


def test_sotp_adapter_fallback_median_multiple():
    inputs = _inputs(peers=_peers(), segments=[
        Segment(name="A", metric="ebitda", value=100.0),
        Segment(name="B", metric="ebitda", value=65.0)])
    r = sotp_mod.run_model(inputs, SotpAssumptions(multiple_metric="ev_ebitda"))
    # peer median 12x x (100+65) = 1980 EV; equity 1780; 17.80/share
    assert r.value_per_share == pytest.approx(17.80)


def test_adapters_echo_assumptions():
    r = dcf_mod.run_model(_inputs(), DcfAssumptions(wacc=0.11))
    assert r.assumptions["wacc"] == 0.11
    assert r.assumptions["forecast_years"] == 5
