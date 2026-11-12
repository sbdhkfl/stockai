# FAIRVALUE AI — Workspace Migration Inventory

Date: 2026-11-11 · Lead: OpenCode · Controlled migration: `stockai-fv-quant` → `stockai`

## 1. Environments audited

| Item | `stockai` (authoritative) | `stockai-fv-quant` (temporary) |
|---|---|---|
| Path | `C:\Users\sbdhk\Downloads\stockai` | `C:\Users\sbdhk\Downloads\stockai-fv-quant` |
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

## 6. Post-migration state

(to be completed after verification — see Phase 6 results in the final report)
