"""Risk module tests: Altman Z known answer + applicability + deterministic flags."""
import pytest
from fairvalue.analysis.risk import altman_z, leverage_flags
from fairvalue.errors import FairValueError, NotSuitableError


def test_altman_known_answer_grey_zone():
    # Z = 0.12 + 0.28 + 0.33 + 0.75 + 1.5 = 2.98 -> grey
    r = altman_z(100, 1000, 200, 100, 500, 400, 1500)
    assert r.z == pytest.approx(2.98)
    assert r.zone == "grey"


def test_altman_zone_boundaries():
    # safe: scale EBIT so Z > 2.99: add EBIT 200/1000*3.3 = 0.66 -> 3.31... use EBIT=200
    r = altman_z(100, 1000, 200, 200, 500, 400, 1500)
    assert r.z == pytest.approx(3.31) and r.zone == "safe"
    # distress: strip WC, RE, EBIT; MVE=50 -> Z = 0 + 0 + 0 + 0.075 + 1.5 = 1.575
    r2 = altman_z(0, 1000, 0, 0, 50, 400, 1500)
    assert r2.z == pytest.approx(1.575) and r2.zone == "distress"


def test_altman_not_suitable_for_financials():
    with pytest.raises(NotSuitableError):
        altman_z(1, 1, 1, 1, 1, 1, 1, sector="banking")
    with pytest.raises(NotSuitableError):
        altman_z(1, 1, 1, 1, 1, 1, 1, sector="insurance")


def test_altman_variant_enforcement():
    with pytest.raises(FairValueError):
        altman_z(100, 1000, 200, 100, 500, 400, 1500, variant="private")


def test_altman_applicability_warnings_present():
    r = altman_z(100, 1000, 200, 100, 500, 400, 1500, sector="retail")
    assert any("manufacturing" in w for w in r.warnings)
    assert any("not a bankruptcy probability" in w for w in r.warnings)


def test_leverage_flags():
    r = leverage_flags(interest_coverage=1.5, net_debt_ebitda=5.0, current_ratio=0.8,
                       revenue_history=[100, 90, 130, 80, 140, 100],
                       ocf_history=[10, -5, -3])
    assert any("interest coverage" in f for f in r["flags"])
    assert any("net debt/EBITDA" in f for f in r["flags"])
    assert any("current ratio" in f for f in r["flags"])
    assert any("cash_flow_instability" in f for f in r["flags"])
    assert not any("earnings_volatility" in f for f in r["flags"])  # CV here is low
    assert r["data_gaps"] == []


def test_volatility_flag_fires_on_unstable_revenue():
    r = leverage_flags(revenue_history=[100, 40, 160, 60, 200, 70])
    assert any("earnings_volatility" in f for f in r["flags"])


def test_missing_inputs_reported_as_gaps_not_defaults():
    r = leverage_flags()
    assert r["flags"] == []
    assert len(r["data_gaps"]) == 2
