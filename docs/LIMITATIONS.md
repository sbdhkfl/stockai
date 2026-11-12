# Known limitations

Honest inventory — what this MVP does **not** do. The engine's design rule is
to surface gaps instead of filling them with guesses.

## Data

- **Market price is often unavailable in live mode.** The free price source
  (Stooq) currently serves a JavaScript anti-bot challenge, so live valuations
  return `price: None` **with a warning** — never a fabricated or default
  price. Callers may pass an explicit `price=` override, which is echoed and
  labeled in the report. Demo mode has illustrative prices (clearly labeled).
- **SEC filings only.** Fundamentals come from EDGAR XBRL. Concepts a company
  does not tag appear under `missing_concepts` — e.g. some issuers lack a
  canonical `ebit`, `gross_profit` or `total_debt`. Nothing is imputed.
- **Share counts for multi-class issuers** fall back from the stale DEI
  cover-page tag to `us-gaap:CommonStockSharesOutstanding`, then to
  diluted weighted-average shares. Option/convertible detail beyond those
  tags is not modeled.
- **Peer data.** Comparables/precedents need peer multiples; in live mode they
  are frequently excluded (with recorded reasons) rather than computed from
  stale or missing inputs.
- **Agent-supplied data** (`POST /v1/valuation/from-data`, MCP
  `submit_financial_data`) is validated for units, dates, duplicates and
  accounting identities, but the engine **cannot verify that a supplied number
  matches the company's actual filings** — correctness rests on the agent's
  `source` provenance, which is echoed, not audited. Nothing is cross-checked
  against SEC data in this path by design (see [AGENT_DATA.md](AGENT_DATA.md)).

## Models

- 9 models are implemented, but each **self-excludes when its inputs are not
  meaningful**: DCF and EPV are refused for financial firms; Graham/DDM need
  positive earnings/dividends; a model may legitimately return a **negative**
  value for a loss-making company (stated assumptions, not a bug).
- Reconciliation is family-weighted across *applicable* models only. With one
  or two applicable models the range is wide by construction — the report says
  so.
- Scenario grids return `None` where WACC ≤ terminal growth rather than a
  mathematically meaningless number.

## Platform

- **Rate limiting and report store are per-process/in-memory unless a DB is
  configured** — not distributed (no Redis), and multi-worker deployments
  share nothing without `FAIRVALUE_DB_URL`.
- **No Docker image / compose file yet**, no release tag yet.
- **Dashboard API URL is baked at build time** (`NEXT_PUBLIC_FAIRVALUE_API`).
- **Quality debt:** 92 ruff and 48 mypy findings are documented, not gating
  (see [TESTING.md](TESTING.md)); CI runs pytest + dashboard build only.
- **No git remote yet** — publication is pending user approval (see release
  report).

## Scope

- Estimates are **conditional on stated assumptions** — not investment advice,
  not a recommendation, not a forecast. Every output carries assumptions,
  provenance and limitations; keep them attached when quoting numbers.
- The engine never calls an LLM: outputs are deterministic and reproducible.
