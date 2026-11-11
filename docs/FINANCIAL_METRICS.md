# Financial Metrics — Definitions & Formulas

All implemented in `backend/fairvalue/metrics.py`. Decimal conventions: ratios are
unitless; CAGR is annualized decimal. Every function returns the formula used.

## Profitability
- Gross margin = (Revenue − COGS) / Revenue
- Operating margin = Operating income / Revenue
- Net margin = Net income / Revenue
- ROA = Net income / Average total assets
- ROE = Net income / Average equity (if avg components missing, uses end balance and flags `end_balance_proxy`)
- ROIC = NOPAT / Invested capital; NOPAT = EBIT×(1−t); Invested capital = total debt + equity − cash & equivalents (average if both periods present)

## Liquidity
- Current ratio = Current assets / Current liabilities
- Quick ratio = (Current assets − Inventory) / Current liabilities
- Cash ratio = Cash & equivalents / Current liabilities

## Solvency
- Debt-to-equity = Total debt / Total equity
- Net debt / EBITDA (EBITDA must be provided; we do not fabricate it from EBIT + guessed D&A unless both are given)
- Interest coverage = EBIT / Interest expense (EBIT ≤ 0 → not meaningful, reported as such)
- Debt maturity exposure = share of total debt maturing within a horizon (needs maturity schedule)

## Efficiency
- Asset turnover = Revenue / Average total assets
- Inventory turnover = COGS / Average inventory
- Receivables turnover = Revenue / Average receivables

## Growth
- CAGR(end, begin, years) = (end/begin)^(1/years) − 1; undefined for begin ≤ 0 or years ≤ 0 — errors, not fake numbers
- Per-share growth uses diluted EPS series

## Valuation ratios
- P/E = Price / diluted EPS (negative EPS → not meaningful)
- P/S, P/B (P/B with negative book → not meaningful)
- EV/EBITDA, EV/Sales, EV/EBIT
- FCF yield = FCF / Market cap; Earnings yield = EPS / Price

## Accounting considerations
- Average balances for return/turnover ratios to match numerator (flow) with denominator (stock).
- Operating leases: pre-ASC 842/IFRS 16 statements understate debt; engine flags `lease_adjustment_needed` when lease data supplied.
- SBC: treated as economic expense in EPV/adjusted metrics; reported (GAAP) figures left untouched and labeled.
