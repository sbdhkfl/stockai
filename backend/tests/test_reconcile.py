"""Reconciliation-layer tests (family-weighted aggregation policy).

Hand-derived: dcf v=20 (w .8), epv v=10 (w .5) -> income aggregate
(20*0.8 + 10*0.5)/1.3 = 16.1538462; comparables v=30 (w 1.0) -> market 30;
asset_based v=5 (w .7) -> asset 5. Base = median(16.1538, 30, 5) = 16.1538.
"""
import pytest

from fairvalue.core.schemas import ModelResult
from fairvalue.valuation.reconcile import reconcile, MODEL_FAMILIES


def _r(model, v, suitable=0.5, applicable=True):
    return ModelResult(model=model, applicable=applicable, value_per_share=v,
                       suitability=suitable)


def test_family_weighted_known_answer():
    rec = reconcile([
        _r("dcf", 20.0, suitable=0.8),
        _r("epv", 10.0, suitable=0.5),
        _r("comparables", 30.0, suitable=1.0),
        _r("asset_based", 5.0, suitable=0.7),
    ])
    assert rec.family_values["income"] == pytest.approx(16.1538462, rel=1e-6)
    assert rec.family_values["market"] == pytest.approx(30.0)
    assert rec.family_values["asset"] == pytest.approx(5.0)
    assert rec.base == pytest.approx(16.1538462, rel=1e-6)
    assert (rec.low, rec.high) == (5.0, 30.0)


def test_no_family_dominates_the_base():
    """A single flashy model cannot become the base when families disagree."""
    rec = reconcile([
        _r("dcf", 100.0, suitable=0.9),
        _r("comparables", 10.0, suitable=0.9),
        _r("asset_based", 10.0, suitable=0.9),
    ])
    # income family = 100; market = 10; asset = 10 -> base = median = 10, NOT 100
    assert rec.base == pytest.approx(10.0)


def test_inapplicable_models_excluded_with_reason():
    rec = reconcile([
        ModelResult(model="ddm", applicable=False, value_per_share=None,
                    excluded_reason="no dividend reported"),
        _r("dcf", 20.0),
    ])
    assert "dcf" in rec.included and "ddm" not in rec.included
    assert any(e.model == "ddm" and "dividend" in e.reason for e in rec.excluded)


def test_family_disagreement_recorded():
    rec = reconcile([
        _r("dcf", 100.0, suitable=0.9),
        _r("comparables", 10.0, suitable=0.9),
    ])
    assert any("disagree" in n for n in rec.notes)


def test_no_applicable_model_gives_no_fake_range():
    rec = reconcile([_r("dcf", None, applicable=False)])
    assert rec.low is None and rec.base is None and rec.high is None


def test_every_family_member_is_classified():
    for fam, members in MODEL_FAMILIES.items():
        for m in members:
            assert m in ("dcf", "ddm", "residual_income", "epv", "graham",
                         "comparables", "precedents", "asset_based", "sotp")
