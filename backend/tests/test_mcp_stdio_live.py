"""Live MCP stdio verification: spawn the real server as a subprocess and
exercise it through a real MCP client session (not by importing tool functions).

Each test owns its full stdio session lifecycle inside one anyio task (an
mcp 2.x/anyio quirk makes cross-task context teardown of stdio_client fail with
"exit cancel scope in a different task"), so the helper is an async context
manager rather than a fixture.
"""
import json
import os
import pathlib
import sys
from contextlib import asynccontextmanager

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "search_company", "get_financial_statements", "get_financial_metrics",
    "calculate_dcf", "calculate_valuation", "compare_competitors",
    "analyze_financial_health", "analyze_risks", "run_scenario_analysis",
    "explain_valuation", "get_valuation_report",
}
pytestmark = pytest.mark.anyio


def _params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "fairvalue.mcp_server"],
        env={"PYTHONPATH": str(pathlib.Path(__file__).resolve().parents[1]),
             "PYTHONIOENCODING": "utf-8",
             **{k: v for k, v in os.environ.items()
                if k in ("SYSTEMROOT", "PATH", "HOME", "TEMP", "TMP")}},
    )


@asynccontextmanager
async def _session():
    async with stdio_client(_params()) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_real_stdio_client_lists_all_11_tools():
    async with _session() as s:
        tools = {t.name for t in (await s.list_tools()).tools}
    assert EXPECTED_TOOLS <= tools, tools


async def test_real_stdio_calculate_valuation():
    async with _session() as s:
        result = await s.call_tool("calculate_valuation", {"ticker": "AUR", "demo": True})
        body = json.loads(result.content[0].text)
    assert not result.is_error
    assert body["company"]["ticker"] == "AUR"
    assert body["is_illustrative"] is True
    assert body["reconciliation"]["base"] is not None
    assert len(body["models"]) >= 5


async def test_real_stdio_structured_error_contract():
    """Lead's 6e28d44: ProviderError -> structured error JSON on every tool."""
    async with _session() as s:
        result = await s.call_tool("calculate_valuation", {"ticker": "NOPE"})
        body = json.loads(result.content[0].text)
    assert "error" in body and body["error"].get("code") == "company_not_found"


async def test_real_stdio_calculate_dcf_honors_wacc():
    """Lead's 6e28d44: calculate_dcf must not silently drop the wacc arg."""
    async with _session() as s:
        result = await s.call_tool("calculate_dcf",
                                   {"ticker": "AUR", "demo": True, "wacc": 0.123})
        body = json.loads(result.content[0].text)
    assert body["assumptions"]["wacc"] == pytest.approx(0.123)


async def test_real_stdio_search_and_report_roundtrip():
    async with _session() as s:
        found = json.loads((await s.call_tool(
            "search_company", {"query": "aurora", "demo": True})).content[0].text)
        rep = json.loads((await s.call_tool(
            "calculate_valuation", {"ticker": "HELI", "demo": True})).content[0].text)
        got = json.loads((await s.call_tool(
            "get_valuation_report", {"report_id": rep["report_id"]})).content[0].text)
    assert found[0]["ticker"] == "AUR"
    assert got["company"]["ticker"] == "HELI"
