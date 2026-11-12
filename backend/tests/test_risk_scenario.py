"""Risk & scenario engine tests against the integrated surface.

Altman hand derivation (audit fixture): WC = 300-100 = 200; TA 900;
RE 200; EBIT 150; X4 = market cap 5000 / TL 300 = 16.6667; sales 1000
Z = 0.266667 + 0.311111 + 0.55 + 10.0 + 1.111111 = 12.2388889 (safe).
"""
import pytest

from fairvalue.analysis.risk import compute_risks
from fairvalue.analysis.scenario import run_scenarios, sensitivity_grid, apply_spec
from fairvalue.core.schemas import DcfAssumptions

from tests.fixtures_common import iv


def test_altman_known_answer_with_market_x4():
    r = compute_risks(iv())
    assert r.altman_z == pytest.approx(12.2388889, rel=1e-6)
    assert r.altman_zone == "safe"


def test_altman_book_equity_fallback_disclosed():
    r = compute_risks(iv(market=None))
    assert r.altman_z is not None
    assert any("book equity" in n for n in r.leverage_notes)


def test_altman_gaps_reported_not_zero_filled():
    r = compute_risks(iv(history=[], total_assets=None))
    assert any("total assets" in g for g in r.data_gaps)


def test_negative_fcf_streak_flagged():
    from tests.fixtures_common import _period, STD
    h = [_period(2023, **STD), _period(2024, **STD),
         _period(2025, operating_cash_flow=-10.0, capex=60.0, **{k: v for k, v in STD.items()
                 if k not in ("operating_cash_flow", "capex")})]
    r = compute_risks(iv(history=h, operating_cash_flow=-10.0, capex=60.0, fcf=-70.0))
    assert r.consecutive_fcf_negative >= 1
    assert any("negative" in f for f in r.flags)


def test_scenarios_bear_lt_base_lt_bull():
    base = DcfAssumptions(wacc=0.10, revenue_growth=0.05,
                          target_operating_margin=0.15,
                          capex_pct_revenue=0.06, depreciation_pct_revenue=0.05,
                          nwc_pct_revenue_change=0.0)
    s = run_scenarios(iv(), base)
    assert s.bear.value_per_share < s.base.value_per_share < s.bull.value_per_share


def test_scenario_assumptions_echoed_for_reproducibility():
    base = DcfAssumptions(wacc=0.10, revenue_growth=0.05)
    s = run_scenarios(iv(), base)
    assert s.bear.applied_assumptions["wacc"] == pytest.approx(0.115)
    assert s.bear.applied_assumptions["revenue_growth"] == pytest.approx(0.025)


def test_terminal_growth_clamped_below_wacc_in_bull():
    base = DcfAssumptions(wacc=0.06, terminal_growth=0.055, revenue_growth=0.0)
    spec_applied = apply_spec(base, __import__("fairvalue.analysis.scenario", fromlist=["BULL"]).BULL)
    assert spec_applied.terminal_growth < spec_applied.wacc


def test_sensitivity_grid_monotone_in_wacc():
    base = DcfAssumptions(wacc=0.10, revenue_growth=0.05,
                          target_operating_margin=0.15,
                          capex_pct_revenue=0.06, depreciation_pct_revenue=0.05,
                          nwc_pct_revenue_change=0.0)
    pts = sensitivity_grid(iv(), base)
    by_wacc = {}
    for p in pts:
        by_wacc.setdefault(p.wacc, []).append(p.value_per_share)
    waccs = sorted(by_wacc)
    means = [sum(v for v in by_wacc[w] if v is not None) /
             max(1, len([v for v in by_wacc[w] if v is not None])) for w in waccs]
    assert means == sorted(means, reverse=True)
