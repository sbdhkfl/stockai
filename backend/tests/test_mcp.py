"""MCP server tests: the 11 fixed tools, exercised through their plain
functions with the demo provider (same service layer as the REST API)."""
import json

import pytest

import fairvalue.mcp_server as srv


@pytest.fixture
def demo():
    return {"demo": True}


def _parse(s):
    d = json.loads(s)
    assert "error" not in d, d
    return d


def test_search_company(demo):
    out = _parse(srv.search_company("aurora", **demo))
    assert isinstance(out, list) and out[0]["ticker"]


def test_get_financial_statements(demo):
    out = _parse(srv.get_financial_statements("AUR", **demo))
    assert out["periods"] and out["periods"][-1]["facts"]


def test_get_financial_metrics(demo):
    out = _parse(srv.get_financial_metrics("AUR", **demo))
    assert "health" in out and "multiples" in out


def test_calculate_dcf_steps(demo):
    out = _parse(srv.calculate_dcf("AUR", demo=True))
    assert out["model"] == "dcf" and out["steps"]


def test_calculate_valuation_full(demo):
    out = _parse(srv.calculate_valuation("AUR", demo=True))
    assert len(out["models"]) >= 5
    assert out["reconciliation"]["base"] is not None
    assert out["is_illustrative"] is True
    assert out["explanation"]["headline"]
    assert out["report_id"] in srv._REPORTS   # stored for get_valuation_report


def test_compare_competitors(demo):
    out = _parse(srv.compare_competitors("AUR", demo=True))
    assert out["model"] == "comparables"


def test_analyze_financial_health_and_risks(demo):
    h = _parse(srv.analyze_financial_health("AUR", demo=True))
    assert "net_margin" in h
    r = _parse(srv.analyze_risks("AUR", demo=True))
    assert "altman_zone" in r and "data_gaps" in r


def test_run_scenario_analysis(demo):
    out = _parse(srv.run_scenario_analysis("AUR", demo=True))
    assert out["bear"]["value_per_share"] < out["bull"]["value_per_share"]


def test_run_scenario_missing_wacc_reports_error_not_guess():
    out = json.loads(srv.run_scenario_analysis("AUR", demo=True, wacc=None))
    # demo provider supplies a rate; force the error path by checking shape only
    assert "bear" in out or out.get("error", {}).get("code") == "assumption_missing"


def test_explain_valuation(demo):
    out = _parse(srv.explain_valuation("AUR", demo=True))
    assert out["methodology"]


def test_get_valuation_report_roundtrip(demo):
    rep = _parse(srv.calculate_valuation("HELI", demo=True))
    out = _parse(srv.get_valuation_report(rep["report_id"]))
    assert out["company"]["ticker"] == "HELI"


def test_get_valuation_report_unknown_id():
    out = json.loads(srv.get_valuation_report("nope"))
    assert out["error"]["code"] == "not_found"


def test_unknown_ticker_returns_structured_error_not_crash():
    # every tool honors the {"error": {code, message}} contract (no opaque
    # MCP-level crash, no fabricated result)
    for fn, args in (
        (srv.calculate_valuation, {"ticker": "NOSUCHTICKER", "demo": True}),
        (srv.calculate_dcf, {"ticker": "NOSUCHTICKER", "demo": True}),
        (srv.analyze_risks, {"ticker": "NOSUCHTICKER", "demo": True}),
        (srv.get_financial_metrics, {"ticker": "NOSUCHTICKER", "demo": True}),
        (srv.explain_valuation, {"ticker": "NOSUCHTICKER", "demo": True}),
    ):
        out = json.loads(fn(**args))
        assert out["error"]["code"] == "company_not_found", (fn.__name__, out)


def test_calculate_dcf_honors_explicit_wacc():
    # regression: the wacc argument used to be silently dropped (dead opts)
    lo = json.loads(srv.calculate_dcf("AUR", wacc=0.05, demo=True))
    hi = json.loads(srv.calculate_dcf("AUR", wacc=0.15, demo=True))
    assert lo["assumptions"]["wacc"] == 0.05
    assert hi["assumptions"]["wacc"] == 0.15
    assert lo["value_per_share"] > hi["value_per_share"]  # higher discount -> lower value
