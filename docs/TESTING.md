# Testing guide

## Running everything

```bash
cd backend
python -m pytest            # 176 tests; exit 0 = green
```

- Tests use recorded real-filing fixtures (AAPL/JNJ/WMT/JPM/XOM/KO) and the
  demo provider — **no network needed**.
- A handful of live tests (SEC EDGAR end-to-end, live MCP stdio) **skip
  themselves automatically when offline** and run against the real network
  when available.

## Suite map

| Suite | Covers |
|---|---|
| `test_models_audit.py` | All 9 models against hand-derived known-answer values |
| `test_reconcile.py`, `test_risk_scenario.py`, `test_metrics.py` | Reconciliation, scenarios, ratio primitives |
| `test_edgar_regression.py`, `test_extra_issuers.py` | Real-filing extraction: taxonomy quirks, fiscal calendars, share-count fallbacks, honest missing-concept reporting |
| `test_api.py`, `test_release_audit_api.py` | REST contract: ApiError shapes, auth, CORS, rate limit, persistence wiring, price honesty |
| `test_mcp.py`, `test_mcp_stdio_live.py` | MCP tool contract + a **real MCP client over stdio** |
| `test_e2e_parity.py` | Engine vs REST vs MCP identical outputs (live when online) |
| `test_sdk.py`, `test_cli.py`, `test_db.py` | SDK against a real uvicorn thread; CLI; SQLAlchemy + real `alembic upgrade head` |

## Quality gates (current honest status)

| Gate | Command | Status |
|---|---|---|
| Pytest | `python -m pytest` | ✅ 176 passed |
| Frontend build | `cd web && npm run build` | ✅ passes (Next.js 16) |
| Dependency vulns (Python) | `pip-audit -r requirements.txt` | ✅ 0 known |
| Dependency vulns (JS) | `cd web && npm audit` | ✅ 0 known |
| Secret scan (full history) | `gitleaks git --log-opts="--all"` | ✅ 0 findings |
| Alembic migration | `alembic -c fairvalue/db/migrations/alembic.ini upgrade head` | ✅ applies `0001_reports`, stamped |
| REST/MCP parity | `pytest tests/test_e2e_parity.py` | ✅ |
| Ruff | `python -m ruff check .` | ⚠️ 92 pre-existing findings (see CI workflow comment) |
| Mypy | `python -m mypy fairvalue` | ⚠️ 48 pre-existing findings after enabling the pydantic plugin |

The last two are **documented debt, not merge gates** — CI runs pytest and the
dashboard build. Live-browser verification (search, company page, report
history) is manual; see [LIMITATIONS.md](LIMITATIONS.md).
