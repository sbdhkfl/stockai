# API, MCP, SDK & CLI reference

Every surface exposes the **same engine** — identical inputs produce identical
outputs over REST, MCP, SDK and CLI (enforced by parity tests).

## REST API

Base URL: `http://127.0.0.1:8000` · Interactive docs: `/docs` · OpenAPI: `/openapi.json`

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + version |
| GET | `/v1/companies/search?q=` | Resolve a name/ticker (`demo=true` for illustrative data) |
| GET | `/v1/companies/{ticker}` | Company profile |
| GET | `/v1/companies/{ticker}/statements` | Normalized filings + provenance + missing concepts |
| GET | `/v1/companies/{ticker}/metrics` | Health metrics + current multiples |
| GET | `/v1/companies/{ticker}/health` | Margins, ROE/ROIC, leverage |
| GET | `/v1/companies/{ticker}/risks` | Altman Z screen, leverage & FCF flags |
| GET | `/v1/companies/{ticker}/valuation` | Full report: 9 models, reconciliation, scenarios, explanation |
| POST | `/v1/companies/{ticker}/scenarios` | Bear/base/bull + WACC×growth grid |
| GET | `/v1/companies/{ticker}/explain` | Deterministic plain-language explanation |
| POST | `/v1/valuation/from-data` | Full report from **agent-supplied structured data** — no external provider, no ticker allowlist (query params: `wacc`, `price`, `models`) |
| GET | `/v1/reports` | Stored report index (DB-backed when `FAIRVALUE_DB_URL` is set) |
| GET | `/v1/reports/{report_id}` | Full stored report (404 in ApiError shape if unknown) |

**Error contract:** every error body is `{"error": {"code", "message", "detail"}}`
(404 `not_found`, 401 `unauthorized`, 422 `validation_error`, 429 `rate_limited`,
502 provider errors). Responses carry assumptions, per-model steps, provenance
and limitations — never a bare number.

**Auth:** optional `X-API-Key` when `FAIRVALUE_API_KEY` is set (constant-time
comparison). **Rate limit:** per-client, in-memory. **CORS:** explicit origin
list, no wildcard (see [CONFIGURATION.md](CONFIGURATION.md)).

## MCP server (13 tools, two transports)

Same server, same tools, same responses on both transports (enforced by a
stdio↔HTTP parity test):

| Transport | Start | Endpoint | Auth |
|---|---|---|---|
| stdio (local) | `python -m fairvalue.mcp_server` | — | none (local process) |
| Streamable HTTP (remote) | `python -m fairvalue.mcp_http` | `http://127.0.0.1:8001/mcp` | **required**: `Authorization: Bearer <token>` (or `X-API-Key`), constant-time compare; token from `FAIRVALUE_MCP_TOKEN` (fallback `FAIRVALUE_API_KEY`) |

HTTP extras: `GET /health` (open, liveness only); 401 with
`{"error": {"code": "unauthorized"}}` otherwise; server refuses to start
without a token (loopback `FAIRVALUE_MCP_ALLOW_ANON=1` dev escape hatch).
Multiple concurrent clients get independent MCP sessions. Protocol `2025-11-25`.

Client configs: [MCP_CLIENTS.md](MCP_CLIENTS.md) · HTTPS deployment:
[MCP_DEPLOYMENT.md](MCP_DEPLOYMENT.md).

`python -m fairvalue.mcp_server` — protocol `2025-11-25`.

| Tool | Key parameters |
|---|---|
| `search_company` | `query`, `demo` |
| `get_financial_statements` | `ticker`, `demo` |
| `get_financial_metrics` | `ticker`, `demo` |
| `calculate_dcf` | `ticker`, `wacc`, `demo` |
| `calculate_valuation` | `ticker`, `demo` (full report + `report_id`) |
| `compare_competitors` | `ticker`, `demo` |
| `analyze_financial_health` | `ticker`, `demo` |
| `analyze_risks` | `ticker`, `demo` |
| `run_scenario_analysis` | `ticker`, `wacc`, `demo` |
| `explain_valuation` | `ticker`, `demo` |
| `get_valuation_report` | `report_id` |
| `submit_financial_data` | `data` (JSON envelope — validation only, no valuation) |
| `calculate_valuation_from_data` | `data`, `wacc?`, `price?`, `models?` (full report from agent-supplied data) |

Envelope reference, provenance taxonomy and validation rules for the two
`from-data` tools: [AGENT_DATA.md](AGENT_DATA.md).

Failures return a **structured error payload** (`error.code` such as
`provider_error`, `not_found`, `assumption_missing`) instead of free text —
every tool was exercised end-to-end over a real stdio client.

See [skill/SKILL.md](../skill/SKILL.md) for the Agent Skill (rules for AI
assistants calling these tools: provenance, uncertainty, no fabrication).

## Python SDK

```python
from fairvalue.sdk import FairValueClient

with FairValueClient(base_url="http://127.0.0.1:8000", api_key="...") as c:
    hits = c.search("apple")
    report = c.valuation("AAPL", price=150.0)   # pydantic-validated responses
    risks = c.risks("AAPL")                     # typed RiskAssessment
    # agent-supplied data (docs/AGENT_DATA.md): no provider touched server-side
    from fairvalue.agent_data import AgentSuppliedCompany
    envelope = AgentSuppliedCompany.model_validate({...})
    report = c.valuation_from_data(envelope, wacc=0.10)
```

Typed errors surface as `SdkError`; auth via `X-API-Key`.

## CLI

```bash
python -m fairvalue.cli search aurora            # JSON by default; --text for human summary
python -m fairvalue.cli valuation AAPL           # full report
python -m fairvalue.cli valuation AUR --demo     # labeled illustrative data
python -m fairvalue.cli health JPM --api-key $KEY
python -m fairvalue.cli report r-abc123          # fetch a stored report
# subcommands: search company statements valuation health risks scenarios explain report
# global flags: --api-url --api-key --demo --text
```

Without `--api-url` reachability, commands can run against the engine directly
(`--demo` works offline).
