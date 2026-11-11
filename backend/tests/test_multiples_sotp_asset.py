"""Multiples, SOTP, asset-based valuation tests."""
import pytest
from fairvalue.valuation.comparables import (median_multiple, implied_value_from_multiple,
                                           ENTERPRISE, EQUITY)
from fairvalue.valuation.sotp import sotp_value, Segment
from fairvalue.valuation.asset_based import adjusted_nav, Adjustment
from fairvalue.errors import FairValueError, NotMeaningfulError


def test_median_known_answers():
    assert median_multiple([1, 2, 3, 4, 5]) == pytest.approx(3)
    assert median_multiple([1, 2, 3, 4]) == pytest.approx(2.5)


def test_median_robust_to_outlier_and_excludes_nonpositive():
    # 100x outlier ignored by median; 0/negative peers excluded, not treated as 0
    assert median_multiple([8.0, 9.0, 0.0, -3.0, 10.0, 100.0, 11.0]) == pytest.approx(10.0)


def test_implied_value():
    # median of [10, 12, 14] = 12; target EBITDA 50 -> 600
    assert implied_value_from_multiple([10, 12, 14], 50.0, ENTERPRISE) == pytest.approx(600)


def test_implied_value_negative_metric_not_meaningful():
    with pytest.raises(NotMeaningfulError):
        implied_value_from_multiple([10, 12, 14], -5.0, ENTERPRISE)
    with pytest.raises(NotMeaningfulError):
        median_multiple([0, 0])


def test_sotp_known_answer():
    segs = [Segment("A", 300.0), Segment("B", 200.0), Segment("C", 100.0)]
    r = sotp_value(segs, net_debt=150.0, unallocated_costs=50.0)
    assert r["gross_segment_value"] == pytest.approx(600.0)
    assert r["sotp_value"] == pytest.approx(400.0)
    assert r["coverage"] == pytest.approx(1.0)


def test_sotp_undisclosed_segment_flagged_not_extrapolated():
    segs = [Segment("A", 300.0), Segment("B", 200.0), Segment("C", 0.0, disclosed=False)]
    r = sotp_value(segs, net_debt=100.0)
    assert r["sotp_value"] == pytest.approx(400.0)
    assert r["coverage"] == pytest.approx(2 / 3)
    assert "C" in r["excluded_segments"]


def test_sotp_all_hidden_not_meaningful():
    with pytest.raises(NotMeaningfulError):
        sotp_value([Segment("A", 0.0, disclosed=False)], net_debt=0.0)


def test_adjusted_nav_requires_reasons():
    r = adjusted_nav(500.0, [Adjustment("real estate", +100.0, "marked to appraised value"),
                             Adjustment("receivables", -20.0, "aging haircut")])
    assert r["adjusted_nav"] == pytest.approx(580.0)
    assert r["adjustments_applied"] == 2
    with pytest.raises(FairValueError):
        adjusted_nav(500.0, [Adjustment("x", 10.0, "")])   # undocumented adjustment


def test_sotp_and_nav_reject_garbage():
    with pytest.raises(FairValueError):
        sotp_value(["nope"], 0.0)
    with pytest.raises(FairValueError):
        adjusted_nav(float("inf"), [])
