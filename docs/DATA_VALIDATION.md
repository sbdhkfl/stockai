# Data Validation & Provenance Specification

Implemented in `backend/fairvalue/data_quality.py`.

## Provenance kinds (enforced enum)
`reported` (from filings) · `guidance` (company) · `estimate` (analyst consensus) ·
`model_assumption` · `ai_interpretation`.
**Rule:** an `estimate` or `ai_interpretation` value may never be rendered as a
reported fact in output; the presentation layer must label it.

## Validation rules

| Rule | Check | Severity |
|---|---|---|
| missing_value | required field absent/NaN | error |
| wrong_unit | value outside plausible magnitude band for its unit declaration (e.g., revenue of 5,000 when filings are in thousands → likely $5,000M) | warning |
| currency_mismatch | mixed currency codes within one composite | error |
| period_mismatch | mixing fiscal-year ends > 35 days apart in one composite | warning |
| duplicate_record | same (company, statement, line_item, period, source) more than once | error |
| restatement | value flagged as restatement_of an earlier value | warning (prefer newest, keep both) |
| negative_value | negative where domain forbids (revenue, shares, assets) | error |
| outlier | value beyond ±5 robust MAD from peer/series median | warning |
| share_count_inconsistency | diluted < basic, or share count change > 20% unexplained YoY | error |
| stale_data | last statement period older than 550 days from valuation date | warning |

## Design rules
- Validation **never repairs data silently**. It classifies issues and lets the
  caller decide; hard errors block valuation, warnings attach to output.
- Each issue record: `{rule, field, message, severity, value_seen}`.
- Composite inputs (e.g., ratios across statements) are only computed when all
  components share currency and period alignment; otherwise a period_mismatch
  warning is attached to the result.
