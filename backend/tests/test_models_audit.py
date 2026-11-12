"""Independent audit of all nine `calculate()` models against hand-derived
expected values. Derivations are inline; no expectation is copied from the
engine. If an engine result disagrees with the derivation, this suite fails.
"""
import pytest

from fairvalue.core.schemas import (
    AssetBasedAssumptions, ComparablesAssumptions, DcfAssumptions,
    DdmAssumptions, EpvAssumptions, GrahamAssumptions, PrecedentAssumptions,
    ResidualIncomeAssumptions, SotpAssumptions)
from fairvalue.valuation import dcf, ddm, epv, graham, comparables, precedents
from fairvalue.valuation import residual_income, asset_based, sotp

from tests.fixtures_common import iv


# ---------------- DCF ----------------
# Hand derivation: FCFF_t = 150*0.79 + 50 - 60 = 108.5 flat (growth 0, margins held)
# PV(1..5) = 108.5 * annuity(10%,5) = 411.3004
# Gordon TV = 108.5*1.02/0.08 = 1383.375; PV(TV) = 1383.375/1.61051 = 858.9670
# EV = 1270.2674; equity = 1070.2674; per share = 10.7026740

def test_dcf_gordon_known_answer():
    r = dcf.calculate(iv(), DcfAssumptions(
        wacc=0.10, terminal_growth=0.02, revenue_growth=0.0,
        target_operating_margin=0.15, capex_pct_revenue=0.06,
        depreciation_pct_revenue=0.05, nwc_pct_revenue_change=0.0))
    assert r.applicable
    assert r.value_per_share == pytest.approx(10.7026740, rel=1e-6)
    assert r.enterprise_value == pytest.approx(1270.2673998, rel=1e-6)


def test_dcf_exit_multiple_known_answer():
    # TV = EBITDA_n 200 x 8 = 1600; PV(TV) = 993.4724; EV = 1404.7727
    r = dcf.calculate(iv(), DcfAssumptions(
        wacc=0.10, terminal_method="exit_multiple", exit_ev_ebitda=8.0,
        revenue_growth=0.0, target_operating_margin=0.15,
        capex_pct_revenue=0.06, depreciation_pct_revenue=0.05,
        nwc_pct_revenue_change=0.0))
    assert r.value_per_share == pytest.approx(12.0477448, rel=1e-6)


def test_dcf_excludes_when_capex_history_missing_and_unset():
    from fairvalue.valuation.base import not_applicable  # noqa: F401 (surface check)
    i = iv(history=[], capex=None, ebit=150.0, revenue=1000.0)
    r = dcf.calculate(i, DcfAssumptions(wacc=0.10, capex_pct_revenue=None))
    assert not r.applicable and "capex" in r.excluded_reason


def test_dcf_terminal_dominance_warning():
    r = dcf.calculate(iv(), DcfAssumptions(
        wacc=0.10, terminal_growth=0.02, revenue_growth=0.0,
        target_operating_margin=0.15, capex_pct_revenue=0.06,
        depreciation_pct_revenue=0.05, nwc_pct_revenue_change=0.0))
    # PV(TV)/EV = 858.967/1270.267 = 67.6% — under the 75% threshold here
    assert not any("dominated by the terminal" in w for w in r.warnings)


# ---------------- DDM ----------------
# DPS 2, r=10%, stage1 5y@6%, terminal 3%:
# PV stage1 = 8.9605618; TV = 2*1.06^5*1.03/0.07 = 41.9467*... -> PV(TV) = 24.4531651
# value = 33.4137269

def test_ddm_known_answer():
    r = ddm.calculate(iv(), DdmAssumptions(
        required_return=0.10, stage1_years=5, stage1_growth=0.06,
        terminal_growth=0.03))
    assert r.value_per_share == pytest.approx(33.4137269, rel=1e-6)


def test_ddm_non_payer_excluded():
    r = ddm.calculate(iv(dps=None), DdmAssumptions(required_return=0.10))
    assert not r.applicable and "non-payer" in r.excluded_reason


# ---------------- Residual income ----------------
# BV0 600, ROE 15%, retention 40% -> g=6% < r=10%; RI_t = 0.05*BV_{t-1}
# 10y PV(RI) + Gordon terminal on RI: V = 1381.0702; /100 shares = 13.8107022

def test_ri_known_answer():
    r = residual_income.calculate(iv(), ResidualIncomeAssumptions(
        cost_of_equity=0.10, roe=0.15, retention_ratio=0.4, forecast_years=10))
    assert r.value_per_share == pytest.approx(13.8107022, rel=1e-6)
    assert r.equity_value == pytest.approx(1381.0702190, rel=1e-6)


def test_ri_roe_below_coe_flags_value_destruction():
    r = residual_income.calculate(iv(), ResidualIncomeAssumptions(
        cost_of_equity=0.10, roe=0.05, retention_ratio=0.0, forecast_years=5))
    assert any("value destruction" in w or "below cost" in w for w in r.warnings)


def test_ri_negative_book_excluded():
    r = residual_income.calculate(iv(book_equity=-50.0),
                                  ResidualIncomeAssumptions(cost_of_equity=0.10, roe=0.15))
    assert not r.applicable


# ---------------- EPV ----------------
# Latest EBIT 150 (latest basis); NOPAT = 118.5; EV = 1185; equity 985; 9.85/sh

def test_epv_known_answer_latest():
    r = epv.calculate(iv(), EpvAssumptions(wacc=0.10, tax_rate=0.21,
                                           margin_normalization="latest"))
    assert r.value_per_share == pytest.approx(9.85)
    assert r.enterprise_value == pytest.approx(1185.0)


def test_epv_negative_ebit_excluded():
    r = epv.calculate(iv(ebit=-10.0, history=[]), EpvAssumptions(wacc=0.10))
    assert not r.applicable and "non-positive" in r.excluded_reason


# ---------------- Graham ----------------
# EPS 3, g 5%: V = 3*(8.5+10) = 55.5

def test_graham_known_answer():
    r = graham.calculate(iv(), GrahamAssumptions(growth_rate=0.05))
    assert r.value_per_share == pytest.approx(55.5)


def test_graham_negative_eps_excluded():
    r = graham.calculate(iv(eps=-1.0), GrahamAssumptions(growth_rate=0.05))
    assert not r.applicable


# ---------------- Comparables ----------------
# Peer EV/EBITDA: 12x, 14x, 10x -> median 12; target EBITDA 200
# (12*200 - 200 net debt)/100 = 22.00/share

def test_comparables_known_answer():
    r = comparables.calculate(iv(), ComparablesAssumptions(multiples=["ev_ebitda"]))
    assert r.value_per_share == pytest.approx(22.00)


def test_comparables_excludes_nonpositive_peer():
    from fairvalue.core.schemas import ComparableCompany
    peers = iv().peers + [ComparableCompany(ticker="BAD", enterprise_value=500.0, ebitda=-50.0)]
    r = comparables.calculate(iv(peers=peers), ComparablesAssumptions(multiples=["ev_ebitda"]))
    assert r.value_per_share == pytest.approx(22.00)  # unchanged: bad peer never treated as 0


def test_comparables_no_peers_excluded_with_reason():
    r = comparables.calculate(iv(peers=[]), ComparablesAssumptions())
    assert not r.applicable and r.excluded_reason


# ---------------- Precedents ----------------
# Deal EV/EBITDA 8,10,12 -> median 10 x 1.20 control premium = 12x
# (12*200 - 200)/100 = 22.00/share

def test_precedents_known_answer():
    r = precedents.calculate(iv(), PrecedentAssumptions(
        multiple="ev_ebitda", control_premium=0.20))
    assert r.value_per_share == pytest.approx(22.00)


def test_precedents_too_few_deals_excluded():
    from fairvalue.core.schemas import PrecedentTransaction
    t = [PrecedentTransaction(target="D1", enterprise_value=800.0, ebitda=100.0)]
    r = precedents.calculate(iv(transactions=t), PrecedentAssumptions())
    assert not r.applicable


# ---------------- Asset-based ----------------
# (900 + 100) - (300 + 50) = 650 -> 6.50/share

def test_asset_based_known_answer():
    r = asset_based.calculate(iv(), AssetBasedAssumptions(
        asset_adjustments=100.0, liability_adjustments=50.0))
    assert r.value_per_share == pytest.approx(6.50)
    assert r.equity_value == pytest.approx(650.0)


# ---------------- SOTP ----------------
# Segments A(100)+B(65)=165 EBITDA x 12x = 1980 EV; equity 1780 -> 17.80

def test_sotp_known_answer():
    r = sotp.calculate(iv(), SotpAssumptions(
        segment_multiples={"A": 12.0, "B": 12.0}, multiple_metric="ev_ebitda"))
    assert r.value_per_share == pytest.approx(17.80)


def test_sotp_missing_multiple_is_not_silently_dropped():
    # only A priced: B has no multiple -> model must be inapplicable, not partial
    r = sotp.calculate(iv(), SotpAssumptions(segment_multiples={"A": 12.0},
                                             multiple_metric="ev_ebitda"))
    assert not r.applicable


def test_all_models_produce_explainable_steps():
    from fairvalue.valuation import run_models
    res = run_models(iv(), {
        "dcf": DcfAssumptions(wacc=0.10),
        "ddm": DdmAssumptions(required_return=0.10),
        "epv": EpvAssumptions(wacc=0.10),
        "graham": GrahamAssumptions(growth_rate=0.05),
        "asset_based": AssetBasedAssumptions(),
    })
    for r in res:
        assert r.steps, f"{r.model} produced no step-by-step derivation"
        assert r.assumptions, f"{r.model} did not echo assumptions"
        assert r.formula, f"{r.model} did not state its formula"
