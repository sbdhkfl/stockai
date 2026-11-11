# Valuation Models — Input Dictionaries, Assumptions, Suitability

Companion to `FINANCIAL_METHODOLOGY.md`. Each model: formula, inputs, assumptions,
limitations, suitability, edge cases, and pointer to its tests in `backend/tests/`.

## DCF (FCFF) — `valuation/dcf.py`

| Input | Definition |
|---|---|
| `fcff[]` | Free cash flow to firm per explicit year = EBIT×(1−t) + D&A − capex − ΔNWC |
| `wacc` | Weighted average cost of capital, decimal |
| `terminal_growth` | Perpetual growth g, decimal, must be < WACC |
| `net_debt` | Total debt − cash & equivalents (+ minority interest, preferred) |
| `diluted_shares` | Diluted weighted-average shares outstanding |

Assumptions: end-of-year flows; TV = Gordon on final-year FCFF; no mid-year
convention; tax rate constant. Edge cases handled: negative FCFF in final year
(TV refused, flagged), g ≥ WACC (error), non-finite inputs (error).
Not suitable: banks, insurers, any firm where interest is operating.

## DDM — `valuation/ddm.py`

Inputs: `d0` (most recent DPS), `r` cost of equity, `g` perpetual growth (Gordon);
two-stage adds `growth_years`, `high_growth`. Edge cases: zero dividend
(model not meaningful), g ≥ r (error), negative g supported (declining dividend).

## Residual Income — `valuation/residual_income.py`

Inputs: `book_value0`, `earnings[]`, `cost_of_equity`, optional `dividends[]`
(B_t = B_{t−1} + E_t − D_t), optional continuing premium.
Edge cases: negative book value → model not meaningful; r ≤ 0 error.

## EPV — `valuation/epv.py`

Inputs: `ebit`, `tax_rate`, `maintenance_capex`, `depreciation`, `sbc`,
`cost_of_capital`. Normalized earnings = (EBIT − SBC)×(1−t) − (maintenance capex − depreciation).
Edge cases: r ≤ 0 error; negative normalized earnings → not meaningful.

## Graham — `valuation/graham.py`

Inputs: `eps` (diluted TTM), `growth_pct` (capped at 15), `aaa_yield_pct` (default 4.4).
Edge cases: negative EPS → not meaningful; growth_pct clamped to [0, 15] with a warning.

## Multiples — `valuation/multiples.py`

Inputs: peer list of (multiple value, metric) pairs, target metric.
Median is used, never mean, to resist outliers. Peers with negative/zero metrics
are excluded with a recorded reason. EV vs equity multiple pairing enforced by
explicit enum; crossing levels raises an error.

## Asset-Based — `valuation/asset_based.py`

Inputs: book assets/liabilities plus adjustment schedule `[(item, delta, reason)]`.
Every adjustment must carry a reason string (provenance rule).

## SOTP — `valuation/sotp.py`

Inputs: segments with own valuations (any model), net_debt, unallocated costs.
Edge case: missing segment disclosure → segment flagged, partial SOTP returned with
coverage percentage rather than silently extrapolated.

## Cross-cutting edge-case tests (all in `backend/tests/`)

zero-growth DCF collapses to perpetuity check; negative FCFF; g→WACC explosion
flagged; high debt (equity→small/negative, per-share flagged negative rather than
hidden); currency/unit mismatch rejection; missing fields → typed errors, not NaN.
