# FAIRVALUE AI — Workspace Migration Inventory

Date: 2026-11-11 · Lead: OpenCode · Controlled migration: `stockai-fv-quant` → `stockai`

## 1. Environments audited

| Item | `stockai` (authoritative) | `stockai-fv-quant` (temporary) |
|---|---|---|
| Path | `~/Downloads/stockai` | `~/Downloads/stockai-fv-quant` |
| Kind | Primary clone (no remote; local-only repo) | **Git worktree of the same repository** (shares all objects/refs) |
| Branch | `lead/integration` | `quant/sprint2-sdk-cli-db` |
| HEAD before migration | `6e28d44` | `99eb14c` |

Because `stockai-fv-quant` is a worktree (not a separate clone), both folders already
share one object database: **no commit can be "only in one folder"** — only
*uncommitted* files differed, and those are now committed (below).

## 2. Commit inventory (all preserved)

Shared history: `fb78c08` → `b7b8033` → `22773a7` → `b1663b3` → `ee15bcc` → `9b1e329` → `13cc6e5`

| Commit | Branch | Content | Status |
|---|---|---|---|
| `ac6707c` | lead/integration | Lead: DCF excluded for financial firms; scenarios gated on DCF applicability | preserved |
| `b6fc33a` | lead/integration | Lead: sprint-2 ownership contract on task board | preserved |
| `6e28d44` | lead/integration | Lead: MCP structured-error contract on all 11 tools; `calculate_dcf` wacc passthrough fix + tests | preserved |
| `69fa3c1` | quant/sprint2-sdk-cli-db | Deep AI Code: Python SDK, CLI, SQLAlchemy/Alembic report persistence + 31 tests | **migrated (merged)** |
| `99eb14c` | quant/sprint2-sdk-cli-db | Deep AI Code: Next.js dashboard (`web/`) consuming the live REST API | **migrated (merged)** |

## 3. Uncommitted state found pre-migration

- `stockai`: none after committing `6e28d44` (MCP fixes were WIP at audit time).
- `stockai-fv-quant`: Next.js dashboard source (`web/app`, `web/lib`, configs) + `.gitignore`
  `.next/` rule → committed as `99eb14c` before any folder is touched. `.next/` build
  artifacts deliberately excluded (regenerable).

## 4. Unique content by folder

- `stockai` unique: commits `ac6707c`, `b6fc33a`, `6e28d44` (Lead work).
- `stockai-fv-quant` unique: commits `69fa3c1`, `99eb14c` (Deep AI Code work);
  regenerable caches only beyond that (`.next/`, `__pycache__`).
- Divergence point: both branches forked from `13cc6e5`; file sets are disjoint
  (Lead: `valuation/`, `service.py`, `mcp_server.py`, docs · Quant: `sdk.py`, `cli.py`,
  `db/`, `web/`, new tests) → clean merge expected.

## 5. Migration procedure

1. ✅ Record status of both folders (this document).
2. ✅ Safety: every unique change committed to a named branch (`lead/integration`,
   `quant/sprint2-sdk-cli-db`) — nothing exists only in working trees.
3. ✅ Authoritative repo: `stockai` primary clone; **no git remote exists** (local-only).
4. Merge `quant/sprint2-sdk-cli-db` → `lead/integration` in `stockai` (Lead owns merges).
5. Run full verification battery (tests, REST, MCP, SDK, CLI, DB, dashboard, SEC).
6. Remove the worktree registration; keep `stockai-fv-quant` folder as a read-only
   backup until verification passes, then delete (its content is fully in git history).
7. Both agents operate on `stockai` from then on (rules in `docs/AGENT_TASKS.md`).

## 6. Post-migration state (completed by Deep AI Code after verification)

Verification battery executed in the canonical repo (commit `d902ab6`):

| Check | Result |
|---|---|
| Full pytest suite | **151 passed** (incl. 31 migrated SDK/CLI/DB tests, 11 new extra-issuer tests, 5 live-MCP-stdio tests) |
| All nine valuation models | pass (`tests/test_models_audit.py`, hand-derived) |
| SDK | pass (`tests/test_sdk.py`, 13 tests vs a real uvicorn server) |
| CLI | pass (`tests/test_cli.py`, 12 tests, engine + API modes) |
| Persistence + Alembic | pass (`tests/test_db.py`, incl. real `alembic upgrade head` subprocess) |
| REST API | pass (`tests/test_api.py`, 9 tests) |
| MCP (tool level) | pass (`tests/test_mcp.py`, 12 tests incl. Lead's 6e28d44 fixes) |
| MCP stdio with a REAL client | pass (`tests/test_mcp_stdio_live.py`, 5 tests via mcp ClientSession over stdio) |
| REST/MCP/engine parity | pass (`tests/test_e2e_parity.py`) |
| SEC fixtures & regression | pass (AAPL/JNJ/WMT + new JPM/XOM/KO) |
| WACC & ProviderError fixes | pass (Lead's 6e28d44, verified through the live stdio client) |
| Dashboard | `next build` succeeds; pages verified serving against live API; real data only |
| Worktree cleanup | `stockai-fv-quant` registration removed after verification (content fully in git history) |

Additional-issuer findings (reported honestly, sprint-2 deliverable 5):
- JPM (banking): shares_outstanding is in raw SHARES (unit sanity 50e6–1e10 held);
  DCF correctly refused for financial firms; reconciliation excludes it and does
  not fake a spread from one applicable model.
- XOM (energy): latest FY lacks the canonical `ebit` tag (OperatingIncomeLoss not
  exposed in these filings) — recorded in missing_concepts, never fabricated;
  revenue magnitude guards passed.
- KO (consumer staples): `gross_profit`, `total_debt`, `total_liabilities` absent
  from canonical set (tag coverage gap — honest gaps; `ebitda` is by design never
  a canonical concept, derived as EBIT + D&A).

### Lead final addendum (2026-11-11, after Phase 6 re-verification)

| Check | Result |
|---|---|
| Full pytest suite | **154 passed, exit 0** (`--collect-only`: 154) |
| Live SEC valuations, 3 industries | AAPL (tech) 6/9 models · JPM (bank) DCF refused by policy · WMT (retail) 5/9 — all `illustrative=False` |
| REST/MCP parity (live) | WMT identical via REST and MCP stdio (recon base 32.21) |
| Persistence | `FAIRVALUE_DB_URL` wired into REST (`845f0a8`); reports survived an in-memory wipe; dashboard "Load report history" shows them |
| CORS | explicit-origin middleware; dashboard calls API with 0 console errors |
| SEC data fix | `shares_outstanding` falls back to us-gaap counts when dei cover-page tag is stale (AUR multi-class gap) — `845f0a8` |
| Security review | constant-time API key compare, bounded rate-limit map, 422 in ApiError contract, `company()` ProviderError→502 — `3b822e4`; next bumped 15.5.4→15.5.29 (CVE-2025-66478) — `8efd145` |
| CI | `.github/workflows/ci.yml`: backend pytest + dashboard `next build` (both verified locally); ruff/mypy deferred (86 pre-existing lint findings, documented) |
| Backup folder | `stockai-fv-quant`: zero unique files (path-diff + git audit), worktree deregistered, files removed; one empty dir may linger while a process cwd points into it |

Final state: HEAD `8efd145` on `lead/integration`, working tree clean, no git remote (local-only repo), 19 commits, single project directory `~/Downloads/stockai`.

