# FAIRVALUE AI

Financially defensible, mathematically tested stock valuation engine.

- **OpenCode** owns architecture, integration and release; **Deep AI Code** owns
  quant validation, SDK/CLI, persistence and dashboard (see `docs/AGENT_TASKS.md`).
- Architecture decisions in `docs/ARCHITECTURE.md` are **binding**
  (`docs/ARCHITECTURE_PROPOSAL.md` is a superseded draft).

## Quick start

```bash
cd backend
pip install -r requirements.txt
python -m pytest                             # full suite; live-SEC tests skip offline
python -m uvicorn api.main:app --reload      # REST API on :8000 (OpenAPI at /docs)
python -m fairvalue.mcp_server               # MCP server (stdio, 11 tools)
python -m fairvalue.cli search AAPL          # CLI (also installed as `fairvalue` via pip install -e .)
```

- **Persistence**: set `FAIRVALUE_DB_URL=sqlite:///fairvalue.db` (or a PostgreSQL URL)
  and valuations are stored; `/v1/reports` serves history. Unset = in-memory.
- **Auth**: set `FAIRVALUE_API_KEY` to require `X-API-Key` on `/v1/*`.
- **SEC data** comes from live EDGAR; demo mode (`--demo` / `demo=true`) is clearly
  labeled illustrative and never mixed with real facts.

## Dashboard

```bash
cd web
npm install
NEXT_PUBLIC_FAIRVALUE_API=http://127.0.0.1:8000 npm run dev   # http://localhost:3000
```

## Core guarantee

Every valuation explains *what* was calculated, *how*, with *which data*,
*which formulas*, and *which assumptions*. See `docs/FINANCIAL_METHODOLOGY.md`.
