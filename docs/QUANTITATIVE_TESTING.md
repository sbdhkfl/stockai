# Quantitative Testing Doctrine

All tests in `backend/tests/`. Doctrine: **every expected value is independently
hand-derived in this document or inline in the test; no test merely asserts "a
number came out".**

## Reference hand calculations (canonical test fixtures)

**DCF-1** — FCFF=[100,100,100], WACC=10%, g=2%, net debt=200, diluted=50:
- PV terms: 90.9090909, 82.6446281, 75.1314801 → Σ = 248.6851991
- TV = 100×1.02/0.08 = 1275; PV(TV) = 1275/1.331 = 957.9263711
- EV = 1206.6115702; Equity = 1006.6115702; **per share = 20.1322314**

**DCF-2 (zero growth, g=0)** — FCFF=[100,100,100], WACC=10%, g=0:
TV = 100/0.10 = 1000; PV(TV)=751.3148009; EV = 248.6851991+751.3148009 = 1000.0000000
(nice internal-consistency check: a flat perpetuity valued exactly).

**DDM-1** — D0=2, r=10%, g=5% → P0 = 2×1.05/0.05 = **42.0**

**RI-1** — B0=100, E=[15,15], r=10%, no dividends:
RI₁ = 15−10 = 5 → PV 4.5454545; B1 = 115; RI₂ = 15−11.5 = 3.5 → PV 2.8925620
V0 = **107.4380165**

**EPV-1** — EBIT=100, tax=25%, SBC=10, maint capex=20, D&A=15, r=10%:
norm. earnings = (100−10)×0.75 − 5 = 62.5 → **EPV = 625**

**Graham-1** — EPS=2, g=5, Y=4.4 → V = 2×(8.5+10)×4.4/4.4 = **37.0**

**Altman-1** — WC=100, TA=1000, RE=200, EBIT=100, MVE=500, TL=400, Sales=1500:
Z = 0.12+0.28+0.33+0.75+1.5 = **2.98 → grey zone**

**CAGR-1** — 100→121 over 2y = **10.0%**

**Median-1** — [1,2,3,4,5]→3; [1,2,3,4]→2.5

## Test classes required per model
known-answer · boundary (g=0, g→WACC limit flagged) · negative earnings/FCFF ·
high-debt (negative equity per share surfaced, not clamped) · share-count
variation (equity value invariant to share split; per-share scales inversely) ·
currency/period mismatch rejection · missing data → typed errors · extreme
discount rate (r ≤ 0 rejected; r ≥ 50% allowed but flagged).

## Independent audit requirement
The auditor (Quant Agent) may not reuse the implementation's intermediate values
to build expectations — expectations come from the hand math above or an
independent recomputation path.
