"""INDEPENDENT RELEASE AUDIT — quantitative spot-checks.

Deliberately distinct derivations from test_models_audit.py (different growth
rates, different statistics, the no-growth RI terminal branch, mixed-multiple
comparables, revenue-based SOTP, mean precedents). If engine and derivation
disagree, the derivation is the authority and the engine gets a bug report.
"""
import pytest

from fairvalue.core.schemas import (
    AssetBasedAssumptions, ComparablesAssumptions, ComparableCompany,
    DcfAssumptions, DdmAssumptions, EpvAssumptions, GrahamAssumptions,
    PrecedentAssumptions, PrecedentTransaction, ResidualIncomeAssumptions,
    Segment, SotpAssumptions)
from fairvalue.analysis.risk import compute_risks
from fairvalue.analysis.scenario import run_scenarios
from fairvalue.valuation import (asset_based, comparables, dcf, ddm, epv,
                                 graham, precedents, residual_income, sotp)
from tests.fixtures_common import iv


def test_audit_dcf_growth_case():
    r = dcf.calculate(iv(), DcfAssumptions(
        wacc=0.12, terminal_growth=0.03, revenue_growth=0.10, forecast_years=3,
        target_operating_margin=0.20, tax_rate=0.25, capex_pct_revenue=0.08,
        depreciation_pct_revenue=0.05, nwc_pct_revenue_change=0.0))
    assert r.value_per_share == pytest.approx(14.4836310, rel=1e-6)


def test_audit_dcf_dilution_treatment():
    """Dilution is applied as end-of-horizon share count over the whole equity
    value (documented conservative choice) — verify the exact factor."""
    base = dcf.calculate(iv(), DcfAssumptions(
        wacc=0.12, terminal_growth=0.03, revenue_growth=0.0, forecast_years=3,
        target_operating_margin=0.20, tax_rate=0.25, capex_pct_revenue=0.08,
        depreciation_pct_revenue=0.05, nwc_pct_revenue_change=0.0))
    dil = dcf.calculate(iv(), DcfAssumptions(
        wacc=0.12, terminal_growth=0.03, revenue_growth=0.0, forecast_years=3,
        target_operating_margin=0.20, tax_rate=0.25, capex_pct_revenue=0.08,
        depreciation_pct_revenue=0.05, nwc_pct_revenue_change=0.0,
        annual_share_growth=0.05))
    # shares_3 = 100 * 1.05^3 = 115.7625 -> per-share scales by 100/115.7625
    assert dil.value_per_share == pytest.approx(
        base.value_per_share * 100 / (100 * 1.05 ** 3), rel=1e-9)
    assert any("conservative" in w for w in dil.warnings)


def test_audit_dcf_working_capital_delta():
    """Full independent derivation with dNWC = 20% of revenue CHANGE, incl. the
    terminal-value base (final-year FCFF includes dNWC — engine must inherit it)."""
    # rev 1100/1210/1331; FCF before NWC 132/145.2/159.72; dNWC 20/22/24.2
    # FCFF 112/123.2/135.52; PV = 100 + 98.2143 + 96.4586 = 294.6729
    # TV = 135.52*1.03/0.09 = 1550.3556; PV(TV) = 1103.4865; EV = 1398.1593
    # equity = 1198.1593 -> 11.9815931/share
    r = dcf.calculate(iv(), DcfAssumptions(
        wacc=0.12, terminal_growth=0.03, revenue_growth=0.10, forecast_years=3,
        target_operating_margin=0.20, tax_rate=0.25, capex_pct_revenue=0.08,
        depreciation_pct_revenue=0.05, nwc_pct_revenue_change=0.20))
    pv = 112 / 1.12 + 123.2 / 1.12 ** 2 + 135.52 / 1.12 ** 3
    tv = 135.52 * 1.03 / 0.09
    ev = pv + tv / 1.12 ** 3
    assert r.value_per_share == pytest.approx((ev - 200) / 100, rel=1e-6)


def test_audit_ddm_new_case():
    r = ddm.calculate(iv(), DdmAssumptions(required_return=0.12, stage1_years=3,
                                           stage1_growth=0.08, terminal_growth=0.04))
    # fixture DPS = 2.0 (my scratch derivation used 3.0; scale by 2/3)
    assert r.value_per_share == pytest.approx(43.3411990 * 2 / 3, rel=1e-6)


def test_audit_ri_no_growth_terminal_branch():
    """g = ROE*retention = 9% = r: engine must use the no-growth perpetuity
    (Gordon is undefined at g=r). Independent derivation: V = 200 + PV(RI) + BV5/1.09^5."""
    r = residual_income.calculate(iv(), ResidualIncomeAssumptions(
        cost_of_equity=0.09, roe=0.18, retention_ratio=0.5, forecast_years=5))
    # BV0 = 600: RI_t = 0.09*BV_{t-1} with 9% BV growth -> each PV term 54/1.09
    # V = 600 + 5*49.5413 + BV5/1.09^5 (=600) = 1447.7053
    assert r.equity_value == pytest.approx(600 + 5 * 54 / 1.09 + 600, rel=1e-6)


def test_audit_ri_gordon_terminal_branch():
    # roe 18%, retention 40% -> g = 7.2% < 9%: Gordon branch on RI
    bv = 600.0  # fixture book equity
    pv = 0.0
    for t in range(1, 6):
        pv += (0.18 - 0.09) * bv / 1.09 ** t
        bv *= 1 + 0.18 * 0.4
    g = 0.18 * 0.4
    tv = (0.18 - 0.09) * bv * (1 + g) / (0.09 - g)
    v = 600 + pv + tv / 1.09 ** 5
    r = residual_income.calculate(iv(), ResidualIncomeAssumptions(
        cost_of_equity=0.09, roe=0.18, retention_ratio=0.4, forecast_years=5))
    assert r.equity_value == pytest.approx(v, rel=1e-9)


def test_audit_epv_historical_average():
    # margins 10% (2024) and 20% (2025); revenue 1000 -> norm EBIT 150; NOPAT 112.5
    from tests.fixtures_common import _period
    p24 = _period(2024, revenue=1000.0, ebit=100.0)
    base_hist = iv().history
    r = epv.calculate(iv(history=[p24, *base_hist]),
                      EpvAssumptions(wacc=0.10, tax_rate=0.25,
                                     margin_normalization="historical_average"))
    assert r.enterprise_value == pytest.approx(1031.25)
    assert r.value_per_share == pytest.approx(8.3125)


def test_audit_graham_new_case():
    assert graham.calculate(iv(eps=4.0), GrahamAssumptions(growth_rate=0.10)
                            ).value_per_share == pytest.approx(114.0)


def test_audit_comparables_mixed_multiples():
    peers = [
        ComparableCompany(ticker="P1", enterprise_value=1500.0, revenue=1000.0),  # ev/s 1.5
        ComparableCompany(ticker="P2", enterprise_value=2000.0, revenue=1000.0),  # 2.0
        ComparableCompany(ticker="P3", enterprise_value=2500.0, revenue=1000.0),  # 2.5
        ComparableCompany(ticker="P4", price=40.0, shares_outstanding=50.0,
                          net_income=100.0),                                       # pe 20
        ComparableCompany(ticker="P5", price=60.0, shares_outstanding=50.0,
                          net_income=150.0),                                       # pe 20
    ]
    r = comparables.calculate(iv(peers=peers),
                              ComparablesAssumptions(multiples=["ev_sales", "pe"]))
    # ev_sales: 2.0 x 1000 = 2000 EV - 200 nd = 1800 / 100 = 18.0
    # pe: median 20x x eps 3 = 60.0 ; combined median = 39.0
    assert r.value_per_share == pytest.approx(39.0)


def test_audit_precedents_mean_statistic():
    r = precedents.calculate(iv(), PrecedentAssumptions(
        multiple="ev_ebitda", statistic="mean", control_premium=0.0))
    assert r.value_per_share == pytest.approx(18.0)


def test_audit_asset_based_negative_equity_warns():
    r = asset_based.calculate(iv(total_assets=200.0, total_liabilities=300.0,
                                 book_equity=-100.0),
                              AssetBasedAssumptions())
    assert r.value_per_share < 0
    assert any("wiped out" in w for w in r.warnings)


def test_audit_sotp_revenue_metric():
    segs = [Segment(name="A", metric="revenue", value=600.0),
            Segment(name="B", metric="revenue", value=400.0)]
    r = sotp.calculate(iv(segments=segs),
                       SotpAssumptions(segment_multiples={"A": 2.0, "B": 3.0},
                                       multiple_metric="ev_sales"))
    # EV = 600*2 + 400*3 = 2400; equity 2200 -> 22.0
    assert r.value_per_share == pytest.approx(22.0)


def test_audit_altman_book_equity_substitution():
    r = compute_risks(iv(market=None))
    # X4 = book equity 600 / TL 300 = 2.0
    expected = 1.2 * 200 / 900 + 1.4 * 200 / 900 + 3.3 * 150 / 900 + 0.6 * 2.0 + 1000 / 900
    assert r.altman_z == pytest.approx(expected)
    assert any("book equity" in n for n in r.leverage_notes)


def test_audit_scenario_internal_consistency():
    """Bear/base/bull must shift ALL drivers in the documented direction."""
    from fairvalue.core.schemas import DcfAssumptions
    base = DcfAssumptions(wacc=0.10, revenue_growth=0.05,
                          target_operating_margin=0.15,
                          capex_pct_revenue=0.06, depreciation_pct_revenue=0.05,
                          nwc_pct_revenue_change=0.0)
    s = run_scenarios(iv(), base)
    # bear: growth halved (2.5%), margin -3pp, wacc +1.5pp, g -0.5pp
    assert s.bear.applied_assumptions["revenue_growth"] == pytest.approx(0.025)
    assert s.bear.applied_assumptions["target_operating_margin"] == pytest.approx(0.12)
    assert s.bear.applied_assumptions["wacc"] == pytest.approx(0.115)
    assert s.bear.applied_assumptions["terminal_growth"] == pytest.approx(0.02)
    # bull: growth x1.4 (7%), margin +3pp, wacc -0.5pp
    assert s.bull.applied_assumptions["revenue_growth"] == pytest.approx(0.07)
    assert s.bull.applied_assumptions["target_operating_margin"] == pytest.approx(0.18)
    # ordering holds
    assert s.bear.value_per_share < s.base.value_per_share < s.bull.value_per_share


def test_audit_terminal_value_share_disclosed():
    r = dcf.calculate(iv(), DcfAssumptions(wacc=0.10, terminal_growth=0.05,
                                           revenue_growth=0.0,
                                           target_operating_margin=0.15,
                                           capex_pct_revenue=0.06,
                                           depreciation_pct_revenue=0.05,
                                           nwc_pct_revenue_change=0.0))
    # g=5% vs wacc=10% -> TV is large: warning must fire (dominance disclosed)
    assert any("dominated by the terminal" in w for w in r.warnings)
