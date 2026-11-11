# FAIRVALUE AI — Architecture Proposal (PROPOSED — awaiting OpenCode review)

> Status: **PROPOSED**. Authored by the Quant Agent as a working substrate, not a
> final architecture. OpenCode may reshape anything here; the financial math in
> `fairvalue/` is the part the Quant Agent defends.

## Proposed stack

| Layer | Technology | Rationale |
|---|---|---|
| Financial engine | Python 3.11, pure functions, no framework deps | testable, auditable math |
| API | FastAPI (Pydantic v2) | typed contracts, OpenAPI for the frontend |
| Persistence | PostgreSQL | provenance-heavy relational data |
| Frontend | Next.js + TypeScript | OpenCode's domain |

## Module boundaries (PROPOSED)

```
backend/
  fairvalue/            # PURE financial library. No I/O. No FastAPI imports.
    metrics.py          # ratios: profitability, liquidity, solvency, efficiency, growth
    risk.py             # Altman Z, leverage/distress flags
    scenario.py         # scenario deltas, sensitivity grids
    data_quality.py     # validation rules, provenance typing
    reconciliation.py   # multi-model reconciliation + confidence
    valuation/
      dcf.py            # 2-stage FCFF DCF, EV<->equity bridge
      ddm.py            # Gordon + 2-stage DDM
      residual_income.py# RI model (suitable for banks/insurers)
      epv.py            # Greenwald earnings power value
      graham.py         # Graham formula + Graham number
      multiples.py      # peer median comps, implied values
      asset_based.py    # adjusted NAV
      sotp.py           # sum-of-the-parts
  api/                  # thin FastAPI adapter; owns no math
  tests/                # pytest; every expected value hand-derived
web/                    # Next.js (OpenCode)
docs/
```

**Key boundary rule (Q-3):** `fairvalue/` imports nothing but the standard library.
The API layer converts HTTP models ↔ engine dataclasses. This guarantees the
mathematics can be audited and tested without the web stack.

## Proposed API contracts (v0, PROPOSED)

- `GET /health` → `{status, version}`
- `POST /valuation/dcf` — body: `{fcff: [float], wacc: float, terminal_growth: float,
  net_debt: float, diluted_shares: float}` → full breakdown (PV terms, TV, EV,
  equity, per-share) with assumption echo.
- `POST /metrics` — body: statement fragments → computed ratio suite with formulas used.
- `POST /risk/altman-z` — body: `{working_capital, total_assets, retained_earnings,
  ebit, market_equity, total_liabilities, sales, sector}` → Z, zone, applicability warnings.
- `POST /scenario/sensitivity` — DCF inputs + parameter ranges → value grid.
- `POST /reconcile` — list of model outputs → suitability-filtered, outlier-flagged,
  confidence-qualified fair-value range.

All responses include the exact inputs and formulas used so every figure is explainable.

## Proposed PostgreSQL domains (for T-016)

- `statement_values(id, company_id, statement, line_item, period, value, unit,
  currency, as_reported, restatement_of, source, ingested_at)`
- `provenance_tags(value_id, kind)` where kind ∈ {reported, guidance, estimate,
  model_assumption, ai_interpretation} — enforced by CHECK constraint.
