"""SDK tests: typed client against a REAL uvicorn server (thread) running the
actual FastAPI app - the network path is exercised end to end, no fakes.
"""
import pytest

from fairvalue.api.app import app
from fairvalue.core.schemas import (
    CompanyProfile, Fundamentals, HealthMetrics, RiskAssessment,
    ScenarioSet, ValuationReport, ValuationExplanation)
from fairvalue.sdk import FairValueClient, SdkError


@pytest.fixture
def client(server_url):
    c = FairValueClient(base_url=server_url)
    yield c
    c.close()


def test_search_typed(client):
    out = client.search("aurora", demo=True)
    assert out and isinstance(out[0], CompanyProfile)


def test_company_typed_and_not_found(client):
    c = client.company("AUR", demo=True)
    assert isinstance(c, CompanyProfile) and c.ticker == "AUR"
    with pytest.raises(SdkError) as e:
        client.company("NOPE", demo=True)
    assert e.value.code == "not_found" and e.value.status is None


def test_statements_typed_with_provenance(client):
    f = client.statements("AUR", demo=True)
    assert isinstance(f, Fundamentals)
    assert f.periods and next(iter(f.periods[-1].facts.values())).source.provider


def test_valuation_typed_full_report(client):
    rep = client.valuation("AUR", demo=True)
    assert isinstance(rep, ValuationReport)
    assert rep.is_illustrative is True                     # demo data labeled
    assert rep.reconciliation.base is not None
    assert rep.reconciliation.low <= rep.reconciliation.base <= rep.reconciliation.high
    dcf = next(m for m in rep.models if m.model == "dcf")
    assert dcf.steps and dcf.assumptions                   # explainability preserved
    assert rep.data_quality.missing is not None


def test_valuation_models_subset(client):
    rep = client.valuation("AUR", demo=True, models=["dcf", "epv"])
    assert {m.model for m in rep.models} <= {"dcf", "epv"}


def test_risks_and_health_typed(client):
    r = client.risks("AUR", demo=True)
    assert isinstance(r, RiskAssessment) and "altman_zone" in r.model_fields
    h = client.health_metrics("AUR", demo=True)
    assert isinstance(h, HealthMetrics)


def test_scenarios_typed_and_ordered(client):
    s = client.scenarios("AUR", demo=True)
    assert isinstance(s, ScenarioSet)
    assert s.bear.value_per_share < s.base.value_per_share < s.bull.value_per_share


def test_explain_typed(client):
    e = client.explain("AUR", demo=True)
    assert isinstance(e, ValuationExplanation) and e.headline


def test_report_roundtrip_and_unknown_error(client):
    rep = client.valuation("HELI", demo=True)
    assert rep.report_id
    again = client.report(rep.report_id)
    assert again.company.ticker == "HELI"
    with pytest.raises(SdkError) as e:
        client.report("no-such-id")
    assert e.value.code == "not_found"


def test_auth_header_sent_when_configured(client, monkeypatch):
    monkeypatch.setenv("FAIRVALUE_API_KEY", "secret")
    with pytest.raises(SdkError) as e:
        client.valuation("AUR", demo=True)   # client has no key -> 401
    # the FastAPI middleware returns {"detail": ...} for HTTPException-based 401;
    # SDK must surface *something* typed, not crash
    assert e.value.code in ("http_error", "unauthorized", "bad_response")


def test_authenticated_client(server_url, monkeypatch):
    monkeypatch.setenv("FAIRVALUE_API_KEY", "secret")
    c = FairValueClient(base_url=server_url, api_key="secret")
    try:
        rep = c.valuation("AUR", demo=True)
        assert rep.company.ticker == "AUR"
    finally:
        c.close()


def test_connection_error_is_typed():
    c = FairValueClient(base_url="http://127.0.0.1:1")  # nothing listening
    try:
        with pytest.raises(SdkError) as e:
            c.search("x")
        assert e.value.code == "connection_error"
    finally:
        c.close()


def test_context_manager(server_url):
    with FairValueClient(base_url=server_url) as c:
        assert c.search("aurora", demo=True)
