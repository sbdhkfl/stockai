"""DCF known-answer and edge-case tests. Expected values from
docs/QUANTITATIVE_TESTING.md (independently hand-derived)."""
import pytest
from fairvalue.valuation.dcf import dcf_fcff, bridge_ev_to_equity, check_dcf_suitability
from fairvalue.errors import FairValueError, NotMeaningfulError, NotSuitableError


def test_dcf_known_answer():
    r = dcf_fcff([100, 100, 100], 0.10, 0.02, 200.0, 50.0)
    assert r.discounted_fcff == pytest.approx([90.9090909, 82.6446281, 75.1314801])
    assert r.pv_explicit == pytest.approx(248.6851991)
    assert r.terminal_value == pytest.approx(1275.0)
    assert r.pv_terminal_value == pytest.approx(957.9263711)
    assert r.enterprise_value == pytest.approx(1206.6115702)
    assert r.equity_value == pytest.approx(1006.6115702)
    assert r.value_per_share == pytest.approx(20.1322314)


def test_dcf_zero_growth_collapses_to_perpetuity():
    """FCFF flat at 100, g=0, w=10% over 3y then flat perpetuity == exactly 1000 EV."""
    r = dcf_fcff([100, 100, 100], 0.10, 0.0, 0.0, 10.0)
    assert r.enterprise_value == pytest.approx(1000.0)


def test_dcf_ev_bridge_both_directions():
    assert bridge_ev_to_equity(1206.6115702, 200.0) == pytest.approx(1006.6115702)
    # net debt exceeding EV yields negative equity: surfaced, not clamped
    assert bridge_ev_to_equity(100.0, 150.0) == pytest.approx(-50.0)


def test_dcf_high_debt_negative_equity_reported_not_hidden():
    r = dcf_fcff([100, 100, 100], 0.10, 0.02, 5000.0, 50.0)
    assert r.equity_value < 0
    assert r.value_per_share < 0


def test_dcf_share_split_invariance():
    """Split 2:1: equity value invariant, per-share halves."""
    a = dcf_fcff([100, 100, 100], 0.10, 0.02, 200.0, 50.0)
    b = dcf_fcff([100, 100, 100], 0.10, 0.02, 200.0, 100.0)
    assert b.equity_value == pytest.approx(a.equity_value)
    assert b.value_per_share == pytest.approx(a.value_per_share / 2)


def test_dcf_negative_final_fcff_refuses_terminal_value():
    with pytest.raises(NotMeaningfulError):
        dcf_fcff([100, 100, -50], 0.10, 0.02, 0.0, 10.0)


def test_dcf_g_at_or_above_wacc_rejected():
    with pytest.raises(FairValueError):
        dcf_fcff([100], 0.10, 0.10, 0.0, 10.0)
    with pytest.raises(FairValueError):
        dcf_fcff([100], 0.10, 0.12, 0.0, 10.0)


def test_dcf_extreme_and_invalid_inputs():
    with pytest.raises(FairValueError):
        dcf_fcff([100], -0.05, 0.01, 0.0, 10.0)     # negative wacc
    with pytest.raises(FairValueError):
        dcf_fcff([100], 0.10, 0.02, 0.0, 0.0)       # zero shares
    with pytest.raises(FairValueError):
        dcf_fcff([float("nan")], 0.10, 0.02, 0.0, 10.0)
    with pytest.raises(FairValueError):
        dcf_fcff([], 0.10, 0.02, 0.0, 10.0)
    # extreme-but-valid discount rate, hand-derived:
    # PV1 = 100/1.5 = 66.6667; TV = 100/0.5 = 200; PV(TV) = 200/1.5 = 133.3333
    # EV = 200.0 -> per share = 20.0
    r = dcf_fcff([100], 0.50, 0.0, 0.0, 10.0)
    assert r.value_per_share == pytest.approx(20.0)


def test_dcf_not_suitable_for_banks():
    with pytest.raises(NotSuitableError):
        check_dcf_suitability("banking")
    with pytest.raises(NotSuitableError):
        check_dcf_suitability("insurance")
    check_dcf_suitability("software")  # no raise
