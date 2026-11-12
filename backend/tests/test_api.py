"""REST API tests (fairvalue/api/app.py) against the demo provider."""
import pytest
from fastapi.testclient import TestClient

from fairvalue.api.app import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_search(client):
    r = client.get("/v1/companies/search", params={"q": "aurora", "demo": "true"})
    assert r.status_code == 200 and len(r.json()) >= 1


def test_company_not_found_is_api_error_shape(client):
    r = client.get("/v1/companies/NOPE", params={"demo": "true"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_statements_returns_periods_and_provenance(client):
    r = client.get("/v1/companies/AUR/statements", params={"demo": "true"})
    body = r.json()
    assert len(body["periods"]) >= 3
    fact = next(iter(body["periods"][-1]["facts"].values()))
    assert fact["source"]["provider"]          # provenance present


def test_valuation_end_to_end(client):
    r = client.get("/v1/companies/AUR/valuation",
                   params={"demo": "true", "wacc": "0.10"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_illustrative"] is True     # demo data labeled, never silent
    names = [m["model"] for m in body["models"]]
    assert "dcf" in names and "comparables" in names
    dcf = next(m for m in body["models"] if m["model"] == "dcf")
    assert dcf["steps"]
    # �7 params don't include wacc: the CAPM-derived rate is used and echoed
    assert 0.0 < dcf["assumptions"]["wacc"] < 0.30
    assert body["reconciliation"]["base"] is not None
    assert body["reconciliation"]["low"] <= body["reconciliation"]["base"] <= body["reconciliation"]["high"]
    assert body["scenarios"]["bear"]["value_per_share"] < body["scenarios"]["bull"]["value_per_share"]
    assert body["explanation"]["headline"]
    assert body["report_id"]


def test_valuation_report_persisted_and_retrievable(client):
    v = client.get("/v1/companies/HELI/valuation", params={"demo": "true"}).json()
    rid = v["report_id"]
    r = client.get(f"/v1/reports/{rid}")
    assert r.status_code == 200 and r.json()["company"]["ticker"] == "HELI"


def test_metrics_and_risks_endpoints(client):
    m = client.get("/v1/companies/CRVN/metrics", params={"demo": "true"}).json()
    assert "health" in m and "multiples" in m
    rk = client.get("/v1/companies/CRVN/risks", params={"demo": "true"}).json()
    assert "altman_zone" in rk and "data_gaps" in rk


def test_api_key_enforced_when_configured(client, monkeypatch):
    monkeypatch.setenv("FAIRVALUE_API_KEY", "secret")
    r = client.get("/v1/companies/AUR/valuation", params={"demo": "true"})
    assert r.status_code == 401
    r = client.get("/v1/companies/AUR/valuation",
                   params={"demo": "true"}, headers={"X-API-Key": "secret"})
    assert r.status_code == 200


def test_report_persists_to_db_when_configured(client, monkeypatch, tmp_path):
    """FAIRVALUE_DB_URL on -> valuation saves through fairvalue.db and
    /v1/reports serves from the DB, surviving loss of the in-memory store."""
    from fairvalue.api import app as app_mod

    db_file = tmp_path / "reports.db"
    monkeypatch.setenv("FAIRVALUE_DB_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setattr(app_mod, "_db_cache", {"url": None, "session_factory": None})

    v = client.get("/v1/companies/AUR/valuation", params={"demo": "true"}).json()
    rid = v["report_id"]
    app_mod._REPORTS.clear()  # simulate a server restart: memory gone, DB kept

    r = client.get(f"/v1/reports/{rid}")
    assert r.status_code == 200 and r.json()["company"]["ticker"] == "AUR"
    rows = client.get("/v1/reports").json()
    assert any(row["report_id"] == rid for row in rows)


def test_cors_allows_dashboard_origin_only(client):
    # the dashboard (localhost:3000) must be able to call the API; other
    # origins must not be granted access (no wildcard)
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    r = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers
