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
python -m fairvalue.mcp_server               # MCP server (stdio, 13 tools)
python -m fairvalue.mcp_http                 # MCP over Streamable HTTP (:8001/mcp, bearer token)
python -m fairvalue.cli search AAPL          # CLI (also installed as `fairvalue` via pip install -e .)
```

- **Persistence**: set `FAIRVALUE_DB_URL=sqlite:///fairvalue.db` (or a PostgreSQL URL)
  and valuations are stored; `/v1/reports` serves history. Unset = in-memory.
- **Auth**: set `FAIRVALUE_API_KEY` to require `X-API-Key` on `/v1/*`.
- **SEC data** comes from live EDGAR; demo mode (`--demo` / `demo=true`) is clearly
  labeled illustrative and never mixed with real facts.
- **Agent-supplied data**: any MCP agent can submit structured financials for
  *any* ticker (no allowlist) — validated, then valued with zero provider calls
  (`POST /v1/valuation/from-data`, MCP `submit_financial_data` →
  `calculate_valuation_from_data`, SDK `valuation_from_data`; canonical naming
  contract in [docs/AGENT_DATA.md](docs/AGENT_DATA.md)).

## Dashboard

```bash
cd web
npm install
NEXT_PUBLIC_FAIRVALUE_API=http://127.0.0.1:8000 npm run dev   # http://localhost:3000
```

## Core guarantee

Every valuation explains *what* was calculated, *how*, with *which data*,
*which formulas*, and *which assumptions*. See `docs/FINANCIAL_METHODOLOGY.md`.

## Documentation

| Doc | Contents |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Setup: backend, API, MCP, dashboard, CLI |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables, safe examples |
| [docs/API.md](docs/API.md) | REST endpoints, MCP tools, SDK & CLI reference |
| [docs/TESTING.md](docs/TESTING.md) | Test suite map + quality-gate status |
| [docs/MCP_CLIENTS.md](docs/MCP_CLIENTS.md) | Connecting Claude Desktop, VS Code, OpenCode, ChatGPT |
| [docs/MCP_DEPLOYMENT.md](docs/MCP_DEPLOYMENT.md) | Secure HTTPS deployment of the remote MCP endpoint |
| [docs/AGENT_DATA.md](docs/AGENT_DATA.md) | Agent-supplied financial data: envelope, provenance, validation, workflow |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Known limitations, honest inventory |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting & design notes |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Binding architecture & shared contracts |

## License

[MIT](LICENSE).
