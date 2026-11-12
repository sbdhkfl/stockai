# MCP client setup guides

FAIRVALUE AI exposes the same **13 tools** over two transports:

| Transport | Entry | Auth |
|---|---|---|
| Local stdio | `python -m fairvalue.mcp_server` | none needed (local process) |
| Remote Streamable HTTP | `python -m fairvalue.mcp_http` → `http://127.0.0.1:8001/mcp` | **required** bearer token |

## What is actually tested vs. not

**Verified in this repository** (real clients, real subprocess/network, see
`backend/tests/test_mcp_stdio_live.py` and `test_mcp_http_live.py`):

- stdio transport: 13 tools listed, valuations, structured errors, wacc honored,
  report roundtrip.
- Streamable HTTP transport: 13 tools listed, every tool returns traceable data
  (including the two agent-supplied-data tools), 401 without/with wrong token,
  two concurrent sessions without conflicts, stdio↔HTTP output parity.

**Not verified:** the GUI/CLI configuration of the individual assistant products
below. Those configs follow each vendor's published documentation, but this
project has not run inside them — treat them as starting points and confirm the
13 tools appear in your client's tool list.

---

## Claude Desktop

**Local (stdio)** — edit `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/`, Windows:
`%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "fairvalue": {
      "command": "python",
      "args": ["-m", "fairvalue.mcp_server"],
      "cwd": "C:/path/to/FAIRVALUE-AI/backend"
    }
  }
}
```

Restart Claude Desktop; the 13 `fairvalue` tools should appear under the
tools/connector icon.

**Remote (Streamable HTTP):** Claude Desktop custom connectors
(*Settings → Connectors → Add custom connector*) take a server URL. This
server requires a bearer token; whether your Claude Desktop build can send
custom headers varies — if it cannot, use the local stdio config above (or a
local reverse proxy). Endpoint URL: `https://your.domain/mcp`
(see [MCP_DEPLOYMENT.md](MCP_DEPLOYMENT.md)).

## VS Code

Project file `.vscode/mcp.json` (or user-level MCP config):

**Remote (Streamable HTTP, token via header):**

```json
{
  "servers": {
    "fairvalue": {
      "type": "http",
      "url": "http://127.0.0.1:8001/mcp",
      "headers": {
        "Authorization": "Bearer ${env:FAIRVALUE_MCP_TOKEN}"
      }
    }
  }
}
```

**Local (stdio):**

```json
{
  "servers": {
    "fairvalue": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "fairvalue.mcp_server"],
      "cwd": "${workspaceFolder}/backend"
    }
  }
}
```

Start the remote server first (`python -m fairvalue.mcp_http`), then use
*MCP: List Servers* in the command palette to confirm `fairvalue` connects and
lists 13 tools.

## OpenCode

Local stdio:

```sh
opencode mcp add fairvalue --global -- python -m fairvalue.mcp_server
```

(or in `opencode.jsonc`):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "fairvalue": {
        "type": "local",
        "command": ["python", "-m", "fairvalue.mcp_server"],
        "cwd": "C:/path/to/FAIRVALUE-AI/backend"
      }
    }
  }
}
```

Remote Streamable HTTP — disable OAuth (this server uses a static bearer
token) and keep the secret in an environment variable, never in the file:

```jsonc
{
  "mcp": {
    "servers": {
      "fairvalue": {
        "type": "remote",
        "url": "http://127.0.0.1:8001/mcp",
        "oauth": false,
        "headers": { "Authorization": "Bearer {env:FAIRVALUE_MCP_TOKEN}" }
      }
    }
  }
}
```

Check with `opencode mcp list` (expect `connected`), or `/mcps` in the TUI.

## ChatGPT

ChatGPT **connectors** (*Settings → Connectors*) speak remote MCP over
Streamable HTTP, but:

- They are **cloud-side**: the endpoint must be a public HTTPS URL
  ([MCP_DEPLOYMENT.md](MCP_DEPLOYMENT.md)), reachable from ChatGPT's servers.
- Custom request headers (our bearer token) are **not configurable** in the
  connector UI as of this writing, and OAuth is not implemented by this
  server.

**Status: not supported out of the box, not tested.** To use ChatGPT you would
need an authenticating proxy in front that ChatGPT's OAuth flow accepts — not
part of this project. Prefer Claude Desktop / VS Code / OpenCode, which all
support header-based tokens.

---

## Verifying any client

Whatever the client, the acceptance check is the same:

1. Server lists **13 tools** (`search_company` … `calculate_valuation_from_data`).
2. `calculate_valuation {"ticker": "AUR", "demo": true}` returns a report with
   `report_id`, `reconciliation`, `is_illustrative: true` and an `explanation`.
3. `get_valuation_report {"report_id": "<id from step 2>"}` returns the same
   report (traceability).
4. A bad ticker returns `{"error": {"code": "company_not_found"}}`, not a crash.
5. Agent-supplied workflow: `submit_financial_data` with any ticker envelope
   returns `valid: true`, and `calculate_valuation_from_data` with the same
   envelope returns a 9-model report — no provider data involved
   (envelope reference: [AGENT_DATA.md](AGENT_DATA.md)).

See [API.md](API.md) for the full tool contract.
