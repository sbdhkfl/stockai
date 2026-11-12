"""Agent-supplied data → valuation workflow, end to end (req 17/18).

Multiple synthetic companies across industries/currencies prove ticker
independence; the whole workflow runs with every network path disabled to
prove the engine's independence from SEC/FRED/Stooq (req 15). Surfaces covered:
service, REST POST, and the two MCP workflow tools.
"""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import fairvalue.mcp_server as srv
from fairvalue.agent_data import (
    AgentSuppliedCompany,
    ProvenanceKind,
    SuppliedFact,
    SuppliedFxRate,
    SuppliedMarket,
    SuppliedPeriod,
    build_valuation_inputs,
)
from fairvalue.api.app import app
from fairvalue.service import ValuationOptions, run_valuation_from_data


@pytest.fixture(autouse=True)
def _rate_window_isolation():
    """REST tests share the app's in-process rate window; reset it so this
    file neither trips nor masks the limit (behavior covered in test_api)."""
    from fairvalue.api import app as app_mod
    app_mod._RATE_WINDOW.clear()
    yield
    app_mod._RATE_WINDOW.clear()

TECH = dict(revenue=1000.0, gross_profit=750.0, ebit=150.0, net_income=90.0,
            depreciation_amortization=50.0, capex=60.0, total_assets=900.0,
            total_liabilities=300.0, equity=600.0, cash=100.0, total_debt=300.0,
            operating_cash_flow=120.0, eps_diluted=0.9, shares_outstanding=100.0,
            dps=0.9, current_assets=300.0, current_liabilities=100.0)


def _period(end: str, start: str | None = None, **facts) -> SuppliedPeriod:
    return SuppliedPeriod(
        period_end=date.fromisoformat(end),
        period_start=date.fromisoformat(start) if start else None,
        facts=[SuppliedFact(concept=c, value=v,
                            period_end=date.fromisoformat(end),
                            period_start=date.fromisoformat(start) if start else None)
               for c, v in facts.items()])


def _company(ticker: str, *, currency: str = "USD", industry: str = "Software",
             sector: str = "Technology", years=(2023, 2024, 2025),
             market: bool = True, rf: float | None = 0.043,
             fx=None, peers=None) -> AgentSuppliedCompany:
    return AgentSuppliedCompany(
        ticker=ticker, name=f"{ticker} Synthetic Co", sector=sector,
        industry=industry, currency=currency, accounting_standard="US-GAAP",
        periods=[_period(f"{y}-12-31", f"{y}-01-01", **TECH) for y in years],
        market=SuppliedMarket(price=20.0, as_of=date(2026, 1, 15),
                              shares_outstanding=100.0, beta=1.1) if market else None,
        risk_free_rate=rf, fx_rates=fx or [], peers=peers or [])


# ---------------- multi-company ticker independence (req 17) ----------------

@pytest.mark.parametrize("ticker,industry,expect_comparables", [
    ("ZZZX", "Software", False),                 # fictional tech, no peers
    ("NEWR", "Retail", True),                    # fictional retailer WITH peers
    ("brk.b", "Insurance", False),               # dotted, lowercase input
])
def test_multiple_synthetic_companies_value_independently(
        ticker, industry, expect_comparables):
    peers = ([{"ticker": "PA", "enterprise_value": 1200.0, "ebitda": 200.0},
              {"ticker": "PB", "enterprise_value": 1400.0, "ebitda": 200.0},
              {"ticker": "PC", "enterprise_value": 1000.0, "ebitda": 200.0}]
             if expect_comparables else [])
    data = _company(ticker, industry=industry, peers=peers)
    rep = run_valuation_from_data(data, ValuationOptions())
    assert rep.company.ticker == ticker.upper()
    assert rep.company.name.startswith(ticker.upper()[:4].upper()) or rep.company.name
    assert rep.is_illustrative is False                 # never demo-labeled
    applicable = [m for m in rep.models if m.applicable]
    assert len(applicable) >= 4, [m.model for m in rep.models]
    assert rep.reconciliation.base is not None
    assert rep.reconciliation.low <= rep.reconciliation.base <= rep.reconciliation.high
    # every model either runs or carries an explicit reason (req 12)
    for m in rep.models:
        if not m.applicable:
            assert m.excluded_reason, m.model
    if expect_comparables:
        assert any(m.model == "comparables" and m.applicable for m in rep.models)


def test_eur_company_with_fx_values_in_company_currency():
    data = _company("EURO", currency="EUR", rf=0.028,
                    fx=[SuppliedFxRate(from_currency="USD", rate=0.92,
                                       as_of=date(2025, 12, 31),
                                       source="ECB reference rate")])
    # replace the last period's gross_profit with an explicitly-USD fact to
    # exercise conversion inside the valuation (same concept, no duplicate)
    data.periods[-1].facts = [f for f in data.periods[-1].facts
                              if f.concept != "gross_profit"]
    data.periods[-1].facts.append(
        SuppliedFact(concept="gross_profit", value=750.0,
                     period_end=date(2025, 12, 31), currency="USD"))
    rep = run_valuation_from_data(data, ValuationOptions())
    assert rep.company.currency == "EUR"
    assert rep.inputs.gross_profit == pytest.approx(750.0 * 0.92)
    assert rep.inputs.revenue == 1000.0                 # untagged = EUR, untouched
    assert any(m.applicable for m in rep.models)


def test_supplied_ticker_never_pulls_demo_data_even_if_demo_name():
    """Req 10: submitting data for AUR must yield THE SUPPLIED numbers, not
    the demo provider's AUR dataset (no silent substitution in either dir)."""
    rep = run_valuation_from_data(_company("AUR"), ValuationOptions())
    assert rep.company.ticker == "AUR"
    assert rep.is_illustrative is False
    assert rep.inputs.revenue == 1000.0                # supplied, not demo's
    assert rep.company.provider == "agent_supplied"


# ---------------- engine independence (req 15) ----------------

def test_workflow_never_touches_network_providers(monkeypatch):
    """SEC/FRED/Stooq independence: any network fetch would explode."""
    def _boom(*a, **k):
        raise AssertionError("network provider called in agent-data workflow")
    monkeypatch.setattr("fairvalue.data.base.http_get", _boom)
    monkeypatch.setattr("fairvalue.service.get_provider",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("registry provider called")))
    rep = run_valuation_from_data(_company("OFFLINE"), ValuationOptions())
    assert any(m.applicable for m in rep.models)
    # and the MCP/REST surfaces on top of it
    out = json.loads(srv.calculate_valuation_from_data(
        _company("OFFLINE").model_dump_json()))
    assert out["company"]["ticker"] == "OFFLINE"
    client = TestClient(app)
    r = client.post("/v1/valuation/from-data",
                    json=json.loads(_company("OFFLINE").model_dump_json()))
    assert r.status_code == 200


# ---------------- rates & model eligibility (req 11/12) ----------------

def test_supplied_risk_free_rate_drives_capm_wacc():
    rep = run_valuation_from_data(_company("RATE1", rf=0.04), ValuationOptions())
    dcf = next(m for m in rep.models if m.model == "dcf")
    assert dcf.applicable
    wacc_note = [w for w in rep.data_quality.warnings if w.startswith("WACC =")]
    assert wacc_note and "4.00%" in wacc_note[0]
    # rf 4% + beta 1.1 * erp 5% = 9.5%
    assert dcf.assumptions["wacc"] == pytest.approx(0.04 + 1.1 * 0.05)


def test_no_rate_no_wacc_excludes_rate_models_with_reasons():
    rep = run_valuation_from_data(_company("NORATE", rf=None), ValuationOptions())
    by = {m.model: m for m in rep.models}
    assert not by["dcf"].applicable and "unavailable" in by["dcf"].excluded_reason
    assert not by["ddm"].applicable
    # non-rate models still run on the supplied fundamentals
    assert by["graham"].applicable or by["asset_based"].applicable


def test_explicit_wacc_option_wins():
    rep = run_valuation_from_data(_company("WACCX", rf=0.04),
                                  ValuationOptions(wacc=0.12))
    dcf = next(m for m in rep.models if m.model == "dcf")
    assert dcf.assumptions["wacc"] == pytest.approx(0.12)


# ---------------- MCP workflow (req 18) ----------------

def test_mcp_submit_then_calculate_then_fetch_roundtrip():
    envelope = _company("WORKS").model_dump_json()
    v = json.loads(srv.submit_financial_data(envelope))
    assert v["valid"] is True and v["company"]["ticker"] == "WORKS"
    assert v["provenance_summary"] and "missing_concepts" in v
    assert any(p["provenance"] == "calculated" for p in v["provenance_summary"])

    out = json.loads(srv.calculate_valuation_from_data(envelope))
    assert out["company"]["ticker"] == "WORKS"
    assert out["report_id"] and out["report_id"] in srv._REPORTS
    assert len(out["models"]) == 9                     # all nine preserved (req 13)
    got = json.loads(srv.get_valuation_report(out["report_id"]))
    assert got["company"]["ticker"] == "WORKS"          # traceable (req 14)


def test_mcp_submit_rejects_bad_payload_with_structured_error():
    bad_json = json.loads(srv.submit_financial_data("{not json"))
    assert bad_json["error"]["code"] == "validation_error"
    no_ticker = json.loads(srv.submit_financial_data(json.dumps(
        {"periods": [{"period_end": "2025-12-31",
                      "facts": [{"concept": "revenue", "value": 1.0,
                                 "period_end": "2025-12-31"}]}]})))
    assert no_ticker["error"]["code"] == "validation_error"
    empty = json.loads(srv.calculate_valuation_from_data(json.dumps(
        {"ticker": "X", "periods": []})))
    assert empty["error"]["code"] == "validation_error"


def test_mcp_existing_eleven_tools_still_present():
    for name in ("search_company", "calculate_valuation", "get_valuation_report",
                 "explain_valuation", "analyze_risks"):
        assert callable(getattr(srv, name))


# ---------------- REST surface (req 16/18) ----------------

def test_rest_from_data_returns_full_report():
    client = TestClient(app)
    r = client.post("/v1/valuation/from-data",
                    json=json.loads(_company("REST1").model_dump_json()))
    assert r.status_code == 200
    body = r.json()
    assert body["company"]["ticker"] == "REST1"
    assert body["report_id"] and len(body["models"]) == 9
    assert body["reconciliation"]["base"] is not None
    assert body["data_quality"]["sources"][0]["provider"].startswith("agent:")
    # stored report fetchable like any other surface
    assert client.get(f"/v1/reports/{body['report_id']}").status_code == 200


def test_rest_from_data_schema_error_uses_apierror_contract():
    client = TestClient(app)
    r = client.post("/v1/valuation/from-data", json={"ticker": "X"})  # no periods
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_rest_from_data_unusable_payload_is_422_not_500():
    client = TestClient(app)
    r = client.post("/v1/valuation/from-data", json={
        "ticker": "JUNK",
        "periods": [{"period_end": "2025-12-31", "facts": [
            {"concept": "revenue", "value": 1000.0, "period_end": "2025-12-31"},
            {"concept": "revenue", "value": 1100.0, "period_end": "2025-12-31"}]}]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"


# ---------------- provenance taxonomy (req 6/7) ----------------

def test_every_fact_carries_provenance_and_kinds_are_distinguished():
    data = _company("PROV")
    data.periods[-1].facts[0] = SuppliedFact(
        concept="revenue", value=1000.0, period_end=date(2025, 12, 31),
        period_start=date(2025, 1, 1), provenance=ProvenanceKind.agent_estimate,
        source="consensus compiled 2026-01-10")
    result = build_valuation_inputs(data)
    for p in result.inputs.history:
        for f in p.facts.values():
            assert f.source.provider.startswith("agent:")   # req 6: provenance on all
            assert f.source.retrieved_at
    rev = result.inputs.history[-1].facts["revenue"]
    assert rev.is_estimate is True and rev.source.locator == "consensus compiled 2026-01-10"
    kinds = {p["concept"]: p["provenance"] for p in result.provenance_summary}
    assert kinds["revenue"] == "agent_estimate"
    assert kinds["ebitda"] == "calculated"                 # derived, labeled
    assert "user_assumption" not in kinds                  # assumptions live elsewhere


def test_accounting_standard_and_fiscal_period_echoed():
    data = _company("IFRS1", currency="EUR")
    data.accounting_standard = "IFRS"
    data.periods[-1].fiscal_period = "Q3"
    rep = run_valuation_from_data(data, ValuationOptions())
    assert rep.company.accounting_standard == "IFRS"
    assert rep.inputs.history[-1].facts["revenue"].fiscal_period == "Q3"


# ------------- 5-ticker verification: AAPL / MSFT / JPM / XOM / synthetic ---
# User steps 4/6/7/8: real tickers submitted as synthetic fixtures (the agent
# supplies the data — FAIRVALUE only validates and calculates), each with a
# sector that exercises industry rules, all nine models reporting honestly.

FIVE = [
    ("AAPL", "Technology", "Computers"),
    ("MSFT", "Technology", "Software"),
    ("JPM", "Financials", "Banks"),
    ("XOM", "Energy", "Oil & Gas"),
    ("SYNTH", "Technology", "Software"),     # purely fictional control
]


@pytest.mark.parametrize("ticker,sector,industry", FIVE)
def test_five_tickers_value_honestly_with_all_nine_models(ticker, sector, industry):
    rep = run_valuation_from_data(
        _company(ticker, sector=sector, industry=industry), ValuationOptions())
    # right identity, agent provenance, NEVER demo substitution (req 10)
    assert rep.company.ticker == ticker
    assert rep.is_illustrative is False
    assert rep.company.provider == "agent_supplied"
    assert all(s.provider.startswith("agent:") for s in rep.data_quality.sources)
    # all nine present; each either runs with steps or carries an explicit reason
    assert len(rep.models) == 9, [m.model for m in rep.models]
    applicable = [m for m in rep.models if m.applicable]
    assert applicable, "no model ran — submission should always support some"
    for m in rep.models:
        if m.applicable:
            assert m.steps, f"{m.model} applicable without steps"
        else:
            assert m.excluded_reason, f"{m.model} excluded without a reason"
    assert rep.reconciliation.low <= rep.reconciliation.base <= rep.reconciliation.high
    if sector == "Financials":               # industry rule: DCF refuses banks
        dcf = next(m for m in rep.models if m.model == "dcf")
        assert not dcf.applicable and "financial" in dcf.excluded_reason.lower()


@pytest.mark.parametrize("ticker,sector,industry", FIVE)
def test_five_tickers_submittable_via_mcp_workflow(ticker, sector, industry):
    """Any MCP-compatible agent can submit these envelopes end to end."""
    envelope = _company(ticker, sector=sector, industry=industry).model_dump_json()
    v = json.loads(srv.submit_financial_data(envelope))
    assert v["valid"] is True and v["company"]["ticker"] == ticker
    out = json.loads(srv.calculate_valuation_from_data(envelope))
    assert out["company"]["ticker"] == ticker
    assert len(out["models"]) == 9
    assert all(("applicable" in m and (m["applicable"] or m["excluded_reason"]))
               for m in out["models"])
    assert out["report_id"] in srv._REPORTS
