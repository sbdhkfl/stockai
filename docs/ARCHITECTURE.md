# FAIRVALUE AI — Architecture & Shared Interfaces (APPROVED)

Status: **APPROVED by Lead Architect** — binding for all agents.
Last updated: 2026-11-11

## 1. Product boundaries

| Product | Path | Rule |
|---|---|---|
| FAIRVALUE CORE | `backend/fairvalue/` | Pure Python engine. **Never imports an LLM.** Deterministic, reproducible. |
| FAIRVALUE API | `backend/fairvalue/api/` (+ entrypoint `backend/api/main.py`) | REST, OpenAPI, auth, rate limit. Thin layer over CORE. |
| FAIRVALUE SKILL | `skill/SKILL.md` | Instructions for AI assistants. No code execution inside the engine. |
| Dashboard | `web/` | Next.js. Displays CORE output; zero valuation logic in the frontend. |

## 2. Approved repository structure

```
stockai/
├── backend/
│   ├── pyproject.toml            # single Python distribution: fairvalue-ai
│   ├── api/main.py               # deployment entrypoint shim (uvicorn api.main:app)
│   ├── fairvalue/
│   │   ├── core/schemas.py       # SHARED CONTRACT — all data types (see §3)
│   │   ├── data/                 # provider interfaces + normalization
│   │   │   ├── base.py           # FinancialDataProvider protocol
│   │   │   ├── normalize.py      # dedupe, conflict detection, missing-data tracking
│   │   │   ├── edgar.py          # SEC EDGAR (real fundamentals)
│   │   │   ├── fred.py           # FRED macro (risk-free rate, inflation, GDP…)
│   │   │   ├── stooq.py          # free EOD price history
│   │   │   └── demo.py           # ILLUSTRATIVE data — explicitly labeled, never silent
│   │   ├── valuation/            # one file per model, all pure functions
│   │   │   ├── dcf.py ddm.py comparables.py precedents.py
│   │   │   ├── residual_income.py epv.py graham.py asset_based.py sotp.py
│   │   │   └── reconcile.py      # model selection + reconciliation layer
│   │   ├── analysis/             # health, multiples, growth, risk, scenario
│   │   ├── explain.py            # deterministic AI-analyst text (no LLM)
│   │   ├── service.py            # orchestration: providers → inputs → models → report
│   │   ├── db/                   # SQLAlchemy models, session, repository (SQLite/PostgreSQL)
│   │   ├── api/                  # FastAPI app, routes, auth, rate limiting
│   │   ├── sdk/                  # Python client SDK (httpx)
│   │   ├── mcp_server.py         # MCP tools (official `mcp` package)
│   │   └── cli.py                # `fairvalue` console command
│   └── tests/                    # pytest; offline (demo provider) by default
├── web/                          # Next.js dashboard
├── skill/SKILL.md                # Agent Skill
├── docs/                         # ARCHITECTURE, METHODOLOGY, API, MCP, AGENT_TASKS…
├── .github/workflows/ci.yml
├── Dockerfile  docker-compose.yml
└── README.md CONTRIBUTING.md SECURITY.md CHANGELOG.md LICENSE
```

## 3. Shared data contract (`fairvalue.core.schemas`)

All agents MUST consume these Pydantic models; no parallel type definitions.

- `SourceRef` — provenance (provider, locator, retrieved_at, license). **Every Fact carries one.**
- `Fact` — one normalized financial number: `concept, value, unit, period_end, fiscal_year,
  fiscal_period, is_estimate, form, filed_at, is_illustrative, source`
- `CompanyProfile`, `PeriodFinancials`, `Fundamentals` (with `missing_concepts`, `conflicts`)
- `MarketData` (`is_illustrative` flag, optional price history)
- `ComparableCompany`, `PrecedentTransaction`, `Segment`
- `ValuationInputs` — assembled view handed to every model (latest FY metrics + history +
  peers + transactions + segments + rates). `None` means **missing**, never zero.
- Per-model assumption models: `DcfAssumptions, DdmAssumptions, ComparablesAssumptions,
  PrecedentAssumptions, ResidualIncomeAssumptions, EpvAssumptions, GrahamAssumptions,
  AssetBasedAssumptions, SotpAssumptions` — all validated (e.g. `terminal_growth < wacc`).
- `ModelResult` — `model, applicable, value_per_share, confidence, suitability,
  assumptions, formula, steps[], limitations[], warnings[], excluded_reason`
- `Reconciliation`, `DataQuality`, `ScenarioSet`, `HealthMetrics`, `ValuationMultiples`,
  `GrowthAnalysis`, `RiskAssessment`, `ValuationExplanation`, `ValuationReport`

### Canonical concepts
`revenue, gross_profit, ebit, ebitda, net_income, operating_cash_flow, capex,
depreciation_amortization, cash, total_debt, total_assets, total_liabilities,
current_assets, current_liabilities, equity, shares_outstanding, eps_diluted, dps`
Convention: `capex` is a **positive magnitude**; flows are annual (`fiscal_period="FY"`).

### Model contract
Every model is a pure function:
```python
def calculate(inputs: ValuationInputs, assumptions: XxxAssumptions) -> ModelResult
```
- If required data is missing → return `applicable=False, excluded_reason="..."`. **Never raise, never guess.**
- `steps` must show the arithmetic; `formula` documents the equation; `limitations` always populated.
- Unit tests must use hand-computed expected values.

## 4. Non-negotiable rules

1. Never fabricate financial data. Missing → `None` + entry in `DataQuality.missing`.
2. Never silently substitute estimates for reported values (`is_estimate` is explicit).
3. Never hardcode financial results; never average incompatible models without the
   reconciliation layer documenting family grouping, suitability weights and exclusions.
4. No secrets in the repo; keys via environment only (`FAIRVALUE_API_KEY`, `FRED_API_KEY` optional).
5. Illustrative data (`demo.py`) is always labeled `is_illustrative=True` end-to-end,
   including API responses and the dashboard.
6. Provider licensing and rate limits respected: SEC requires a descriptive `User-Agent`,
   requests are cached in-process with backoff on 429/503.

## 5. Interface ownership (anti-collision rules)

| Area | Owner | Notes |
|---|---|---|
| `core/schemas.py` | Lead Architect | Changes require review note in `docs/AGENT_TASKS.md` |
| `valuation/*` (9 models) | Deep AI Code | One file per model; Lead owns `reconcile.py` |
| `analysis/*`, `explain.py` | Lead Architect | |
| `data/edgar.py`, `data/fred.py` | Deep AI Code | May not change `normalize.py` contract |
| `api/*`, `db/*`, `service.py`, `sdk`, `cli`, `mcp_server.py` | Lead Architect | |
| `docs/FINANCIAL_METHODOLOGY.md` | Deep AI Code (drafts), Lead (approves) | |
| `web/*` | Lead Architect | |

Never edit a file owned by another agent concurrently; post the proposed diff in `docs/AGENT_TASKS.md`.

## 6. Data flow

```
providers (edgar/fred/stooq/demo) → normalize (dedupe/conflicts/missing)
  → ValuationInputs (service.py)
  → 9 models (pure) → reconcile.py (applicability → suitability → families → range)
  → analysis (health/multiples/growth/risk) → scenario engine (bear/base/bull + sensitivity)
  → explain.py (deterministic narrative)
  → ValuationReport → REST API / MCP / SDK / CLI / dashboard
```

## 7. API surface (v1)

`GET /health` · `GET /v1/companies/search?q=` · `GET /v1/companies/{ticker}` ·
`GET /v1/companies/{ticker}/statements` · `GET /v1/companies/{ticker}/metrics` ·
`GET /v1/companies/{ticker}/health` · `GET /v1/companies/{ticker}/risks` ·
`GET /v1/companies/{ticker}/valuation` (params: `price, peers, models, demo`) ·
`POST /v1/companies/{ticker}/scenarios` · `GET /v1/companies/{ticker}/explain` ·
`GET|POST /v1/reports` · `GET /v1/reports/{id}` · OpenAPI at `/docs` + `/openapi.json`

Auth: if `FAIRVALUE_API_KEY` is set, `X-API-Key` required on `/v1/*`. Rate limit: fixed-window
per client IP (env-configurable). Errors: `{"error": {"code", "message", "detail"}}`.

## 8. MCP tool list (fixed)

`search_company, get_financial_statements, get_financial_metrics, calculate_dcf,
calculate_valuation, compare_competitors, analyze_financial_health, analyze_risks,
run_scenario_analysis, explain_valuation, get_valuation_report`
