"""Reconciliation engine tests: suitability filtering, outlier handling, range logic."""
import pytest
from fairvalue.valuation.reconcile import reconcile, ModelOutput
from fairvalue.errors import FairValueError


def _out(model, v, suitable=True, completeness=1.0):
    return ModelOutput(model, v, suitable=suitable, data_completeness=completeness)


def test_unsuitable_models_never_enter_the_range():
    """A DCF result on a bank (wrongly produced upstream) must not drag the range."""
    r = reconcile([_out("dcf", 500.0, suitable=False),
                   _out("residual_income", 80.0),
                   _out("ddm", 85.0)])
    assert "dcf" not in r["models_used"]
    assert r["fair_value_range"] == [80.0, 85.0]


def test_outlier_excluded_but_reported():
    r = reconcile([_out("m1", 100.0), _out("m2", 104.0), _out("m3", 300.0)])
    assert r["fair_value_range"][0] < 110
    assert r["outliers_excluded"][0]["model"] == "m3"
    # never silently dropped: it must appear in the output
    assert any(o["model"] == "m3" for o in r["outliers_excluded"])


def test_incomplete_data_lowered_or_excluded():
    r = reconcile([_out("m1", 100.0), _out("m2", 104.0),
                   _out("m3", 102.0, completeness=0.5)])
    assert "m3" not in r["models_used"]


def test_confidence_is_not_a_calibrated_probability():
    r = reconcile([_out("m1", 100.0), _out("m2", 104.0), _out("m3", 102.0)])
    assert "NOT a statistically calibrated probability" in r["confidence"]["caveat"]


def test_low_agreement_when_models_disagree_widely():
    # spread = 160/180 = 88.9% > 75% -> low; (100 vs 160 would be 46% -> moderate)
    r = reconcile([_out("m1", 100.0), _out("m2", 260.0)])
    assert r["confidence"]["model_agreement"] == "low"
    r2 = reconcile([_out("m1", 100.0), _out("m2", 160.0)])
    assert r2["confidence"]["model_agreement"] == "moderate"


def test_market_price_within_range_flagged():
    r = reconcile([_out("m1", 100.0), _out("m2", 104.0)], market_price=102.0)
    assert r["confidence"]["market_price_within_range"] is True


def test_no_suitable_models_blocks():
    with pytest.raises(FairValueError):
        reconcile([_out("dcf", 500.0, suitable=False)])
    with pytest.raises(FairValueError):
        reconcile([])
