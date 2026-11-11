"""Scenario engine and sensitivity grid tests."""
import pytest
from fairvalue.analysis.scenario import (DCFInputs, run_scenario, run_all_scenarios,
                                sensitivity_grid, apply_scenario)
from fairvalue.valuation.dcf import dcf_fcff
from fairvalue.errors import FairValueError

BASE = DCFInputs(fcff=[100, 100, 100], wacc=0.10, terminal_growth=0.02,
                 net_debt=200.0, diluted_shares=50.0)


def test_base_scenario_equals_plain_dcf():
    assert run_scenario(BASE, "base")["value_per_share"] == pytest.approx(20.1322314)


def test_scenario_ordering_bear_lt_base_lt_bull():
    r = run_all_scenarios(BASE)
    assert r["bear"]["value_per_share"] < r["base"]["value_per_share"] < r["bull"]["value_per_share"]


def test_bear_scenario_known_answer():
    # hand-derived: fcff 70s, wacc 11.5%, g 1%, net debt 220 -> 8.7065039/share
    assert run_scenario(BASE, "bear")["value_per_share"] == pytest.approx(8.7065039, rel=1e-5)


def test_terminal_growth_clamped_for_consistency():
    # base already at g=8.5%: bull raises g to 9% while cutting wacc to 9%
    # -> clamp to wacc - 50bp = 8.5%, and the clamp must be recorded
    base = DCFInputs(fcff=[100, 100, 100], wacc=0.10, terminal_growth=0.085,
                     net_debt=200.0, diluted_shares=50.0)
    r = run_scenario(base, "bull")
    assert r["terminal_growth_clamped_to"] == pytest.approx(0.085)
    assert r["assumptions_used"]["terminal_growth"] == pytest.approx(0.085)
    assert r["assumptions_used"]["wacc"] == pytest.approx(0.09)


def test_scenario_echoes_assumptions():
    r = run_scenario(BASE, "bear")
    assert r["assumptions_used"]["wacc"] == pytest.approx(0.115)
    assert r["assumptions_used"]["net_debt"] == pytest.approx(220.0)


def test_unknown_scenario_rejected():
    with pytest.raises(FairValueError):
        run_scenario(BASE, "melt-up")


def test_sensitivity_grid_monotonicity():
    grid = sensitivity_grid(BASE, wacc_range=[0.08, 0.10, 0.12],
                            g_range=[0.0, 0.01, 0.02])["grid"]
    # value decreases in WACC (columns constant g) ...
    for g in (0.0, 0.01, 0.02):
        assert grid[0.08][g] > grid[0.10][g] > grid[0.12][g]
    # ... and increases in terminal growth (rows constant wacc)
    for w in (0.08, 0.10, 0.12):
        assert grid[w][0.0] < grid[w][0.01] < grid[w][0.02]


def test_sensitivity_grid_marks_g_greater_equal_wacc_as_none_not_faked():
    grid = sensitivity_grid(BASE, wacc_range=[0.05], g_range=[0.05, 0.06])["grid"]
    assert grid[0.05][0.05] is None and grid[0.05][0.06] is None
