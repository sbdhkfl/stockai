"""API contract tests (thin adapter over the engine)."""
import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_dcf_endpoint_known_answer(client):
    r = client.post("/valuation/dcf", json={
        "fcff": [100, 100, 100], "wacc": 0.10, "terminal_growth": 0.02,
        "net_debt": 200.0, "diluted_shares": 50.0})
    assert r.status_code == 200
    body = r.json()
    assert body["value_per_share"] == pytest.approx(20.1322314)
    assert body["assumptions_echoed"]["wacc"] == 0.10   # assumptions echoed for explainability


def test_dcf_endpoint_rejects_g_ge_wacc(client):
    r = client.post("/valuation/dcf", json={
        "fcff": [100], "wacc": 0.05, "terminal_growth": 0.05,
        "net_debt": 0.0, "diluted_shares": 10.0})
    assert r.status_code == 422


def test_ddm_endpoint(client):
    r = client.post("/valuation/ddm", json={"d0": 2.0, "r": 0.10, "g": 0.05})
    assert r.json()["value"] == pytest.approx(42.0)


def test_altman_endpoint(client):
    r = client.post("/risk/altman-z", json={
        "working_capital": 100, "total_assets": 1000, "retained_earnings": 200,
        "ebit": 100, "market_equity": 500, "total_liabilities": 400,
        "sales": 1500})
    assert r.json()["z_score"] == pytest.approx(2.98)
    assert r.json()["zone"] == "grey"


def test_altman_endpoint_bank_rejection(client):
    r = client.post("/risk/altman-z", json={
        "working_capital": 1, "total_assets": 1, "retained_earnings": 1,
        "ebit": 1, "market_equity": 1, "total_liabilities": 1, "sales": 1,
        "sector": "banking"})
    assert r.status_code == 422
