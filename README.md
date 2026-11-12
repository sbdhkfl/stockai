# FAIRVALUE AI

Financially defensible, mathematically tested stock valuation engine.

- **OpenCode** owns architecture, integration and release; **Deep AI Code** owns
  quant validation, SDK/CLI, persistence and dashboard (see `docs/AGENT_TASKS.md`).
- Architecture decisions in `docs/ARCHITECTURE.md` are **binding**
  (`docs/ARCHITECTURE_PROPOSAL.md` is a superseded draft).

## Use FAIRVALUE AI with any AI agent

You can introduce FAIRVALUE AI to an AI agent by sharing this repository:

**Repository:** https://github.com/sbdhkfl/stockai

Tell the agent to:

1. Read the repository's `README.md` and `docs/AGENT_DATA.md`.
2. Download the Agent Skill at [`skill/SKILL.md`](skill/SKILL.md)
   (raw file: https://raw.githubusercontent.com/sbdhkfl/stockai/release/github-prep/skill/SKILL.md)
   and install/load it using that agent's supported Agent Skills workflow.
3. Follow the skill and the agent-supplied-data workflow in `docs/AGENT_DATA.md`.
4. Check whether FAIRVALUE AI's MCP server or API is actually connected. If it
   is not, explain the required setup; do not claim to have run the engine.

The repository link and skill teach the agent how to use FAIRVALUE AI; they do
**not** automatically connect a remote calculation engine. To execute valuations,
the agent must have access to a running FAIRVALUE AI MCP server or REST API.
See [MCP client setup](docs/MCP_CLIENTS.md) and
[secure remote deployment](docs/MCP_DEPLOYMENT.md).

### Universal prompt (any AI agent, any valid ticker)

Copy this prompt into any AI agent after sharing the repository link:

```text
Use FAIRVALUE AI from this GitHub repository:
https://github.com/sbdhkfl/stockai

First, read the README and docs/AGENT_DATA.md. Download and load the Agent
Skill from skill/SKILL.md using the skill-installation method supported by
your environment. Follow its instructions.

Your task is to analyze and estimate the intrinsic/fair value of the ticker
I provide. This workflow must work for ANY valid publicly traded ticker,
not just a hardcoded list or example company.

ARCHITECTURE RULE — KEEP THESE RESPONSIBILITIES SEPARATE:
- YOU, the AI agent, are responsible for all research and data retrieval.
  Retrieve the company's financial statements, relevant historical periods,
  current market inputs, industry/sector information, peer data and other
  inputs needed for suitable valuation methods.
- FAIRVALUE AI is the deterministic validation and calculation engine.
  Submit the retrieved, structured data to FAIRVALUE AI; let it validate
  inputs, determine model eligibility, calculate results and reconcile them.
- Do not make FAIRVALUE AI depend on its own SEC/FRED/Stooq or other external
  data-provider access for this agent-supplied-data workflow.

RESEARCH AND DATA RULES:
1. Resolve the supplied ticker to the correct company and exchange. If it is
   invalid or ambiguous, ask for clarification instead of guessing.
2. Retrieve current, reliable source data. Prefer official filings, company
   investor-relations releases and reputable market-data sources. Collect
   multiple fiscal years and the latest available interim period when useful.
3. Collect source names/URLs or document identifiers, reporting periods,
   publication/filing dates, retrieval timestamps, currencies and units for
   every fact. Preserve the original source context.
4. Clearly classify each input as a reported fact, your estimate, a user
   assumption, or a value calculated by the engine. Never label an estimate
   as reported data.
5. Do not invent, silently fill, or substitute missing facts with demo data.
   Do not silently mix currencies, accounting periods or units. Retrieve
   documented FX rates when conversion is required.
6. Include market inputs such as share price and shares outstanding with
   explicit as-of dates. Identify assumptions such as WACC, cost of equity,
   terminal growth and equity risk premium separately from reported facts.
7. Retrieve peer, transaction and segment data only when needed for the
   relevant models, and document how peers/transactions were selected.
8. If a required input is unavailable, disclose the gap. Do not fabricate it
   just to make a model run.

SUBMISSION AND VALUATION:
1. Build the structured input envelope defined in docs/AGENT_DATA.md. Support
   the company's actual reporting currency, accounting standard and available
   fiscal periods. Do not impose a ticker allowlist.
2. If the MCP tools are connected, use submit_financial_data as a validation
   preflight, then calculate_valuation_from_data with the validated data and
   appropriate explicit options. Retrieve the finished report with
   get_valuation_report when a report_id is returned.
3. If using REST instead, follow the documented POST /v1/valuation/from-data
   contract. Do not invent endpoints or tool names.
4. Run all models that the engine determines are applicable. FAIRVALUE AI
   supports nine model families: DCF, DDM, comparable companies, precedent
   transactions, residual income, earnings power value, Graham-style,
   adjusted NAV and sum-of-the-parts. Do not force unsuitable models; report
   every excluded model and the engine's reason.
5. Do not average model outputs blindly. Preserve the engine's reconciliation,
   scenario ranges, assumptions, calculation steps, warnings and limitations.

OUTPUT:
- Identify the company, ticker, exchange, currency and data as-of date.
- Summarize the key sourced financial facts and their periods.
- Report which models ran and which were excluded, with reasons.
- Show the per-model results, fair-value range and bear/base/bull scenarios
  when the engine provides them.
- Explain the most important assumptions, sensitivities, risks, data gaps
  and source limitations.
- Clearly distinguish the current market price from estimated intrinsic value.
- State that valuation outputs are estimates conditional on assumptions, not
  guaranteed future prices or personalized investment advice.

IMPORTANT EXECUTION HONESTY:
If the FAIRVALUE AI MCP server/API is not connected or unreachable, do NOT
pretend you submitted data or ran the engine. You may provide a clearly
separated preliminary analysis, but label it as not calculated by FAIRVALUE AI
and explain exactly what connection/setup is missing. Never fabricate tool
results, report IDs, model outputs or successful tests.

Start by asking me for the ticker if I have not provided one.
```

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
- **Provider-driven mode**: the original provider-backed workflows can retrieve
  SEC EDGAR data; demo mode (`--demo` / `demo=true`) is clearly labeled
  illustrative and never mixed with real facts.
- **Agent-supplied-data mode (recommended for external AI agents)**: the agent
  retrieves all financial/market data and submits structured facts for *any*
  ticker. FAIRVALUE AI validates and calculates without making provider calls:
  `POST /v1/valuation/from-data`, MCP
  `submit_financial_data` → `calculate_valuation_from_data`, SDK
  `valuation_from_data`. See [docs/AGENT_DATA.md](docs/AGENT_DATA.md).

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
| [skill/SKILL.md](skill/SKILL.md) | FAIRVALUE AI Agent Skill |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Known limitations, honest inventory |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting & design notes |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Binding architecture & shared contracts |

## License

[MIT](LICENSE).
