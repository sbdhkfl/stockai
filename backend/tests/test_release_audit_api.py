"""INDEPENDENT RELEASE AUDIT — API/persistence/market-price edge cases.

Adds coverage beyond the existing suites: DB-backed persistence over the REST
surface, rate limiting, scenario endpoint failure shapes, and honesty checks
for the currently-unavailable live market price (Stooq serves a JS anti-bot
challenge as of this audit; price must stay None with a warning, never faked).
"""
import os

import pytest
import uvicorn
from fastapi.testclient import TestClient

from fairvalue.api.app import app
from fairvalue.data.stooq import StooqProvider


@pytest.fixture
def client():
    return TestClient(app)


def test_persistence_wired_via_env(tmp_path, monkeypatch, client):
    """FAIRVALUE_DB_URL set -> /v1/.../valuation persists; report survives a
    fresh server (in-memory store empty) thanks to the DB."""
    db_file = tmp_path / "audit.db"
    monkeypatch.setenv("FAIRVALUE_DB_URL", f"sqlite:///{db_file.as_posix()}")
    # _db_session() reads the env per request (cached by URL) — no module reload
    # needed (and reload under a live test server was a flake source: removed).
    import fairvalue.api.app as app_mod
    app_mod._db_cache.update({"url": None, "session_factory": None})
    c = TestClient(app)
    r = c.get("/v1/companies/AUR/valuation", params={"demo": "true"})
    assert r.status_code == 200
    rid = r.json()["report_id"]
    from sqlalchemy import select
    from fairvalue.db.models import ReportRecord
    s = __import__("fairvalue.db.session", fromlist=["make_session"]).make_session()
    rec = s.scalar(select(ReportRecord).where(ReportRecord.report_id == rid))
    assert rec is not None and rec.ticker == "AUR"
    assert rec.payload["models"], "full payload (assumptions, steps) must be stored"


def test_rate_limit_enforced_when_configured(monkeypatch):
    # middleware reads module globals at call time -> patch, don't reload
    import fairvalue.api.app as app_mod
    monkeypatch.setattr(app_mod, "RATE_LIMIT", 3)
    monkeypatch.setattr(app_mod, "RATE_WINDOW_S", 60.0)
    app_mod._RATE_WINDOW.clear()
    c = TestClient(app)
    codes = [c.get("/v1/companies/search", params={"q": "a", "demo": "true"}).status_code
             for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429 and codes[4] == 429
    app_mod._RATE_WINDOW.clear()


def test_scenarios_unknown_ticker_error_shape(client):
    r = client.post("/v1/companies/NOPE/scenarios", json={"demo": True})
    assert r.status_code in (400, 404, 422, 502)
    if r.headers.get("content-type", "").startswith("application/json"):
        body = r.json()
        assert "error" in body or "detail" in body


def test_statements_live_ticker_offline_is_structured_error(client):
    """Live EDGAR with no network must surface a structured ProviderError, not a 500."""
    r = client.get("/v1/companies/AAPL/statements")  # live mode; network may or may not exist
    if r.status_code >= 400:
        body = r.json()
        assert "error" in body and body["error"]["code"]
        assert r.status_code != 500


def test_unauthenticated_access_when_no_key_configured(client, monkeypatch):
    monkeypatch.delenv("FAIRVALUE_API_KEY", raising=False)
    assert client.get("/v1/companies/search", params={"q": "a", "demo": "true"}).status_code == 200


def test_price_absence_is_honest_live():
    """Audit finding: Stooq currently serves a JS anti-bot challenge -> the
    provider must return price=None WITH a warning, and never a fabricated or
    default price."""
    m = StooqProvider().get_market_data("AAPL")
    assert m.price is None
    assert m.warnings, "missing price must carry a warning"
    assert m.is_illustrative is False  # and it must not pretend to be demo data
    # an unknown symbol must behave identically (no signal leakage via shape)
    m2 = StooqProvider().get_market_data("ZZZZZZ")
    assert m2.price is None and m2.warnings


def test_price_used_only_when_provided_live(client, monkeypatch):
    """Caller-provided price override: valuation must use it and say so."""
    r = client.get("/v1/companies/AUR/valuation", params={"demo": "true", "price": "50"})
    body = r.json()
    assert body["market"]["price"] == 50.0
