# Risk Methodology

Implemented in `backend/fairvalue/risk.py`. Principle: **historical volatility is
NOT a complete measure of business risk.** Volatility measures price behavior;
business risk is the probability distribution of future cash flows, which depends
on leverage, cyclicality, concentration, regulation, and balance-sheet resilience.

## Quantitative risk scores

### Altman Z-score (manufacturing/public-firm weights)
`Z = 1.2·WC/TA + 1.4·RE/TA + 3.3·EBIT/TA + 0.6·MVE/TL + 1.0·Sales/TA`
Zones (original 1968/2000 cutoffs): Z > 2.99 safe; 1.81–2.99 grey; < 1.81 distress.

**Applicability limits (documented and enforced by warnings in code):**
- Original weights fit *public manufacturing* firms. Private-firm and
  non-manufacturer variants exist (Z′, Z″) and must not be silently substituted.
- Service firms, financials, and REITs: MVE/TL and RE terms distort; use
  sector-appropriate distress models instead. The engine refuses banking/insurance
  inputs with an explanatory error.
- Z-score is a *screening* statistic, not a probability of bankruptcy.

### Deterministic flags (v1)
- Interest coverage < 2.0 → `leverage_risk`
- Net debt / EBITDA > 4.0 → `leverage_risk`
- Current ratio < 1.0 → `liquidity_risk`
- Revenue coefficient of variation (≥5 years) > 0.35 → `earnings_volatility`
- Negative operating cash flow in ≥2 of last 3 years → `cash_flow_instability`

Planned (specified, not yet implemented): customer/industry concentration
(HHI), regulatory-exposure rubric, FX/interest-rate sensitivity via scenario
engine (`docs/SCENARIO_ANALYSIS.md`).

## Output honesty rules
- Every risk output lists which inputs produced it.
- Missing inputs are reported as gaps, never defaulted to zero.
- No risk score is presented as a calibrated probability.
