# Industry-Specific Valuation & Metrics Framework

Classification drives model selection. **Financial institutions are excluded from
standard DCF by default** (interest is both operating and financing; free cash flow
is not well-defined). Framework below is PROPOSED pending OpenCode's data-availability
constraints.

| Sector | Primary models | Sector metrics | Standard-DCF policy |
|---|---|---|---|
| Technology (software) | DCF (FCFF), EV/Sales comps, Rule-of-40 screen | Net revenue retention, gross retention/churn, CAC, CAC payback, LTV/CAC, R&D % revenue, SBC % revenue | Allowed; SBC dilution modeled via diluted share growth |
| Banking | Residual income, P/B vs ROE regression, DDM | NIM, NPL/nonaccrual %, loan-loss reserve coverage, CET1 ratio, deposit mix & cost, ROE/ROTCE | DCF refused; use RI/DDM |
| Insurance | P/B-ROE, embedded value (life), combined-ratio trend | Combined ratio (CR = loss ratio + expense ratio), reserve development, net investment yield, float | DCF refused |
| Retail | EV/EBITDA comps, EPV, store-level economics | Same-store sales, inventory turnover, gross margin, sales per sq ft, lease-adjusted leverage | Allowed with lease capitalization |
| Real estate / REITs | NAV, FFO/AFFO yield, cap-rate DCF | FFO = NI + RE depreciation − gains on sale; AFFO = FFO − maintenance capex − straight-line rent adj; occupancy, WALT | Use FFO-based; GAAP D&A misleads |
| Energy | NAV of reserves (commodity-price deck), EV/EBITDAX | Production, proved reserves (1P/2P), reserve life, finding & development cost, hedging %, capex intensity | DCF with explicit price-deck assumptions |
| Industrials | DCF, EV/EBIT comps | Backlog/book-to-bill, capacity utilization, operating margin, capital intensity (capex/revenue) | Allowed |
| Healthcare (pharma/biotech) | DCF with pipeline probability weighting, rNPV | Patent cliffs, trial success rates, R&D productivity | Probabilistic; success rates documented per asset, never presented as certainty |
| Utilities/telecom | DCF + DDM | Regulated ROE, rate base, capex plans, dividend payout | Allowed; low growth, high capex |
| Financial holding / asset managers | DDM, P/E, P/AUM margins | AUM flows, fee rate, margin | DCF refused |

Implementation status: v1 ships generic models + banking/insurance exclusion rules
in `valuation/dcf.py` (`sector="banking"|"insurance"` raises `NotSuitableError`)
and residual income as the bank-appropriate alternative. Remaining sector models
are specified here and scheduled in `AGENT_TASKS.md`.
