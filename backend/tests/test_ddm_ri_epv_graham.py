"""DDM, residual income, EPV, Graham — known answers and edge cases."""
import pytest
from fairvalue.valuation.ddm import gordon_ddm, two_stage_ddm
from fairvalue.valuation.residual_income import residual_income_value
from fairvalue.valuation.epv import epv
from fairvalue.valuation.graham import graham_value, graham_number
from fairvalue.errors import FairValueError, NotMeaningfulError


def test_gordon_known_answer():
    assert gordon_ddm(2.0, 0.10, 0.05) == pytest.approx(42.0)


def test_gordon_zero_growth():
    assert gordon_ddm(5.0, 0.10, 0.0) == pytest.approx(50.0)


def test_gordon_negative_growth():
    # declining payer: D1 = 1*0.9, r=0.1 -> 0.9/0.2 = 4.5
    assert gordon_ddm(1.0, 0.10, -0.10) == pytest.approx(4.5)


def test_gordon_rejections():
    with pytest.raises(NotMeaningfulError):
        gordon_ddm(0.0, 0.10, 0.02)     # non-payer
    with pytest.raises(FairValueError):
        gordon_ddm(2.0, 0.05, 0.05)     # g >= r
    with pytest.raises(FairValueError):
        gordon_ddm(2.0, -0.05, 0.02)
    with pytest.raises(FairValueError):
        gordon_ddm(-1.0, 0.10, 0.02)    # negative dividend


def test_two_stage_ddm_known_answer():
    # d0=2, g_high=10% for 2y, r=10%, g_term=4% -> pv explicit 4.0, pv term 34.6666667
    r = two_stage_ddm(2.0, 0.10, 0.10, 2, 0.04)
    assert r.pv_explicit_dividends == pytest.approx(4.0)
    assert r.pv_terminal == pytest.approx(34.6666667)
    assert r.value == pytest.approx(38.6666667)


def test_residual_income_known_answer():
    v = residual_income_value(100.0, [15.0, 15.0], 0.10)
    assert v == pytest.approx(107.4380165)


def test_residual_income_with_dividends_clean_surplus():
    # B0=100, E=15, D=5 -> B1=110, RI1=5, RI2=15-11=4
    v = residual_income_value(100.0, [15.0, 15.0], 0.10, dividends=[5.0, 5.0])
    assert v == pytest.approx(100 + 5/1.1 + 4/1.21)


def test_residual_income_roe_equals_r_gives_book_value():
    # Full payout: B stays 100, E=10 = r*B exactly -> RI 0 each year -> V = B0
    v = residual_income_value(100.0, [10.0, 10.0], 0.10, dividends=[10.0, 10.0])
    assert v == pytest.approx(100.0)


def test_residual_income_constant_earnings_growing_book_negative_ri():
    # No payout: B1=110 but E2=10 < r*B1=11 -> RI2 = -1 -> V = 100 - 1/1.21
    v = residual_income_value(100.0, [10.0, 10.0], 0.10)
    assert v == pytest.approx(99.1735537)


def test_residual_income_rejections():
    with pytest.raises(NotMeaningfulError):
        residual_income_value(0.0, [15.0], 0.10)     # no book equity
    with pytest.raises(NotMeaningfulError):
        residual_income_value(-50.0, [15.0], 0.10)
    with pytest.raises(FairValueError):
        residual_income_value(100.0, [15.0], 0.0)
    with pytest.raises(FairValueError):
        residual_income_value(100.0, [15.0], 0.10, dividends=[1.0, 2.0])  # length mismatch


def test_epv_known_answer():
    # (100-10)*0.75 - (20-15) = 62.5 -> 625 at 10%
    assert epv(100.0, 0.25, 20.0, 15.0, 10.0, 0.10) == pytest.approx(625.0)


def test_epv_negative_normalized_earnings_not_meaningful():
    with pytest.raises(NotMeaningfulError):
        epv(10.0, 0.25, 100.0, 0.0, 0.0, 0.10)


def test_epv_sbc_treated_as_expense():
    # without SBC: 100*0.75 - 5 = 70 -> 700; SBC of 10 removes 7.5 of earnings -> 625
    assert epv(100.0, 0.25, 20.0, 15.0, 0.0, 0.10) == pytest.approx(700.0)


def test_graham_known_answer():
    assert graham_value(2.0, 5.0, 4.4) == pytest.approx(37.0)


def test_graham_growth_clamped_at_15():
    assert graham_value(2.0, 40.0, 4.4) == pytest.approx(graham_value(2.0, 15.0, 4.4))
    assert graham_value(2.0, -5.0, 4.4) == pytest.approx(graham_value(2.0, 0.0, 4.4))


def test_graham_yield_adjustment():
    # higher AAA yield -> lower value: 2*(8.5+10)*4.4/8.8 = 18.5
    assert graham_value(2.0, 5.0, 8.8) == pytest.approx(18.5)


def test_graham_number_known_answer():
    # sqrt(22.5 * 4 * 10) = sqrt(900) = 30
    assert graham_number(4.0, 10.0) == pytest.approx(30.0)


def test_graham_negative_eps_rejected():
    with pytest.raises(NotMeaningfulError):
        graham_value(-2.0, 5.0, 4.4)
    with pytest.raises(NotMeaningfulError):
        graham_number(4.0, -10.0)
