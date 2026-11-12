# Agent-supplied financial data

## The architecture principle

```
AI agent  = data retrieval and research (it knows the ticker, it finds the facts)
FAIRVALUE = financial validation and calculation (it checks the facts, it runs the models)
```

FAIRVALUE AI is a calculation engine, not a data provider. Any MCP-compatible
agent can submit structured financials for **any publicly traded ticker** —
there is deliberately **no ticker allowlist** — and the engine validates the
submission and runs all nine models on it. Nothing here contacts SEC EDGAR,
FRED, Stooq or any other external source (`fairvalue/data/static.py` serves
only the submitted data), and nothing is ever fabricated: absent concepts are
reported as missing, never defaulted. Existing provider-driven flows (REST,
dashboard, SDK, CLI) are unchanged.

## Workflow (MCP)

```
1. submit_financial_data(data)            -> validation: issues, provenance,
                                             derived_concepts, missing_concepts
2. calculate_valuation_from_data(data,    -> full ValuationReport: 9 models,
      wacc?, price?, models?)                eligibility + reasons, reconciliation,
                                             report_id
3. get_valuation_report(report_id)        -> re-fetch the exact report (traceability)
```

Step 1 is optional (a pre-flight); step 2 validates again before calculating.
The same envelope works over REST: `POST /v1/valuation/from-data`.

## Canonical naming contract

One naming family across every surface — Python `from_data`, URL/doc `from-data`.
This is the ratified contract; the earlier draft names
(`run_valuation_from_agent_data`, `POST /v1/valuation/agent-data`,
`submit_and_value_company`) were **never implemented and are superseded**.

| Surface | Canonical name |
|---|---|
| Service (Python) | `fairvalue.service.run_valuation_from_data(data, opts)` |
| REST | `POST /v1/valuation/from-data` (query: `wacc`, `price`, `models`) |
| MCP validate step | `submit_financial_data(data)` |
| MCP value step | `calculate_valuation_from_data(data, wacc?, price?, models?)` |
| SDK | `FairValueClient.valuation_from_data(data, *, wacc, price, models)` |
| Documentation | `docs/AGENT_DATA.md` (this file) · `docs/API.md` |

Parity across REST/MCP/SDK on one submission is enforced by
`tests/test_from_data_naming_audit.py`.

## Envelope reference

```jsonc
{
  "ticker": "ZZZX",                    // any valid ticker, uppercased; no allowlist
  "name": "Zebra Zoom Inc",            // optional
  "sector": "Technology",              // optional — feeds industry suitability rules
  "industry": "Software",              // optional
  "currency": "USD",                   // facts without a currency tag are in this currency
  "accounting_standard": "US-GAAP",    // optional, echoed in the report (req 5)
  "is_illustrative": false,            // must be explicit; demo data is NEVER substituted
  "periods": [                         // multiple fiscal years; ascending not required
    {
      "period_end": "2025-12-31",
      "period_start": "2025-01-01",    // duration facts; omit for instants (balance sheet)
      "fiscal_period": "FY",           // FY | Q1..Q4 | TTM
      "facts": [
        {"concept": "revenue", "value": 1000.0, "period_end": "2025-12-31",
         "period_start": "2025-01-01",
         "currency": "EUR",            // optional; != company currency needs fx_rates
         "unit": "USD",                // optional; defaults per concept
         "provenance": "reported",     // reported | agent_estimate | user_assumption
         "source": "10-K p.42, filed 2026-01-10"}  // free-text locator, req 6
      ]
    }
  ],
  "market": {                          // optional market inputs the agent retrieved
    "price": 20.0, "as_of": "2026-01-15",
    "shares_outstanding": 100.0, "beta": 1.1,
    "provenance": "reported", "source": "exchange quote 2026-01-15"
  },
  "risk_free_rate": 0.043,             // optional macro input -> CAPM WACC (req 4)
  "erp": 0.05,                         // optional equity risk premium override
  "fx_rates": [ {"from_currency": "USD", "rate": 0.92,
                 "as_of": "2025-12-31", "source": "ECB reference rate"} ],
  "peers":     [ {"ticker": "PA", "enterprise_value": 1200.0, "ebitda": 200.0} ],
  "transactions": [ {"target": "T1", "enterprise_value": 500.0, "ebitda": 50.0} ],
  "segments":  [ {"name": "Cloud", "metric": "ebitda", "value": 80.0} ]
}
```

**Canonical concepts** (everything else is rejected and listed, not stored):
`revenue, gross_profit, ebit, net_income, operating_cash_flow, capex,
depreciation_amortization, cash, total_debt, total_assets, total_liabilities,
current_assets, current_liabilities, equity, shares_outstanding, eps_diluted,
dps`. `ebitda` and `fcf` are **derived by rule** (EBIT+D&A, OCF−capex) and must
not be supplied — the engine derives and labels them `calculated`.

## Provenance taxonomy (req 7)

| Kind | Where it lives | How it is labeled |
|---|---|---|
| Reported fact | `periods[].facts[]` with `provenance: "reported"` | `Fact.source.provider = "agent:reported"`, `is_estimate=False` |
| Agent estimate | same, `provenance: "agent_estimate"` | `"agent:estimate"`-style provider tag, `is_estimate=True` |
| User assumption | request options (`wacc`, `price`, `erp`) — **not** facts | echoed in `ModelResult.assumptions` + rate notes |
| Calculated value | derived by the engine (`ebitda`, `fcf`, `net_debt`, WACC…) | `source.provider = "agent:calculated"` + warnings/steps |

Every fact carries a `SourceRef` with retrieval timestamp (req 6); the
submission's `source` free-text rides in `locator`. Facts missing a `source`
are answered with `"not provided"` — provenance is never invented.

## Validation rules (req 8)

| Rule | Severity | Meaning |
|---|---|---|
| `schema` | error (422) | envelope fails pydantic validation (missing ticker/periods, bad dates) |
| `currency_mismatch` | error | fact tagged in another currency without an `fx_rates` entry — rejected, never converted at a guessed rate |
| `duplicate_conflict` | error | two different values for the same concept/period — fact rejected |
| `derived_concept_supplied` | error | agent sent `ebitda`/`fcf` — rejected, supply the inputs |
| `negative_value` | error | revenue/assets/shares/price negative where the domain forbids it |
| `balance_identity` | warning | assets ≠ liabilities + equity (>1%) — supplied as-is, flagged |
| `eps_consistency` | warning | net_income/shares disagrees with supplied EPS (>25%) |
| `short_period` | warning | flow fact spans <300 days — check quarterly/stub data |
| `unknown_concept` | warning | non-canonical concept rejected and listed |

Hard errors on individual facts drop **that fact** and continue; a submission
with nothing usable is refused outright (`validation_failed`, 422) — the
engine never guesses a replacement value.

## Model eligibility (req 12)

The report always contains all nine models. Each is either `applicable:
true` with full steps/assumptions, or `applicable: false` with an explicit
`excluded_reason` (also aggregated in `reconciliation.excluded`). Typical
agent-data exclusions: no `risk_free_rate`/`wacc` → DCF/EPV excluded; no
cost-of-equity inputs → DDM/residual-income excluded; no peers/transactions/
segments supplied → comparables/precedents/SOTP excluded.

## What is preserved

- All nine models, reconciliation, scenarios, explanation, health/multiples/risks.
- REST, dashboard, SDK, CLI and the original 11 MCP tools: untouched.
- MCP now has 13 tools (11 existing + `submit_financial_data` +
  `calculate_valuation_from_data`).

See [API.md](API.md) for endpoint details and [TESTING.md](TESTING.md) for
the test map (`test_agent_data.py`, `test_from_data_workflow.py`).
