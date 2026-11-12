"""INDEPENDENT AUDIT of the Streamable HTTP MCP transport.

Reproduces OpenCode's claims with my own client session and my own server
instance on my own port: tool listing, auth (missing/wrong/correct token),
a valuation call whose numbers must match the stdio transport's, and the
demo-data labeling. Any mismatch here is a release blocker.
"""
import json
import os
import pathlib
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager

import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

AUDIT_TOKEN = "audit-token-independent"

pytestmark = pytest.mark.anyio


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/mcp"


def _headers(token: str | None):
    h = {}
    if token is not None:
        h["Authorization"] = f"Bearer {token}"
    return h


@asynccontextmanager
async def _server(port: int):
    import fairvalue.mcp_http as mh
    os.environ["FAIRVALUE_MCP_TOKEN"] = AUDIT_TOKEN
    os.environ.pop("FAIRVALUE_MCP_ALLOW_ANON", None)
    config = uvicorn.Config(mh.create_app(), host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    import httpx
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    yield
    server.should_exit = True
    t.join(timeout=5)


@asynccontextmanager
async def _session(port: int, token: str | None):
    import httpx2
    async with httpx2.AsyncClient(headers=_headers(token)) as hc:
        async with streamable_http_client(_base_url(port), http_client=hc) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                yield s


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_audit_http_requires_bearer_token():
    port = _free_port()
    async with _server(port):
        # raw HTTP check (transport-independent): 401 + WWW-Authenticate on /mcp
        import httpx2
        r_none = httpx2.post(_base_url(port), content=b"")
        r_wrong = httpx2.post(_base_url(port), content=b"",
                              headers={"Authorization": "Bearer wrong-token"})
        assert r_none.status_code == 401 and r_wrong.status_code == 401
        assert "Bearer" in r_none.headers.get("www-authenticate", "")
        # through the MCP client: unauthenticated sessions must fail to initialize
        for tok in (None, "wrong-token"):
            with pytest.raises(Exception):
                async with _session(port, token=tok):
                    pass
        # correct token -> session works
        async with _session(port, token=AUDIT_TOKEN) as s:
            tools = {t.name for t in (await s.list_tools()).tools}
            assert len(tools) == 11


async def test_audit_http_valuation_matches_stdio():
    """Cross-transport parity, checked independently: run the same demo
    valuation over HTTP and over stdio and compare model values exactly."""
    import fairvalue.mcp_server as stdio_srv
    port = _free_port()
    async with _server(port):
        async with _session(port, token=AUDIT_TOKEN) as s:
            body_http = json.loads((await s.call_tool(
                "calculate_valuation", {"ticker": "AUR", "demo": True})).content[0].text)
    async with stdio_client_session() as s:
        body_stdio = json.loads((await s.call_tool(
            "calculate_valuation", {"ticker": "AUR", "demo": True})).content[0].text)
    http_vals = {m["model"]: m["value_per_share"] for m in body_http["models"] if m["applicable"]}
    stdio_vals = {m["model"]: m["value_per_share"] for m in body_stdio["models"] if m["applicable"]}
    assert http_vals == stdio_vals
    assert body_http["is_illustrative"] is True
    assert body_http["reconciliation"]["base"] == pytest.approx(
        body_stdio["reconciliation"]["base"], rel=1e-12)


@asynccontextmanager
async def stdio_client_session():
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
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s


async def test_audit_http_traceable_output_shape():
    """Every tool response must carry provenance/assumptions/steps — spot-check
    the three most data-heavy tools."""
    port = _free_port()
    async with _server(port):
        async with _session(port, token=AUDIT_TOKEN) as s:
            dcf = json.loads((await s.call_tool(
                "calculate_dcf", {"ticker": "AUR", "demo": True, "wacc": 0.11})).content[0].text)
            assert dcf["assumptions"]["wacc"] == pytest.approx(0.11)
            assert dcf["steps"] and dcf["formula"]
            stmt = json.loads((await s.call_tool(
                "get_financial_statements", {"ticker": "AUR", "demo": True})).content[0].text)
            fact = next(iter(stmt["periods"][-1]["facts"].values()))
            assert fact["source"]["provider"]
            scen = json.loads((await s.call_tool(
                "run_scenario_analysis", {"ticker": "AUR", "demo": True})).content[0].text)
            assert scen["bear"]["value_per_share"] < scen["bull"]["value_per_share"]
            assert scen["bear"]["applied_assumptions"]
