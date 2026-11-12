

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
