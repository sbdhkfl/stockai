# Scenario & Sensitivity Analysis

Implemented in `backend/fairvalue/scenario.py`.

## Standard scenarios (bear / base / bull)

Deltas applied to a DCF input set. All deltas move **together** for internal
consistency (a bear case does not cut growth while assuming margin expansion):

| Input | Bear | Base | Bull |
|---|---|---|---|
| FCFF path | ×0.70 | ×1.00 | ×1.25 |
| Terminal growth | −100 bp | 0 | +50 bp (capped < WACC−100bp) |
| WACC | +150 bp | 0 | −100 bp |
| Net debt | +10% (downside refinancing) | 0 | 0 |

Consistency constraints enforced after delta application:
`g < WACC − 50 bp` (margin of safety against near-zero terminal PV denominator);
scenarios re-clamp g and record it.

## Sensitivity grid
Two-parameter grid (default: WACC × terminal growth) of per-share values,
computed on the **base** inputs. Used to show fair-value dispersion across
reasonable assumption ranges — the honest alternative to a false single number.

## Probabilistic simulation (specified; scheduled)
Monte-Carlo over correlated assumption distributions is specified but must obey
these presentation rules:
- Output distributions are **conditional on the assumed input distributions**;
  they are not guaranteed probabilities of future outcomes.
- Correlation structure (e.g., growth↔margin) must be stated, not implicit.

## Interpretation rules
- Never collapse a scenario range to one number without labeling the aggregation.
- Confidence levels in reconciliation (`docs/QUANTITATIVE_TESTING.md` § reconciliation)
  reflect data quality + model suitability + assumption uncertainty; they are
  **not** statistically calibrated probabilities unless derived from an actual
  calibrated model (none exists in v1 — stated plainly).
