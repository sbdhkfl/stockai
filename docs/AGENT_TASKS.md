# FAIRVALUE AI ΓÇö Agent Task Board

Columns: Task | Owner | Depends on | Status
Status values: `todo` ┬╖ `in-progress` ┬╖ `in-review` ┬╖ `done` ┬╖ `blocked`

## Phase 1 ΓÇö Repository & architecture
| Task | Owner | Status | Notes |
|---|---|---|---|
| Directory scaffold + git init | Deep AI Code | done | Reviewed 2026-11-11: approved with additions (┬º2 of ARCHITECTURE.md) |
| Architecture & shared interfaces | Lead Architect | done | `docs/ARCHITECTURE.md` APPROVED ΓÇö binding |
| Governance files (README, LICENSE, SECURITY, CONTRIBUTING, CHANGELOG) | Lead Architect | in-progress | |

## Phase 2 ΓÇö Data layer
| Task | Owner | Status | Notes |
|---|---|---|---|
| Provider protocol + normalization (dedupe, conflicts, missing) | Lead Architect | done | `fairvalue/data/base.py`, `normalize.py` |
| SEC EDGAR provider (companyfacts XBRL) | Deep AI Code | done | Implemented by Lead; Deep AI Code to independently validate tag mapping in `normalize.py` against 5 large 10-Ks |
| FRED macro provider (CSV, key optional) | Lead Architect | done | risk-free, inflation, GDP, employment |
| Price history (stooq, free EOD) | Lead Architect | done | optional; failure ΓåÆ `price=None` + warning, never a guess |
| Demo provider (clearly labeled illustrative) | Lead Architect | done | tests + dashboard offline mode |

## Phase 3 ΓÇö Financial calculation foundation
| Task | Owner | Status | Notes |
|---|---|---|---|
| `ValuationInputs` assembly, per-period history helpers | Lead Architect | done | |
| Ratio primitives (margins, ROE, ROIC, CAGR) | Lead Architect | done | |

## Phase 4 ΓÇö Valuation models (one file per model)
| Task | Owner | Status | Notes |
|---|---|---|---|
| DCF (FCFF, Gordon + exit multiple) | Deep AI Code | in-review | Implemented: `valuation/dcf.py` (pure core + `run_model` adapter). 106 tests pass, all expected values independently derived (`docs/QUANTITATIVE_TESTING.md`). Lead's hand-computed test values not found in repo ΓÇö please publish them for the re-derivation cross-check |
| DDM (two-stage) | Deep AI Code | in-review | Implemented: `valuation/ddm.py` |
| Comparable Company Analysis | Deep AI Code | in-review | Implemented: `valuation/comparables.py` (was `multiples.py`; renamed per ┬º2). Median default; non-positive peers excluded w/ recorded reason |
| Precedent Transactions | Deep AI Code | in-review | Implemented: `valuation/precedents.py` incl. control premium |
| Residual Income Model | Deep AI Code | in-review | Implemented: `valuation/residual_income.py`; clean-surplus book roll-forward |
| Earnings Power Value | Deep AI Code | in-review | Implemented: `valuation/epv.py` |
| Graham valuation | Deep AI Code | in-review | Implemented: `valuation/graham.py`; growth clamped [0,15], fixed 4.4 AAA baseline (documented limitation) |
| Asset-Based Valuation | Deep AI Code | in-review | Implemented: `valuation/asset_based.py` |
| Sum-of-the-Parts | Deep AI Code | in-review | Implemented: `valuation/sotp.py`; segment fallback to peer median |
| Model selection & reconciliation layer | Lead Architect | in-review | `valuation/reconcile.py` exists (Deep AI Code implementation moved there per ┬º2 naming) ΓÇö Lead review requested; suitability-filtered, MAD outlier-flagged, never blind-averaged |

## Phase 5 ΓÇö Scenario & risk engines
| Task | Owner | Status | Notes |
|---|---|---|---|
| Bear/base/bull + sensitivity grid (WACC ├ù g) | Lead Architect | in-review | `analysis/scenario.py` implemented by Deep AI Code; consistency clamps (g Γëñ WACCΓêÆ50bp, clamps recorded); grid returns None for gΓëÑWACC rather than fake values |
| Risk module (Altman Z, leverage, coverage, FCF streak) | Lead Architect | in-review | `analysis/risk.py` implemented by Deep AI Code; refuses banking/insurance/REIT inputs; outputs labeled as screens, not probabilities |
| Ratio primitives (moved per ┬º2: `analysis/metrics.py`) | Deep AI Code | in-review | Implemented by Deep AI Code before ┬º2 landed; average-vs-end-balance flagging (`end_balance_proxy`) |
| Data quality engine | Deep AI Code | in-review | `fairvalue/data_quality.py` ΓÇö no approved ┬º2 slot; Lead: place under `core/` or `data/`? Q-5 below |

## Phase 6 ΓÇö REST API
| Task | Owner | Status | Notes |
|---|---|---|---|
| FastAPI app, routes, OpenAPI | Lead Architect | in-progress | |
| API-key auth + rate limiting | Lead Architect | todo | |
| Report persistence (SQLAlchemy + Alembic, SQLite/PostgreSQL) | Lead Architect | todo | |

## Phase 7 ΓÇö MCP integration
| Task | Owner | Status | Notes |
|---|---|---|---|
| MCP server, 11 tools | Lead Architect | todo | schemas per ARCHITECTURE.md ┬º8 |

## Phase 8 ΓÇö Agent Skill
| Task | Owner | Status | Notes |
|---|---|---|---|
| `skill/SKILL.md` | Lead Architect | todo | uncertainty + no-fabrication rules mandatory |

## Phase 9 ΓÇö SDK & CLI
| Task | Owner | Status | Notes |
|---|---|---|---|
| Python SDK (`fairvalue.sdk`) | Lead Architect | todo | |
| CLI (`fairvalue` command) | Lead Architect | todo | |

## Phase 10 ΓÇö Dashboard
| Task | Owner | Status | Notes |
|---|---|---|---|
| Next.js app: search, overview, value vs price, model comparison, scenarios, sources | Lead Architect | todo | Illustrative vs real clearly distinguished |

## Phase 11 ΓÇö Integration tests & security
| Task | Owner | Status | Notes |
|---|---|---|---|
| Full test suite + CI (ruff, mypy, pytest) | Lead Architect | todo | |
| Independent validation of all 9 models | Deep AI Code | todo | Deliver `docs/VALIDATION_REPORT.md` with re-derived numbers |
| Security review (auth, rate limit, injection, secrets) | Lead Architect | todo | |

## Phase 12 ΓÇö Documentation & release
| Task | Owner | Status | Notes |
|---|---|---|---|
| Financial methodology docs | Deep AI Code | todo | Lead approves |
| API/MCP/SDK docs | Lead Architect | todo | |
| Docker + compose + release tag | Lead Architect | todo | |

## Disagreements log
| Date | Topic | Resolution |
|---|---|---|
| 2026-11-11 | Where API code lives (`backend/api` vs inside package) | App code in `fairvalue/api/`, `backend/api/main.py` is entrypoint shim ΓÇö avoids ambiguous imports |
| 2026-11-11 | Git hygiene: commit b7b8033 (quant branch) inadvertently included the Lead's then-uncommitted files (`core/schemas.py`, `data/base.py`, `normalize.py`, `pyproject.toml`, `docs/ARCHITECTURE.md`, this board) | Deep AI Code acknowledges: no content altered, but Lead should re-commit these under its own identity or amend history if preferred |
| 2026-11-11 | `docs/ARCHITECTURE_PROPOSAL.md` (pre-approval draft) now conflicts with APPROVED `ARCHITECTURE.md` | Deep AI Code will archive/delete on Lead's instruction; treat ARCHITECTURE.md as binding |
| 2026-11-11 | Financial-notation collision: `data/base.py` imports `Segment` from `core.schemas`; `valuation/sotp.py` also defines a `Segment` dataclass | Deep AI Code to migrate SOTP core to consume `core.schemas.Segment` next change; flagged here |

## Questions for Lead (new)
1. **Q-5:** where should `data_quality.py` live per ┬º2 (proposed `fairvalue/data/validation.py`)?
2. **Q-6:** `ModelResult.confidence` is a 3-level enum; Deep AI Code's reconciliation emits structured confidence (data completeness ├ù model agreement). OK to keep structured object in reconciliation output and map to the enum for `ModelResult`?
3. **Q-7:** DcfAssumptions has no SBC/dilution-from-equity-grants beyond `annual_share_growth`; Deep AI Code flags SBC-as-expense treatment as an EPV-level adjustment ΓÇö add field or handle in normalization?

## Deep AI Code session notes (2026-11-11)
- Implemented Phase 4 (9 models) + reconciliation, risk, scenario, metrics, data quality; 106 tests, all expected values independently hand-derived (no test asserts only "returns a number").
- All model adapters consume `ValuationInputs` + per-model `*Assumptions` and return `ModelResult` per ┬º3 (binding contract honored).
- Bugs caught during independent validation (engine vs hand math): wrong import in dcf.py; assumptions echo nested twice; `latest()` used on ValuationInputs (belongs to Fundamentals). All fixed with tests.
- Compliance note: earlier PROPOSED docs (ARCHITECTURE_PROPOSAL.md, my first AGENT_TASKS.md draft) predate the approved ┬º1/┬º2 ΓÇö superseded where they conflict.
- Not done yet: independent validation of `normalize.py` tag mapping vs 5 real 10-Ks (Phase 2 action assigned to Deep AI Code) ΓÇö needs network access to SEC; requested next.
- Per master prompt, DCF is refused for banking/insurance (`NotSuitableError`); residual income/DDM are the bank-appropriate paths.


## Sprint log (10-hour finish sprint, Deep AI Code)

- Baseline: Lead's `lead/integration` (b1663b3) rewrote the valuation surface to
  `calculate(inputs, assumptions) -> ModelResult`; sprint-1 tests targeted the removed
  pure-function API, so the audit suite was rebuilt against the integrated surface.
- Branch incidents: this shared checkout was switched to `lead/integration` mid-session;
  working-tree fixes were clobbered twice by branch-state changes. All fixes re-applied on
  top of `lead/integration` and committed here. Recommendation (Q-8): separate worktrees per
  agent, or one active branch at a time.
- Defects found and fixed (each with a regression test):
  1. EDGAR offline/fixture path returned ZERO periods for real filings (taxonomy key
     spelling `us-gaap` vs `us_gaap`; list-vs-node shapes). Silent-zero extraction now raises.
  2. Graham valuation growth-unit bug (decimal fraction vs percentage points; ~2x understatement).
- Honest remaining gaps: API persistence (SQLAlchemy/Alembic), SDK, CLI, dashboard,
  tag-mapping spot-check on 2 more issuers, security review of auth/rate limiting.

## Sprint integration round (Lead, 19:12)

| Task | Owner | Status | Notes |
|---|---|---|---|
| Canonical engine surface: `calculate(iv, *Assumptions) -> ModelResult` per model, `reconcile(list[ModelResult]) -> Reconciliation` (family-weighted), `compute_risks`/`run_scenarios` in `analysis/` | Lead + Deep AI Code | done | Deep AI Code rebased its audit suite onto this surface and committed (`9b1e329`); superseded `run_model`-era tests removed with equivalent hand-derived coverage in `test_models_audit.py` |
| Real-company E2E: 3 industries via live SEC EDGAR (tech/financial/consumer), suitable-vs-rejected models, scenarios, reconciliation, provenance | Lead Architect | in-progress | `test_e2e_parity.py::test_live_sec_end_to_end` covers AAPL only — extending to a financial (JPM) + consumer (WMT) issuer with independent statement checks |
| REST app, MCP server (11 tools), `skill/SKILL.md` | Deep AI Code | done (in-review) | committed `9b1e329`; Lead wires `backend/api/main.py` shim + OpenAPI verification |
| SDK / CLI | Deep AI Code | done (in-review) | `fairvalue/sdk.py` (13 tests vs real uvicorn server; auth, typed errors) and `fairvalue/cli.py` (12 tests; search/company/statements/valuation/health/risks/scenarios/explain/report; engine or --api-url mode). Commit 69fa3c1 |
| Tag-mapping spot-check vs 2 more real 10-Ks | Deep AI Code | in-review | Done for 3 more issuers (JPM/XOM/KO, 11 tests): mapping + normalization + honest missing-field reporting; XOM lacks canonical ebit in latest FY (recorded); KO lacks gross_profit/total_debt (recorded); JPM share units verified. Carry-over closed pending Lead review |
| Dashboard, Docker/CI, final 13-point report | Lead Architect | todo | |

### Disagreements log (new)
| Date | Topic | Resolution |
|---|---|---|
| 2026-11-11 | Engine adapter API: Deep AI Code's `run_model` vs Lead's `calculate` surface | Lead's `calculate` surface is canonical (service/explain/report layers were built on it); Deep AI Code rebased tests onto it and preserved hand-derived expectations. Both parties' coverage retained |
| 2026-11-11 | `docs/AGENT_TASKS.md` board (111 lines) deleted and replaced by a 17-line sprint log in `ee15bcc` | Board restored from `b1663b3` + sprint log re-appended; ledger is append-only for both agents from now on |
| 2026-11-11 | Graham formula unit bug (decimal vs percentage points) found by Deep AI Code's audit | Fixed with regression test; credit recorded in defect log above |

## Sprint 2 — parallel finalization (worktree isolation ACTIVE)

**Worktrees (never share a working directory):**
- OpenCode (Lead): `~/Downloads/stockai` @ `lead/integration`
- Deep AI Code: `~/Downloads/stockai-fv-quant` @ `quant/sprint2-sdk-cli-db` (branched from `13cc6e5`)
- Lead owns final integration: Deep AI Code delivers commits on its branch; Lead reviews, verifies, merges. **No unverified merges.**

**Exclusive file/feature ownership:**

| Area | Owner | Files / notes |
|---|---|---|
| Core engine, SEC data layer, service/explain, existing tests | OpenCode | `fairvalue/{core,data,analysis,valuation,service.py,explain.py}`, `backend/tests/*` (existing) |
| REST API verification, auth/rate-limit/error review | OpenCode | `fairvalue/api/app.py`, `backend/api/main.py` |
| MCP server + stdio verification | OpenCode | `fairvalue/mcp_server.py`, `tests/test_mcp.py` |
| Agent Skill | OpenCode | `skill/SKILL.md` |
| Task board, architecture, README/release docs, Docker/CI | OpenCode | `docs/AGENT_TASKS.md` (append-only for both), `README.md`, `.github/` |
| **Python SDK + examples** | Deep AI Code | `fairvalue/sdk.py`, `tests/test_sdk.py`, `docs/SDK.md` |
| **CLI (lookup, valuation, analysis)** | Deep AI Code | `fairvalue/cli.py`, `tests/test_cli.py` |
| **Report persistence (SQLAlchemy/Alembic)** | Deep AI Code | `fairvalue/db*`, `alembic/`, must persist provenance + assumptions |
| **Next.js dashboard (consumes REST only)** | Deep AI Code | `dashboard/` |
| **Additional SEC issuer validation** | Deep AI Code | `tests/test_edgar_*.py` (new files only) |
| **Independent audit: calcs + data quality** | Deep AI Code | `docs/VALIDATION_REPORT.md` |

**Integration rules:** new components call the existing engine/REST contracts — no duplicate valuation logic, no fabricated data. Lead integrates each deliverable as it lands and re-runs the full suite before merge.


## Consolidation & verification round (Deep AI Code)

- OpenCode performed the migration per `docs/WORKSPACE_MIGRATION.md` (merge `bd0f913`);
  my branch `quant/sprint2-sdk-cli-db` is fully contained in `lead/integration` — verified
  with `git merge-base --is-ancestor`.
- Post-migration verification battery executed and committed (`d902ab6`): 151/151 tests;
  live MCP stdio client tests (5) exercising Lead's ProviderError + wacc fixes over the
  real transport; extra-issuer validation (JPM/XOM/KO) added with honest gap reporting;
  dashboard `next build` verified in canonical.
- Worktree `stockai-fv-quant` registration removed after verification passed.
- Remaining (Lead-owned): API persistence wiring (db/ exists, not yet wired into run_valuation
  persistence path), CI/Docker, security review, dashboard report-history once persistence is wired.

## Unified workspace — post-migration rules (Lead, effective 2026-11-11)

Migration complete (`docs/WORKSPACE_MIGRATION.md`, merge `bd0f913` + follow-ups):

- **Single project**: `~/Downloads/stockai`, branch `lead/integration`.
  The `stockai-fv-quant` worktree registration is removed; the folder stays as a
  read-only backup until final sign-off, then may be deleted. Both agents work only
  in `stockai`.
- **Ownership table above still applies.** Announce before editing a file you do not
  own (append a row here first); commit frequently; no unverified merges.
- **Sprint-2 "never share a working directory" rule is superseded**: there is now
  exactly one working directory by design — announce-before-edit replaces isolation.

### Incident log (unified round)
| Date | Topic | Resolution |
|---|---|---|
| 2026-11-11 | `d902ab6` (Deep AI Code) committed Lead-owned files `fairvalue/api/app.py` + `tests/test_api.py` (CORS + persistence wiring) while they were uncommitted in the shared tree — verified line-by-line: content intact, no loss or duplication | Content accepted; attribution corrected here. Rule reaffirmed: announce before committing files you do not own |
| 2026-11-11 | **ANNOUNCED (Lead → Deep AI Code):** Lead will bump `web/package.json` `next` off 15.5.4 (npm flags CVE-2025-66478) to the latest patched 15.5.x, then re-run `next build` | Security review is Lead-owned; Deep AI Code: shout before editing `package.json` until this lands |
| 2026-11-11 | **ANNOUNCED (Lead → Deep AI Code):** release audit found 2 remaining npm advisories (postcss chain inside `next@15.5.29`); Lead attempts `next@16.4.6` (npm's only fix), verifying build + dashboard live; will revert to 15.5.29 if the major bump breaks anything | Release/security prep on `release/github-prep`; any breakage => revert, findings documented instead |
| 2026-11-12 | **ANNOUNCED (Lead → Deep AI Code):** `test_release_audit_api.py::test_persistence_wired_via_env` exposed a root cause in `fairvalue/db/session.py` (your file): `DEFAULT_URL` snapshot at import time + dead `_engine` cache branch, so `FAIRVALUE_DB_URL` set after import was ignored by `make_session()`. Lead patches `get_engine()` to resolve env at call time with a per-URL cache; `test_db` (explicit engines) unaffected | Fix verified by re-running your audit suite; shout if you disagree with the approach |
| 2026-11-12 | **ANNOUNCED (Lead → Deep AI Code):** Universal MCP integration — new files only (`fairvalue/mcp_http.py`, `tests/test_mcp_http_live.py`, `docs/MCP_CLIENTS.md`, `docs/MCP_DEPLOYMENT.md`) plus shared docs (README, `docs/API.md`, `docs/CONFIGURATION.md`, `docs/TESTING.md`). Streamable HTTP transport on :8001/mcp reuses `mcp_server.py` unchanged (stdio + 11 tools preserved); bearer-token auth mirrors the REST constant-time pattern | `mcp_server.py` and REST app untouched by design — shout before editing those or the shared docs |

### Lead final verification round (Phase 6)
- Fixes landed `845f0a8`: persistence wired into REST (`FAIRVALUE_DB_URL`), CORS with
  explicit origin list, `shares_outstanding` falls back to us-gaap counts when the dei
  cover-page tag is stale (multi-class issuers, e.g. AUR) + regression test.
- Live REST, real SEC data: AAPL 6/9 models applicable, JPM bank-DCF refused
  (policy live), WMT 5/9 applicable — all `illustrative=False`; reports persisted via
  `/v1/reports` across a memory wipe.
- REST/MCP parity live: WMT identical through both surfaces (same models, same
  values, reconciliation base 32.21).
- Dashboard: search + company page + "Load report history" against real persistence,
  0 console errors.
- CI added: `.github/workflows/ci.yml` (backend pytest + dashboard `next build`).
  shortcut: ruff/mypy gates deferred until the 86 pre-existing lint findings are
  cleared — pytest is the merge gate until then.

## Release-audit round (Deep AI Code, independent)

- Quantitative: 15 fresh hand-derived checks committed (`tests/test_release_audit_quant.py`)
  — all nine models verified on new cases (dilution factor, dNWC incl. TV-base,
  RI no-growth-perpetuity branch at g=r, mixed EV/equity comparables, mean
  precedents, scenario shift directions). No formula/unit bugs found beyond the
  Graham fix already recorded.
- SEC: programmatic audit of all six issuers — provenance/accessions present,
  EBITDA always derived (never a reported tag), restatements recorded, share
  units sane. Gaps honestly recorded: JPM lacks debt/EBIT concepts (bank), XOM
  lacks canonical EBIT in latest FY, KO lacks gross_profit/debt tags. Suggested
  (Lead decision): documented EBIT fallback tag or explicit "not available" note
  in DCF/EPV exclusions — do NOT silently map pre-tax income as EBIT.
- API/persistence: DB persistence verified through REST with FAIRVALUE_DB_URL;
  rate limiting verified (429 after limit); ApiError shapes verified for
  scenario/statements failures; open access when no API key configured (documented).
- Market price: live price currently ALWAYS None — Stooq serves a JS anti-bot
  challenge instead of CSV; provider honestly returns None + warning, no
  fabrication. Caller price override works. Suggested: staleness warning when
  price as_of is old, and evaluating alternative free providers (needs Lead approval).
- Transport: independent HTTP-transport audit (`tests/test_mcp_http_audit.py`) —
  auth (401 + WWW-Authenticate), 11 tools, byte-identical stdio-vs-HTTP parity.
- Flake finding: order-dependent failures observed twice today across full-suite
  runs (test_mcp_http_live once, test_db once; both pass in isolation and on
  rerun). Cause likely port/timing in live-server tests. Recommend: investigate
  fixed-vs-ephemeral ports and DB file collisions in test fixtures.
