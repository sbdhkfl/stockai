# FAIRVALUE AI — Agent Task Board

Columns: Task | Owner | Depends on | Status
Status values: `todo` · `in-progress` · `in-review` · `done` · `blocked`

## Phase 1 — Repository & architecture
| Task | Owner | Status | Notes |
|---|---|---|---|
| Directory scaffold + git init | Deep AI Code | done | Reviewed 2026-11-11: approved with additions (§2 of ARCHITECTURE.md) |
| Architecture & shared interfaces | Lead Architect | done | `docs/ARCHITECTURE.md` APPROVED — binding |
| Governance files (README, LICENSE, SECURITY, CONTRIBUTING, CHANGELOG) | Lead Architect | in-progress | |

## Phase 2 — Data layer
| Task | Owner | Status | Notes |
|---|---|---|---|
| Provider protocol + normalization (dedupe, conflicts, missing) | Lead Architect | done | `fairvalue/data/base.py`, `normalize.py` |
| SEC EDGAR provider (companyfacts XBRL) | Deep AI Code | done | Implemented by Lead; Deep AI Code to independently validate tag mapping in `normalize.py` against 5 large 10-Ks |
| FRED macro provider (CSV, key optional) | Lead Architect | done | risk-free, inflation, GDP, employment |
| Price history (stooq, free EOD) | Lead Architect | done | optional; failure → `price=None` + warning, never a guess |
| Demo provider (clearly labeled illustrative) | Lead Architect | done | tests + dashboard offline mode |

## Phase 3 — Financial calculation foundation
| Task | Owner | Status | Notes |
|---|---|---|---|
| `ValuationInputs` assembly, per-period history helpers | Lead Architect | done | |
| Ratio primitives (margins, ROE, ROIC, CAGR) | Lead Architect | done | |

## Phase 4 — Valuation models (one file per model)
| Task | Owner | Status | Notes |
|---|---|---|---|
| DCF (FCFF, Gordon + exit multiple) | Deep AI Code | in-review | Tests written by Lead with hand-computed values — Deep AI Code must re-derive independently |
| DDM (two-stage) | Deep AI Code | in-review | |
| Comparable Company Analysis | Deep AI Code | in-review | |
| Precedent Transactions | Deep AI Code | in-review | |
| Residual Income Model | Deep AI Code | in-review | |
| Earnings Power Value | Deep AI Code | in-review | |
| Graham valuation | Deep AI Code | in-review | |
| Asset-Based Valuation | Deep AI Code | in-review | |
| Sum-of-the-Parts | Deep AI Code | in-review | |
| Model selection & reconciliation layer | Lead Architect | done | Do NOT average across families without documenting weights |

## Phase 5 — Scenario & risk engines
| Task | Owner | Status | Notes |
|---|---|---|---|
| Bear/base/bull + sensitivity grid (WACC × g) | Lead Architect | done | |
| Risk module (Altman Z, leverage, coverage, FCF streak) | Lead Architect | done | |

## Phase 6 — REST API
| Task | Owner | Status | Notes |
|---|---|---|---|
| FastAPI app, routes, OpenAPI | Lead Architect | in-progress | |
| API-key auth + rate limiting | Lead Architect | todo | |
| Report persistence (SQLAlchemy + Alembic, SQLite/PostgreSQL) | Lead Architect | todo | |

## Phase 7 — MCP integration
| Task | Owner | Status | Notes |
|---|---|---|---|
| MCP server, 11 tools | Lead Architect | todo | schemas per ARCHITECTURE.md §8 |

## Phase 8 — Agent Skill
| Task | Owner | Status | Notes |
|---|---|---|---|
| `skill/SKILL.md` | Lead Architect | todo | uncertainty + no-fabrication rules mandatory |

## Phase 9 — SDK & CLI
| Task | Owner | Status | Notes |
|---|---|---|---|
| Python SDK (`fairvalue.sdk`) | Lead Architect | todo | |
| CLI (`fairvalue` command) | Lead Architect | todo | |

## Phase 10 — Dashboard
| Task | Owner | Status | Notes |
|---|---|---|---|
| Next.js app: search, overview, value vs price, model comparison, scenarios, sources | Lead Architect | todo | Illustrative vs real clearly distinguished |

## Phase 11 — Integration tests & security
| Task | Owner | Status | Notes |
|---|---|---|---|
| Full test suite + CI (ruff, mypy, pytest) | Lead Architect | todo | |
| Independent validation of all 9 models | Deep AI Code | todo | Deliver `docs/VALIDATION_REPORT.md` with re-derived numbers |
| Security review (auth, rate limit, injection, secrets) | Lead Architect | todo | |

## Phase 12 — Documentation & release
| Task | Owner | Status | Notes |
|---|---|---|---|
| Financial methodology docs | Deep AI Code | todo | Lead approves |
| API/MCP/SDK docs | Lead Architect | todo | |
| Docker + compose + release tag | Lead Architect | todo | |

## Disagreements log
| Date | Topic | Resolution |
|---|---|---|
| 2026-11-11 | Where API code lives (`backend/api` vs inside package) | App code in `fairvalue/api/`, `backend/api/main.py` is entrypoint shim — avoids ambiguous imports |
