"""FastAPI application implementing docs/ARCHITECTURE.md §7.

Endpoints:
  GET  /health
  GET  /v1/companies/search?q=
  GET  /v1/companies/{ticker}
  GET  /v1/companies/{ticker}/statements
  GET  /v1/companies/{ticker}/metrics
  GET  /v1/companies/{ticker}/health
  GET  /v1/companies/{ticker}/risks
  GET  /v1/companies/{ticker}/valuation      (params: price, peers, models, demo)
  POST /v1/companies/{ticker}/scenarios
  GET  /v1/companies/{ticker}/explain
  GET  /v1/reports  ·  GET /v1/reports/{id}

Errors: {"error": {"code", "message", "detail"}} (ApiError contract).
Auth: when FAIRVALUE_API_KEY is set, X-API-Key is required on /v1/*.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from fairvalue.core.schemas import ApiError, DcfAssumptions, ValuationReport
from fairvalue.data import ProviderError, get_provider
from fairvalue.data.base import ProviderError as _PE  # re-exported alias safety
from fairvalue.service import (
    ValuationOptions,
    load_inputs,
    run_valuation,
    search_companies,
)

app = FastAPI(
    title="FAIRVALUE AI",
    version="1.0.0",
    description=(
        "Transparent, model-independent stock valuation. Every response carries "
        "assumptions, per-model steps, provenance and limitations. Nothing here "
        "is investment advice."
    ),
)

_REPORTS: dict[str, ValuationReport] = {}
_RATE_WINDOW: dict[str, list[float]] = {}
RATE_LIMIT = int(os.environ.get("FAIRVALUE_RATE_LIMIT", "60"))
RATE_WINDOW_S = float(os.environ.get("FAIRVALUE_RATE_WINDOW_S", "60"))


def _err(code: str, message: str, detail: Any = None, status: int = 400):
    payload = ApiError(error={"code": code, "message": message,
                              "detail": "" if detail is None else str(detail)})
    return JSONResponse(status_code=status, content=payload.model_dump())


def _provider(demo: bool):
    return get_provider(demo=demo)


# ---------------- auth & rate limiting ----------------

@app.middleware("http")
async def auth_and_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/v1/") and os.environ.get("FAIRVALUE_API_KEY"):
        key = request.headers.get("X-API-Key")
        if key != os.environ["FAIRVALUE_API_KEY"]:
            return _err("unauthorized", "missing or invalid X-API-Key", status=401)
    client = request.client.host if request.client else "anon"
    now = time.time()
    hits = [t for t in _RATE_WINDOW.get(client, []) if now - t < RATE_WINDOW_S]
    if len(hits) >= RATE_LIMIT:
        return _err("rate_limited", f"max {RATE_LIMIT} requests per {RATE_WINDOW_S:.0f}s",
                    status=429)
    hits.append(now)
    _RATE_WINDOW[client] = hits
    return await call_next(request)


# ---------------- basic endpoints ----------------

@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/v1/companies/search")
def companies_search(q: str = Query(..., min_length=1), demo: bool = False):
    try:
        return [c.model_dump() for c in search_companies(q, demo=demo)]
    except ProviderError as exc:
        return _err(exc.code, exc.message, status=502)


@app.get("/v1/companies/{ticker}")
def company(ticker: str, demo: bool = False):
    found = search_companies(ticker, demo=demo)
    exact = [c for c in found if c.ticker.upper() == ticker.upper()]
    if not exact:
        return _err("not_found", f"company '{ticker}' not found", status=404)
    return exact[0].model_dump()


@app.get("/v1/companies/{ticker}/statements")
def statements(ticker: str, demo: bool = False):
    try:
        fund = _provider(demo).get_fundamentals(ticker)
    except ProviderError as exc:
        return _err(exc.code, exc.message, status=502)
    return {
        "company": fund.company.model_dump(),
        "periods": [
            {"fiscal_year": p.fiscal_year, "period_end": str(p.period_end),
             "facts": {k: v.model_dump() for k, v in p.facts.items()}}
            for p in fund.periods
        ],
        "missing_concepts": fund.missing_concepts,
        "conflicts": fund.conflicts,
        "validation_errors": list(getattr(fund, "validation_errors", [])),
    }


def _loaded(ticker: str, opts: ValuationOptions):
    try:
        return load_inputs(_provider(opts.demo), ticker, opts)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@app.get("/v1/companies/{ticker}/metrics")
def metrics(ticker: str, demo: bool = False):
    from fairvalue.analysis import compute_health, compute_multiples
    loaded = _loaded(ticker, ValuationOptions(demo=demo))
    return {"health": compute_health(loaded.inputs).model_dump(),
            "multiples": compute_multiples(loaded.inputs).model_dump()}


@app.get("/v1/companies/{ticker}/health")
def health_metrics(ticker: str, demo: bool = False):
    from fairvalue.analysis import compute_health
    return compute_health(_loaded(ticker, ValuationOptions(demo=demo)).inputs).model_dump()


@app.get("/v1/companies/{ticker}/risks")
def risks(ticker: str, demo: bool = False):
    from fairvalue.analysis import compute_risks
    return compute_risks(_loaded(ticker, ValuationOptions(demo=demo)).inputs).model_dump()


@app.get("/v1/companies/{ticker}/valuation")
def valuation(
    ticker: str,
    price: float | None = Query(None, gt=0),
    peers: list[str] = Query(default=[]),
    models: list[str] | None = Query(None),
    demo: bool = False,
    run_scenarios: bool = True,
):
    if peers and len(peers) == 1 and "," in peers[0]:
        peers = peers[0].split(",")
    opts = ValuationOptions(price=price, peer_tickers=peers, models=models,
                            demo=demo, run_scenarios=run_scenarios)
    try:
        report = run_valuation(_provider(demo), ticker, opts)
    except ProviderError as exc:
        return _err(exc.code, exc.message, status=502)
    if report.report_id is None:
        report = report.model_copy(update={"report_id": f"r-{uuid.uuid4().hex[:12]}"})
    _REPORTS[report.report_id] = report
    return report.model_dump()


@app.post("/v1/companies/{ticker}/scenarios")
def scenarios(ticker: str, opts: ValuationOptions | None = None):
    opts = opts or ValuationOptions()
    loaded = _loaded(ticker, opts)
    from fairvalue.analysis import run_scenarios as _rs
    a = loaded.rates.get("wacc")
    if a is None:
        return _err("assumption_missing",
                    "no WACC derivable (risk-free rate unavailable); supply opts.wacc",
                    status=422)
    base = DcfAssumptions(wacc=a)
    return _rs(loaded.inputs, base).model_dump()


@app.get("/v1/companies/{ticker}/explain")
def explain(ticker: str, demo: bool = False):
    report = run_valuation(_provider(demo), ticker, ValuationOptions(demo=demo))
    if report.report_id is None:
        report = report.model_copy(update={"report_id": f"r-{uuid.uuid4().hex[:12]}"})
    _REPORTS[report.report_id] = report
    return report.explanation.model_dump()


@app.get("/v1/reports")
def reports():
    return [{"report_id": rid, "company": r.company.ticker,
             "generated_at": r.generated_at.isoformat()}
            for rid, r in sorted(_REPORTS.items(),
                                 key=lambda kv: kv[1].generated_at, reverse=True)]


@app.get("/v1/reports/{report_id}")
def report_by_id(report_id: str):
    r = _REPORTS.get(report_id)
    if not r:
        return _err("not_found", f"report '{report_id}' not found (reports are "
                                 "in-memory in this MVP; re-request the valuation)", status=404)
    return r.model_dump()
