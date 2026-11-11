# Financial Methodology — FAIRVALUE AI

Author: Quant Agent. Status: living document; formulas here are implemented and
unit-tested in `backend/fairvalue/` with hand-derived expected values.

## 0. Global conventions

- **Currency & units:** every input carries explicit units; the engine never mixes
  currencies. Conversions must happen upstream with a dated FX rate recorded in provenance.
- **Shares:** per-share outputs use **diluted** shares (treasury-stock method where
  available). Basic shares only when diluted is unavailable, flagged in provenance.
- **Enterprise vs equity value:**
  `EV = equity value + total debt + minority interest + preferred − cash & equivalents`.
  FCFF discounts to EV; FCFE/coupon-type flows discount to equity directly. Confusing
  the two is the most common valuation error; both directions are tested.
- **Mid-year convention:** not used in v1 (end-of-year flows) — documented assumption.
- **Negative-value policy:** never silently clamp. Negative FCFF propagates; the
  DCF refuses to compute a terminal value from a negative base-year FCFF and
  returns a `not_meaningful` flag instead.

## 1. Discounted Cash Flow (2-stage FCFF)

```
PV_explicit = Σ_{t=1..N} FCFF_t / (1+WACC)^t
TV          = FCFF_N × (1+g) / (WACC − g)      [Gordon terminal, g < WACC enforced]
EV          = PV_explicit + TV / (1+WACC)^N
Equity      = EV − net debt                     [net debt = debt − cash]
Per share   = Equity / diluted shares
```

- WACC = (E/V)·Re + (D/V)·Rd·(1−t); Re via CAPM = rf + β·ERP.
- Constraints enforced: `0 ≤ g < WACC`; N ≥ 1; FCFF_t finite.
- Limitations: unsuitable for banks/insurers (interest is operating); poor for
  negative-FCFF startups unless explicit horizon covers cash-flow turn.
- See `docs/VALUATION_MODELS.md` for full input dictionary.

## 2. Dividend Discount Model

Gordon: `P0 = D1 / (r − g)`, D1 = D0·(1+g), with `g < r` enforced.
Two-stage: explicit high-growth dividends then Gordon terminal. Suitable for
mature dividend payers, banks, utilities. Unsuitable for non-payers or
buyback-heavy firms (use FCFE instead).

## 3. Residual Income

```
V0 = B0 + Σ_{t=1..N} (E_t − r·B_{t−1}) / (1+r)^t     (+ optional continuing RI premium)
```
Book value is equity book value; r is cost of equity. Works when FCFF is negative
for the forecast horizon. Premium over book exists only if ROE ≠ r. Particularly
appropriate for financial firms whose book value is meaningful.

## 4. Earnings Power Value (Greenwald)

`EPV = adjusted normalized earnings / cost of capital`, growth-free by design.
Adjusted earnings = EBIT − (maintenance capex − D&A adjustments), after tax, with
SBC treated as a real expense. EPV ≈ reproduction-value comparison yields franchise
margin. Suitable for stable incumbents; not for cyclicals at peak earnings.

## 5. Graham-style valuation

Revised Graham formula: `V = EPS × (8.5 + 2g) × 4.4 / Y`
(EPS diluted trailing; g = 7–10y expected growth in % points; Y = current AAA
corporate yield, %). Capped growth input at 15 in our implementation because the
formula degrades empirically for high-growth names (documented limitation).
Graham Number: `√(22.5 × EPS × BVPS)` — a defensive floor, not a fair value.

## 6. Asset-Based Valuation

Adjusted NAV = Σ fair-valued assets − liabilities, with stated adjustment schedule
(mark-to-market, receivable aging haircuts, off-balance-sheet items). Suitable for
holding companies, REITs (alongside NAV models), liquidators, deep-value; not for
going-concern franchise businesses.

## 7. Sum-of-the-Parts

Each segment valued by the model suited to it (DCF, multiples, NAV), summed at
[consolidated EV − net debt − unallocated corporate costs capitalized]. Requires
segment-level disclosure; hidden-value claim must survive a conglomerate-discount check.

## 8. Comparable Company Analysis

Implied value = peer **median** multiple (robust to outliers) × target metric.
Screening rules for peer sets: same GICS sector/industry, size band ±50% revenue,
positive metric (a negative-EBIT peer's multiple is undefined and must be excluded,
never treated as 0). EV multiples pair with EV-level numerators/denominators;
equity multiples with equity-level. Leverage differences make EV/EBITDA preferred
cross-capital-structure; P/E only among comparable leverage and growth.

## References

- Koller, Goedhart, Wessels. *Valuation* (McKinsey & Company), Wiley.
- Damodaran, *Investment Valuation* ( Damodaran on Valuation materials, NYU Stern).
- Penman, *Financial Statement Analysis and Security Valuation*.
- Greenwald et al., *Value Investing: From Graham to Buffett and Beyond*.
- Graham, *The Intelligent Investor* (revised edition formula appendix).
- CFA Institute curriculum, Equity Valuation readings.
- Altman, E. (1968; 2000 revision) "Predicting Financial Distress of Companies".
