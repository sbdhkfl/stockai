# Configuration reference

All configuration is environment variables (or CLI flags). There are **no
`.env` files in the repository**; `.env`, `.env*.local`, `*.db` and
`*.sqlite*` are git-ignored. Values below are examples — never commit real
credentials.

## REST API (`fairvalue/api/app.py`)

| Variable | Default | Purpose |
|---|---|---|
| `FAIRVALUE_API_KEY` | unset | When set, every `/v1/*` request must send header `X-API-Key: <value>`. Compared in constant time. Unset = open (dev mode). |
| `FAIRVALUE_RATE_LIMIT` | `60` | Max requests per client per window (in-memory, per process). |
| `FAIRVALUE_RATE_WINDOW_S` | `60` | Rate-limit window in seconds. |
| `FAIRVALUE_DB_URL` | unset | When set, valuations persist to this database and `/v1/reports` serves history from it. Examples: `sqlite:///./fairvalue.db`, `postgresql+psycopg://user:pass@host/fairvalue`. Unset = in-memory only (nothing written to disk). |
| `FAIRVALUE_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins allowed to call the API. Never a wildcard. |

Example hardened start:

```bash
export FAIRVALUE_API_KEY="choose-a-long-random-string"
export FAIRVALUE_DB_URL="sqlite:///./fairvalue.db"
export FAIRVALUE_CORS_ORIGINS="https://your-dashboard.example"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

## Data providers

| Variable | Default | Purpose |
|---|---|---|
| `SEC_EDGAR_UA` | `FAIRVALUE-AI/0.1 (…; contact@example.com)` | User-Agent sent to SEC EDGAR. SEC requests a descriptive UA with contact info; set your own for production traffic. |
| (none needed) | — | FRED CSV endpoint requires no API key; Stooq price history requires no key. When a price source is unavailable, `price` stays `None` with a warning — never a guess. |

## SDK / CLI

| Flag / variable | Default | Purpose |
|---|---|---|
| `--api-url` (CLI) | `http://127.0.0.1:8000` | REST API base URL. |
| `--api-key` (CLI) / `api_key` (SDK) | unset | Sent as `X-API-Key` when auth is enabled. |
| `--demo` / `demo=true` | off | Clearly-labeled illustrative data, offline. |

## Dashboard (`web/`)

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_FAIRVALUE_API` | `http://127.0.0.1:8000` | API base URL baked in at build time (Next.js public env). |

## Database migrations

With `FAIRVALUE_DB_URL` set, the API bootstraps tables on first use
(convenience for dev). Real deployments should manage schema explicitly:

```bash
cd backend
FAIRVALUE_DB_URL="sqlite:///./fairvalue.db" \
  python -m alembic -c fairvalue/db/migrations/alembic.ini upgrade head
```
