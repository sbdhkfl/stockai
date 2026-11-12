# Installation

## Requirements

- Python **3.12+** (engine, REST API, MCP server, SDK, CLI)
- Node.js **20+** (dashboard; verified with 22/24)
- Network access to SEC EDGAR for real data (everything else runs offline;
  demo mode never needs the network)

## Backend (engine, API, MCP, SDK, CLI)

```bash
git clone <your-repo-url> FAIRVALUE-AI
cd FAIRVALUE-AI/backend
pip install -r requirements.txt
```

Optional, for development tooling (editable install with the `fairvalue`
console script, ruff, mypy):

```bash
pip install -e ".[dev]"
```

Sanity check:

```bash
python -m pytest            # full suite; live-SEC tests skip when offline
```

## REST API

```bash
cd backend
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
# OpenAPI UI: http://127.0.0.1:8000/docs
```

## MCP server

```bash
cd backend
python -m fairvalue.mcp_server      # stdio transport; 11 tools
```

Example MCP client registration (Claude Desktop / any MCP-compatible host):

```json
{
  "mcpServers": {
    "fairvalue": {
      "command": "python",
      "args": ["-m", "fairvalue.mcp_server"],
      "cwd": "/path/to/FAIRVALUE-AI/backend"
    }
  }
}
```

## Dashboard

```bash
cd web
npm install
NEXT_PUBLIC_FAIRVALUE_API=http://127.0.0.1:8000 npm run dev
# http://localhost:3000
```

For a production build: `npm run build && npm run start`.

## CLI

```bash
cd backend
python -m fairvalue.cli --help       # runs without installation
# or, after `pip install -e .`:
fairvalue --help
```

See [CONFIGURATION.md](CONFIGURATION.md) for environment variables and
[API.md](API.md) for endpoint/tool/SDK/CLI reference.
