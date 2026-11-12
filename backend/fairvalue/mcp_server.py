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
    run_valuation_from_data,
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


def _parse_submission(data: str):
    """JSON envelope -> AgentSuppliedCompany. Every failure becomes a
    ProviderError so tools answer with the structured error contract."""
    from pydantic import ValidationError

    from fairvalue.agent_data import AgentSuppliedCompany
    try:
        payload = json.loads(data)
    except ValueError as exc:
        raise ProviderError("validation_error", f"data is not valid JSON: {exc}") from exc
    try:
        return AgentSuppliedCompany.model_validate(payload)
    except ValidationError as exc:
        e = exc.errors()[0]
        raise ProviderError(
            "validation_error",
            f"schema validation failed at {'.'.join(str(x) for x in e['loc'])}: {e['msg']}",
        ) from exc


@mcp.tool()
def submit_financial_data(data: str) -> str:
    """Validate structured financial data supplied by the agent for ANY ticker
    (no allowlist). Runs NO valuation — use it as the pre-flight step of the
    workflow: submit_financial_data -> calculate_valuation_from_data ->
    get_valuation_report.

    `data` is a JSON string: {"ticker": "ZZZX", "name"?, "sector"?, "industry"?,
    "currency"?="USD", "accounting_standard"?="US-GAAP", "is_illustrative"?=false,
    "periods": [{"period_end": "2025-12-31", "period_start"?, "fiscal_period"?
        ="FY"|"Q1".."Q4"|"TTM", "facts": [{"concept": "revenue", "value": 1000.0,
        "period_end": "2025-12-31", "period_start"?, "currency"?, "unit"?,
        "provenance"?="reported"|"agent_estimate"|"user_assumption", "source"?
        ="10-K p.42"}]}], "market"? {"price"?, "as_of"?, "shares_outstanding"?,
    "beta"?, "provenance"?, "source"?}, "risk_free_rate"?, "erp"?, "fx_rates"?,
    "peers"?, "transactions"?, "segments"?}
    Canonical concepts: revenue, gross_profit, ebit, net_income,
    operating_cash_flow, capex, depreciation_amortization, cash, total_debt,
    total_assets, total_liabilities, current_assets, current_liabilities,
    equity, shares_outstanding, eps_diluted, dps (ebitda/fcf are derived and
    must NOT be supplied). Returns valid + issues (errors/warnings),
    provenance_summary, derived_concepts and missing_concepts. Nothing is
    fabricated: rejected facts are reported, never guessed."""
    try:
        sub = _parse_submission(data)
        from fairvalue.agent_data import build_valuation_inputs
        result = build_valuation_inputs(sub)
    except ProviderError as exc:
        return _e(exc)
    except ValueError as exc:  # nothing usable after validation
        return _e(ProviderError("validation_failed", str(exc)))
    errors = [i for i in result.issues if i.severity == "error"]
    return json.dumps({
        "valid": True,
        "rejected_facts": len(errors),
        "company": {"ticker": sub.ticker, "name": sub.name or sub.ticker,
                    "currency": sub.currency,
                    "accounting_standard": sub.accounting_standard},
        "issues": [i.model_dump() for i in result.issues],
        "provenance_summary": result.provenance_summary,
        "derived_concepts": result.derived_concepts,
        "missing_concepts": result.missing_concepts,
        "next": "call calculate_valuation_from_data with the same data "
                "(rate-based models need risk_free_rate or wacc)",
    }, default=str)


@mcp.tool()
def calculate_valuation_from_data(
    data: str,
    wacc: float | None = None,
    price: float | None = None,
    models: list[str] | None = None,
) -> str:
    """Full valuation from agent-supplied structured data (same envelope as
    submit_financial_data). The agent supplies the facts; this tool validates
    them and runs ALL nine models, returning the standard ValuationReport
    (steps, assumptions, provenance, limitations, reconciliation, report_id —
    fetchable afterwards via get_valuation_report). No external data provider
    is contacted, and demo data is NEVER substituted for the supplied ticker.

    Optional: `wacc` (explicit discount rate, else CAPM from supplied
    risk_free_rate + market.beta, else rate-based models are excluded with
    explicit reasons), `price` (market-price override), `models` (subset)."""
    try:
        sub = _parse_submission(data)
        opts = ValuationOptions(wacc=wacc, price=price, models=models)
        report = run_valuation_from_data(sub, opts)
    except ProviderError as exc:
        return _e(exc)
    except ValueError as exc:  # schema/valuation options/empty submission
        return _e(ProviderError("validation_failed", str(exc)))
    if report.report_id is None:
        import uuid
        report = report.model_copy(update={"report_id": f"r-{uuid.uuid4().hex[:12]}"})
    assert report.report_id is not None   # narrowed for mypy (model_copy hides it)
    _REPORTS[report.report_id] = report.model_dump()   # same store shape as _run()
    return _d(report)


def main() -> None:  # console entrypoint
    mcp.run()


if __name__ == "__main__":
    main()
