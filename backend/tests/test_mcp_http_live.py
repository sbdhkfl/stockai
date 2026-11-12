"""Remote MCP integration tests: real uvicorn server serving the Streamable
HTTP transport (fairvalue.mcp_http) exercised through a real MCP client, plus
a stdio-vs-HTTP parity check so both transports stay byte-compatible.

Auth is required on /mcp and open on /health; tokens are test constants, never
real credentials. The stdio side is additionally covered by
test_mcp_stdio_live.py (13 tools, error contract, wacc, report roundtrip).
"""
import json
import os
import pathlib
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

TEST_TOKEN = "test-token-not-a-real-secret"  # constant used only by this suite
EXPECTED_TOOLS = {
    "search_company", "get_financial_statements", "get_financial_metrics",
    "calculate_dcf", "calculate_valuation", "compare_competitors",
    "analyze_financial_health", "analyze_risks", "run_scenario_analysis",
    "explain_valuation", "get_valuation_report",
    "submit_financial_data", "calculate_valuation_from_data",
}
pytestmark = pytest.mark.anyio


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def http_base():
    """Real uvicorn thread serving mcp_http.create_app() with token auth."""
    os.environ["FAIRVALUE_MCP_TOKEN"] = TEST_TOKEN
    os.environ.pop("FAIRVALUE_MCP_ALLOW_ANON", None)
    from fairvalue.mcp_http import create_app
    port = _free_port()
    import uvicorn
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port,
                            log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):  # health is deliberately token-free
        try:
            if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("mcp_http server never became healthy")
    yield base
    server.should_exit = True
    thread.join(timeout=5)
    os.environ.pop("FAIRVALUE_MCP_TOKEN", None)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@asynccontextmanager
async def _session(base, token=TEST_TOKEN):
    import httpx2
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(headers=headers) as hc:
        async with streamable_http_client(f"{base}/mcp", http_client=hc) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                yield s


# ---- auth boundary (requirement: credentials never leak) ----

def test_health_is_open_and_leaks_nothing(http_base):
    r = httpx.get(f"{http_base}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["transport"] == "streamable-http"
    assert TEST_TOKEN not in r.text


def test_mcp_rejects_missing_token(http_base):
    r = httpx.post(f"{http_base}/mcp", json={}, timeout=5)
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("www-authenticate", "")
    assert r.json()["error"]["code"] == "unauthorized"
    assert TEST_TOKEN not in r.text


def test_mcp_rejects_wrong_token(http_base):
    r = httpx.post(f"{http_base}/mcp", json={},
                   headers={"Authorization": "Bearer wrong-token"},
                   timeout=5)
    assert r.status_code == 401
    assert TEST_TOKEN not in r.text


def test_x_api_key_header_also_accepted(http_base):
    # same header contract as the REST API: X-API-Key passes the auth boundary
    r = httpx.post(f"{http_base}/mcp",
                   headers={"X-API-Key": TEST_TOKEN},
                   json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {}}, timeout=5)
    # 400/406/422 are all "auth passed, payload rejected" — 401 would not be
    assert r.status_code != 401, r.text
    assert TEST_TOKEN not in r.text


def test_token_resolution_and_fail_closed(monkeypatch):
    from fairvalue import mcp_http
    for var in ("FAIRVALUE_MCP_TOKEN", "FAIRVALUE_API_KEY",
                "FAIRVALUE_MCP_ALLOW_ANON"):
        monkeypatch.delenv(var, raising=False)

    def req(headers):
        scope = {"type": "http", "method": "POST", "path": "/mcp",
                 "headers": [(k.lower().encode(), v.encode())
                             for k, v in headers.items()]}
        from starlette.requests import Request
        return Request(scope)

    assert not mcp_http._allowed(req({}))            # no token configured
    monkeypatch.setenv("FAIRVALUE_API_KEY", "fallback-tok")
    assert mcp_http._allowed(req({"Authorization": "Bearer fallback-tok"}))
    assert not mcp_http._allowed(req({"Authorization": "Bearer nope"}))
    assert not mcp_http._allowed(req({"X-API-Key": "nope"}))
    assert mcp_http._allowed(req({"X-API-Key": "fallback-tok"}))


def test_main_refuses_to_start_unsafe(monkeypatch):
    from fairvalue import mcp_http
    for var in ("FAIRVALUE_MCP_TOKEN", "FAIRVALUE_API_KEY",
                "FAIRVALUE_MCP_ALLOW_ANON", "FAIRVALUE_MCP_HOST"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit):            # no token, no anon flag
        mcp_http.main()
    monkeypatch.setenv("FAIRVALUE_MCP_ALLOW_ANON", "1")
    monkeypatch.setenv("FAIRVALUE_MCP_HOST", "0.0.0.0")
    with pytest.raises(SystemExit):            # anon never binds non-loopback
        mcp_http.main()


# ---- remote transport over real HTTP ----

async def test_http_lists_all_tools(http_base):
    async with _session(http_base) as s:
        tools = {t.name for t in (await s.list_tools()).tools}
    assert EXPECTED_TOOLS <= tools, tools


async def test_http_structured_error_contract(http_base):
    async with _session(http_base) as s:
        result = await s.call_tool("calculate_valuation",
                                   {"ticker": "NOPE", "demo": True})
        body = json.loads(result.content[0].text)
    assert body["error"]["code"] == "company_not_found"


async def test_http_every_tool_traceable(http_base):
    """Requirement: every exposed tool returns traceable, accurate data."""
    async with _session(http_base) as s:
        async def call(name, args):
            r = await s.call_tool(name, args)
            assert not r.is_error, (name, r)
            d = json.loads(r.content[0].text)
            assert "error" not in d, (name, d)
            return d

        hits = await call("search_company", {"query": "aurora", "demo": True})
        assert hits[0]["ticker"] == "AUR"

        st = await call("get_financial_statements", {"ticker": "AUR", "demo": True})
        assert st["periods"][-1]["facts"]
        src = next(iter(st["periods"][-1]["facts"].values()))
        assert src["source"]["provider"], src["source"]   # traceable to provider

        met = await call("get_financial_metrics", {"ticker": "AUR", "demo": True})
        assert "net_margin" in json.loads(met["health"])
        assert "pe" in json.loads(met["multiples"])

        dcf = await call("calculate_dcf", {"ticker": "AUR", "demo": True})
        assert dcf["model"] == "dcf" and dcf["steps"] and dcf["assumptions"]["wacc"]

        rep = await call("calculate_valuation", {"ticker": "AUR", "demo": True})
        assert rep["company"]["ticker"] == "AUR"
        assert rep["report_id"] and rep["is_illustrative"] is True
        assert rep["reconciliation"]["base"] is not None
        assert len(rep["models"]) >= 5 and rep["explanation"]["headline"]
        assert rep["data_quality"] is not None            # gaps surfaced, not hidden

        comp = await call("compare_competitors", {"ticker": "AUR", "demo": True})
        assert comp["model"] == "comparables"

        health = await call("analyze_financial_health", {"ticker": "AUR", "demo": True})
        assert "net_margin" in health

        risks = await call("analyze_risks", {"ticker": "AUR", "demo": True})
        assert "altman_zone" in risks and "data_gaps" in risks

        scen = await call("run_scenario_analysis", {"ticker": "AUR", "demo": True})
        assert scen["bear"]["value_per_share"] < scen["bull"]["value_per_share"]

        expl = await call("explain_valuation", {"ticker": "AUR", "demo": True})
        assert expl["methodology"] and expl["headline"]

        got = await call("get_valuation_report", {"report_id": rep["report_id"]})
        assert got["company"]["ticker"] == "AUR"           # roundtrip traceable

        # agent-supplied-data workflow tools (same envelope as REST from-data)
        envelope = json.dumps({
            "ticker": "ZZZX",
            "periods": [{"period_end": "2025-12-31", "period_start": "2025-01-01",
                         "facts": [{"concept": c, "value": v,
                                    "period_end": "2025-12-31",
                                    "period_start": "2025-01-01"}
                                   for c, v in {
                                       "revenue": 1000.0, "gross_profit": 750.0,
                                       "ebit": 150.0, "net_income": 90.0,
                                       "depreciation_amortization": 50.0,
                                       "capex": 60.0, "total_assets": 900.0,
                                       "total_liabilities": 300.0, "equity": 600.0,
                                       "cash": 100.0, "total_debt": 300.0,
                                       "operating_cash_flow": 120.0,
                                       "eps_diluted": 0.9,
                                       "shares_outstanding": 100.0,
                                       "dps": 0.9}.items()]}],
             "market": {"price": 20.0, "as_of": "2026-01-15",
                        "shares_outstanding": 100.0, "beta": 1.1},
             "risk_free_rate": 0.043})
        sub = await call("submit_financial_data", {"data": envelope})
        assert sub["valid"] is True and sub["company"]["ticker"] == "ZZZX"
        val = await call("calculate_valuation_from_data", {"data": envelope})
        assert val["company"]["ticker"] == "ZZZX" and len(val["models"]) == 9
        assert val["report_id"] and val["data_quality"]["sources"][0][
            "provider"].startswith("agent:")               # traceable, no provider


async def test_http_two_sessions_do_not_conflict(http_base):
    """Multiple AI clients: independent sessions, independent report ids."""
    async with _session(http_base) as a, _session(http_base) as b:
        ra = json.loads((await a.call_tool(
            "calculate_valuation", {"ticker": "AUR", "demo": True})
        ).content[0].text)
        rb = json.loads((await b.call_tool(
            "calculate_valuation", {"ticker": "HELI", "demo": True})
        ).content[0].text)
        assert ra["report_id"] != rb["report_id"]
        ga = json.loads((await a.call_tool(
            "get_valuation_report", {"report_id": ra["report_id"]})
        ).content[0].text)
        gb = json.loads((await b.call_tool(
            "get_valuation_report", {"report_id": rb["report_id"]})
        ).content[0].text)
        assert ga["company"]["ticker"] == "AUR"
        assert gb["company"]["ticker"] == "HELI"


async def test_stdio_and_http_parity(http_base):
    """Same tool, same input -> identical output on both transports."""
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "fairvalue.mcp_server"],
        env={"PYTHONPATH": str(pathlib.Path(__file__).resolve().parents[1]),
             "PYTHONIOENCODING": "utf-8",
             **{k: v for k, v in os.environ.items()
                if k in ("SYSTEMROOT", "PATH", "HOME", "TEMP", "TMP")}},
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            stdio_out = (await s.call_tool(
                "calculate_dcf", {"ticker": "AUR", "demo": True,
                                  "wacc": 0.123})).content[0].text
    async with _session(http_base) as s:
        http_out = (await s.call_tool(
            "calculate_dcf", {"ticker": "AUR", "demo": True,
                              "wacc": 0.123})).content[0].text
    assert json.loads(stdio_out) == json.loads(http_out)
