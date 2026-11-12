"""FAIRVALUE AI MCP server (docs/ARCHITECTURE.md §8).

Exposes the same service layer as the REST API to MCP-compatible AI
assistants. Eleven fixed tools; every response is JSON-serialized pydantic
schemas — identical shapes to the REST API.

Run:  python -m fairvalue.mcp_server        (stdio transport)
Deps: pip install "fairvalue-ai[mcp]"  (the `mcp` package)
"""
from __future__ import annotations

import json
from typing import Any

try:  # mcp 2.x renamed FastMCP -> MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from fairvalue.core.schemas import DcfAssumptions
from fairvalue.data import ProviderError, get_provider
from fairvalue.service import (
    ValuationOptions,
    load_inputs,
    run_valuation,
    search_companies,
)

mcp = _Server(name="fairvalue-ai",
              instructions="FAIRVALUE AI: transparent stock valuation. Never present estimates as reported facts; every tool result carries assumptions, provenance and limitations.")

_REPORTS: dict[str, dict] = {}


def _d(model: Any) -> str:
    def _conv(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, (list, tuple)):
            return [_conv(o) for o in obj]
        if isinstance(obj, dict):
            return {k: _conv(v) for k, v in obj.items()}
        return obj
    return json.dumps(_conv(model), default=str)


def _run(ticker: str, *, demo: bool = False, price: float | None = None,
         peers: list[str] | None = None, models: list[str] | None = None,
         wacc: float | None = None):
    opts = ValuationOptions(demo=demo, price=price, peer_tickers=peers or [],
                            models=models, wacc=wacc)
    report = run_valuation(get_provider(demo=demo), ticker, opts)
    if report.report_id is None:
        import uuid
        report = report.model_copy(update={"report_id": f"r-{uuid.uuid4().hex[:12]}"})
    _REPORTS[report.report_id] = report.model_dump()
    return report


# ---- tools (plain functions; FastMCP decorators expose them) ----

def _e(exc: ProviderError) -> str:
    """Structured error payload — the documented contract for every tool."""
    return json.dumps({"error": {"code": exc.code, "message": exc.message}})


@mcp.tool()
def search_company(query: str, demo: bool = False) -> str:
    """Search companies by name or ticker. Returns CompanyProfile JSON list."""
    try:
        return _d(search_companies(query, demo=demo))
    except ProviderError as exc:
        return _e(exc)


@mcp.tool()
def get_financial_statements(ticker: str, demo: bool = False) -> str:
    """Normalized annual statements with provenance, missing concepts,
    restatement conflicts and structural validation errors."""
    try:
        fund = get_provider(demo=demo).get_fundamentals(ticker)
    except ProviderError as exc:
        return json.dumps({"error": {"code": exc.code, "message": exc.message}})
    return _d(fund)


@mcp.tool()
def get_financial_metrics(ticker: str, demo: bool = False) -> str:
    """Financial-health metrics and current market multiples."""
    from fairvalue.analysis import compute_health, compute_multiples
    try:
        loaded = load_inputs(get_provider(demo=demo), ticker, ValuationOptions(demo=demo))
    except ProviderError as exc:
        return _e(exc)
    return json.dumps({"health": _d(compute_health(loaded.inputs)),
                       "multiples": _d(compute_multiples(loaded.inputs))})


@mcp.tool()
def calculate_dcf(ticker: str, wacc: float | None = None, demo: bool = False) -> str:
    """DCF (FCFF) only, with full step-by-step derivation."""
    try:
        report = _run(ticker, demo=demo, models=["dcf"],
                      wacc=wacc if wacc and 0 < wacc < 1 else None)
    except ProviderError as exc:
        return _e(exc)
    dcf_result = next((m for m in report.models if m.model == "dcf"), None)
    return _d(dcf_result) if dcf_result else json.dumps({"error": "dcf not applicable"})


@mcp.tool()
def calculate_valuation(ticker: str, demo: bool = False, price: float | None = None,
                        peers: list[str] | None = None,
                        models: list[str] | None = None) -> str:
    """Full valuation: all suitable models + reconciliation + analysis +
    scenarios + explanation. The single entry point AI agents should call."""
    try:
        return _d(_run(ticker, demo=demo, price=price, peers=peers, models=models))
    except ProviderError as exc:
        return _e(exc)


@mcp.tool()
def compare_competitors(ticker: str, demo: bool = False) -> str:
    """Comparable-company analysis for the ticker (peers from the provider)."""
    try:
        report = _run(ticker, demo=demo, models=["comparables"])
    except ProviderError as exc:
        return _e(exc)
    return _d(next(m for m in report.models if m.model == "comparables"))


@mcp.tool()
def analyze_financial_health(ticker: str, demo: bool = False) -> str:
    """Profitability, liquidity, solvency and efficiency metrics."""
    from fairvalue.analysis import compute_health
    try:
        loaded = load_inputs(get_provider(demo=demo), ticker, ValuationOptions(demo=demo))
    except ProviderError as exc:
        return _e(exc)
    return _d(compute_health(loaded.inputs))


@mcp.tool()
def analyze_risks(ticker: str, demo: bool = False) -> str:
    """Altman Z screen, leverage and cash-flow risk flags with data gaps."""
    from fairvalue.analysis import compute_risks
    try:
        loaded = load_inputs(get_provider(demo=demo), ticker, ValuationOptions(demo=demo))
    except ProviderError as exc:
        return _e(exc)
    return _d(compute_risks(loaded.inputs))


@mcp.tool()
def run_scenario_analysis(ticker: str, demo: bool = False,
                          wacc: float | None = None) -> str:
    """Bear/base/bull DCF scenarios + WACC × terminal-growth sensitivity grid."""
    from fairvalue.analysis import run_scenarios
    try:
        loaded = load_inputs(get_provider(demo=demo), ticker, ValuationOptions(demo=demo))
    except ProviderError as exc:
        return _e(exc)
    w = wacc if wacc and 0 < wacc < 1 else loaded.rates.get("wacc")
    if w is None:
        return json.dumps({"error": {"code": "assumption_missing",
                                     "message": "no WACC derivable; pass wacc explicitly"}})
    return _d(run_scenarios(loaded.inputs, DcfAssumptions(wacc=w)))


@mcp.tool()
def explain_valuation(ticker: str, demo: bool = False) -> str:
    """Deterministic plain-language explanation of the valuation (no LLM)."""
    try:
        return _d(_run(ticker, demo=demo).explanation)
    except ProviderError as exc:
        return _e(exc)


@mcp.tool()
def get_valuation_report(report_id: str) -> str:
    """Fetch a previously generated valuation report by id (session memory)."""
    r = _REPORTS.get(report_id)
    if r is None:
        return json.dumps({"error": {"code": "not_found",
                                     "message": f"report '{report_id}' not found"}})
    return json.dumps(r, default=str)


def main() -> None:  # console entrypoint
    mcp.run()


if __name__ == "__main__":
    main()
