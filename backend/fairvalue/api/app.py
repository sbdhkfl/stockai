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
Persistence: when FAIRVALUE_DB_URL is set, reports are stored via
fairvalue.db (SQLAlchemy) and /v1/reports reads from it; unset = in-memory.
"""
from __future__ import annotations

import hmac
import os
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
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

# Browser origins allowed to call the API (the dashboard runs on :3000).
# Explicit list, never "*": deployments widen it via FAIRVALUE_CORS_ORIGINS.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.environ.get(
            "FAIRVALUE_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if o.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_REPORTS: dict[str, ValuationReport] = {}
_RATE_WINDOW: dict[str, list[float]] = {}
RATE_LIMIT = int(os.environ.get("FAIRVALUE_RATE_LIMIT", "60"))
RATE_WINDOW_S = float(os.environ.get("FAIRVALUE_RATE_WINDOW_S", "60"))


def _err(code: str, message: str, detail: Any = None, status: int = 400):
    payload = ApiError(error={"code": code, "message": message,
                              "detail": "" if detail is None else str(detail)})
    return JSONResponse(status_code=status, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    # same ApiError contract as every other failure — never a bare FastAPI
    # {"detail": [...]} body
    return _err("validation_error", "request parameters failed validation",
                detail=exc.errors(), status=422)


def _provider(demo: bool):
    return get_provider(demo=demo)


# ---------------- optional report persistence ----------------

_db_cache: dict[str, Any] = {"url": None, "session_factory": None}


def _db_session():
    """SQLAlchemy session when FAIRVALUE_DB_URL is set, else None.

    Persistence failures never break a valuation request (best-effort with a
    server-side log line); the in-memory store remains the fallback.
    """
    url = os.environ.get("FAIRVALUE_DB_URL")
    if not url:
        return None
    try:
        if _db_cache["url"] != url:
            from fairvalue.db.session import create_all, get_engine, make_session

            engine = get_engine(url)
            create_all(engine)  # shortcut: create_all on first use — real
            # deployments run `alembic upgrade head` (fairvalue/db/migrations)
            _db_cache["url"] = url
            _db_cache["session_factory"] = lambda: make_session(engine)
        return _db_cache["session_factory"]()
    except Exception as exc:  # noqa: BLE001 — persistence must never 500 a report
        print(f"persistence unavailable: {exc}")
        return None


def _persist(report: ValuationReport) -> None:
    s = _db_session()
    if s is None:
        return
    try:
        from fairvalue.db.repo import save_report

        save_report(s, report)
    except Exception as exc:  # noqa: BLE001
        print(f"report persistence failed for {report.report_id}: {exc}")
    finally:
        s.close()


def _stored_list() -> list[dict] | None:
    s = _db_session()
    if s is None:
        return None
    try:
        from fairvalue.db.repo import list_reports

        return list_reports(s)
    except Exception as exc:  # noqa: BLE001
        print(f"report listing failed: {exc}")
        return None
    finally:
        s.close()


def _stored_get(report_id: str) -> dict | None:
    s = _db_session()
    if s is None:
        return None
    try:
        from fairvalue.db.repo import get_report

        r = get_report(s, report_id)
        return r.model_dump() if r else None
    except Exception as exc:  # noqa: BLE001
        print(f"report retrieval failed for {report_id}: {exc}")
        return None
    finally:
        s.close()


# ---------------- auth & rate limiting ----------------

@app.middleware("http")
async def auth_and_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/v1/") and os.environ.get("FAIRVALUE_API_KEY"):
        key = request.headers.get("X-API-Key") or ""
        # constant-time comparison: no timing oracle on the API key
        if not hmac.compare_digest(key, os.environ["FAIRVALUE_API_KEY"]):
            return _err("unauthorized", "missing or invalid X-API-Key", status=401)
    client = request.client.host if request.client else "anon"
    now = time.time()
    hits = [t for t in _RATE_WINDOW.get(client, []) if now - t < RATE_WINDOW_S]
    if len(hits) >= RATE_LIMIT:
        return _err("rate_limited", f"max {RATE_LIMIT} requests per {RATE_WINDOW_S:.0f}s",
                    status=429)
    hits.append(now)
    _RATE_WINDOW[client] = hits
    if len(_RATE_WINDOW) > 1024:  # bound memory if source addresses are spoofed
        for c, ts in list(_RATE_WINDOW.items()):
            if not any(now - t < RATE_WINDOW_S for t in ts):
                del _RATE_WINDOW[c]
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
    try:
        found = search_companies(ticker, demo=demo)
    except ProviderError as exc:
        return _err(exc.code, exc.message, status=502)
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
    _persist(report)
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
    _persist(report)
    return report.explanation.model_dump()


@app.get("/v1/reports")
def reports():
    stored = _stored_list()
    if stored is not None:
        return [{"report_id": r["report_id"], "company": r["ticker"],
                 "generated_at": r["generated_at"]} for r in stored]
    return [{"report_id": rid, "company": r.company.ticker,
             "generated_at": r.generated_at.isoformat()}
            for rid, r in sorted(_REPORTS.items(),
                                 key=lambda kv: kv[1].generated_at, reverse=True)]


@app.get("/v1/reports/{report_id}")
def report_by_id(report_id: str):
    stored = _stored_get(report_id)
    if stored is not None:
        return stored
    r = _REPORTS.get(report_id)
    if not r:
        return _err("not_found", f"report '{report_id}' not found (reports are "
                                 "in-memory in this MVP; re-request the valuation)", status=404)
    return r.model_dump()
