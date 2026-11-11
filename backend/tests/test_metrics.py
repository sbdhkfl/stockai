"""Metrics tests: hand-derived known answers + non-meaningful edge cases."""
import pytest
from fairvalue import metrics as M
from fairvalue.errors import FairValueError, NotMeaningfulError


def test_margins():
    assert M.gross_margin(100, 60).value == pytest.approx(0.40)
    assert M.operating_margin(20, 100).value == pytest.approx(0.20)
    assert M.net_margin(12, 100).value == pytest.approx(0.12)


def test_roe_average_vs_end_balance_proxy():
    # NI 15, equity 100->120: avg 110 -> 0.1363636
    r = M.roe(15.0, 120.0, 100.0)
    assert r.value == pytest.approx(15 / 110)
    r2 = M.roe(15.0, 120.0)
    assert r2.value == pytest.approx(0.125)
    assert "end_balance_proxy" in r2.flags


def test_roic_known_answer():
    # NOPAT = 100*0.75 = 75; IC = 200+300-100 = 400 -> 0.1875
    assert M.roic(100.0, 0.25, 200.0, 300.0, 100.0).value == pytest.approx(0.1875)


def test_liquidity_ratios():
    assert M.current_ratio(150, 100).value == pytest.approx(1.5)
    assert M.quick_ratio(150, 50, 100).value == pytest.approx(1.0)
    assert M.cash_ratio(30, 100).value == pytest.approx(0.3)


def test_solvency():
    assert M.debt_to_equity(200, 400).value == pytest.approx(0.5)
    assert M.net_debt_to_ebitda(400, 100).value == pytest.approx(4.0)
    assert M.interest_coverage(50, 10).value == pytest.approx(5.0)
    m = M.debt_maturity_share({1: 100, 3: 100, 8: 300}, 5)
    assert m.value == pytest.approx(200 / 500)


def test_interest_coverage_ebit_negative_is_not_meaningful():
    with pytest.raises(NotMeaningfulError):
        M.interest_coverage(-10, 10)


def test_efficiency_with_averages():
    assert M.asset_turnover(220, 120, 100).value == pytest.approx(2.0)
    assert M.inventory_turnover(400, 55, 45).value == pytest.approx(8.0)
    assert M.receivables_turnover(365, 55, 45).value == pytest.approx(7.3)


def test_cagr_known_answer_and_rejections():
    assert M.cagr(121, 100, 2).value == pytest.approx(0.10)
    with pytest.raises(NotMeaningfulError):
        M.cagr(-121, 100, 2)   # sign change is not growth
    with pytest.raises(NotMeaningfulError):
        M.cagr(121, 0, 2)
    with pytest.raises(FairValueError):
        M.cagr(121, 100, 0)


def test_valuation_ratios_and_not_meaningful():
    assert M.pe_ratio(40, 2).value == pytest.approx(20)
    assert M.pb_ratio(30, 10).value == pytest.approx(3.0)
    assert M.ev_ebitda(1000, 100).value == pytest.approx(10.0)
    assert M.ev_sales(1000, 250).value == pytest.approx(4.0)
    assert M.fcf_yield(10, 200).value == pytest.approx(0.05)
    with pytest.raises(NotMeaningfulError):
        M.pe_ratio(40, -2)
    with pytest.raises(NotMeaningfulError):
        M.pb_ratio(30, -10)
    with pytest.raises(NotMeaningfulError):
        M.ev_ebitda(1000, 0)


def test_missing_values_are_errors_not_zeros():
    with pytest.raises(FairValueError):
        M.net_margin(None, 100)
    with pytest.raises(FairValueError):
        M.net_margin(float("nan"), 100)
