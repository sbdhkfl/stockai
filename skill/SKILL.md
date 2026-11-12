---
name: fairvalue-ai
description: >
  Transparent, model-independent stock valuation via FAIRVALUE AI. Use when a
  user asks to value a company, analyze financial health, run bull/base/bull
  scenarios, or explain a valuation. Every result carries assumptions,
  provenance, and limitations. Never present estimates as reported facts.
version: 1.0.0
---

# FAIRVALUE AI — Agent Skill

A valuation engine that returns **reproducible, explainable** results: which
models ran, which inputs they used (with SEC provenance), step-by-step math,
and explicit limitations. Deterministic — the same inputs always produce the
same numbers. No LLM inside the calculation path.

## Setup

```bash
cd backend
pip install -e ".[mcp]"          # or: pip install -r requirements.txt
```

Two ways to invoke:

1. **MCP tools** (for MCP-compatible assistants) — register the server:
   `python -m fairvalue.mcp_server` (stdio transport).
2. **REST API** — `uvicorn api.main:app` then HTTP calls below.

Data sources: SEC EDGAR (real filings), FRED (risk-free rate), Stooq (prices).
Offline/demo mode returns clearly-labeled **illustrative** data (`is_illustrative:
true`) — never present it as real.

## Core usage

### One-call full valuation (recommended)

MCP: `calculate_valuation(ticker="AAPL")`
REST: `GET /v1/companies/AAPL/valuation`

Returns a `ValuationReport`: all suitable models with per-model `steps`
(derivation), `assumptions` (echoed), `limitations`, `warnings`;
a `reconciliation` (base/low/high range across model families — never a blind
average); `scenarios` (bear/base/bull + WACC×growth sensitivity); `health`,
`multiples`, `growth`, `risks` (incl. Altman Z screen); `explanation` (plain
language); `data_quality` (missing concepts, restatement conflicts, sources).

### Other tools

| Tool | Purpose |
|---|---|
| `search_company(q)` | resolve a name/ticker |
| `get_financial_statements(t)` | normalized filings + provenance |
| `get_financial_metrics(t)` | health metrics + current multiples |
| `calculate_dcf(t, wacc?)` | DCF only, with derivation steps |
| `compare_competitors(t)` | peer multiples |
| `analyze_financial_health(t)` | margins, ROE/ROIC, leverage |
| `analyze_risks(t)` | Altman Z screen, leverage & FCF flags |
| `run_scenario_analysis(t, wacc?)` | bear/base/bull + sensitivity grid |
| `explain_valuation(t)` | deterministic narrative |
| `get_valuation_report(id)` | fetch a stored report |

## Mandatory behavior rules for the calling agent

1. **Provenance:** quote figures with their source and period ("per the FY2025
   10-K, filed 2025-11-03"). Never strip provenance from a result.
2. **Estimates ≠ facts:** model outputs are estimates conditional on stated
   assumptions. Say so every time. Never present a valuation as "the" fair value.
3. **Illustrative data:** if `is_illustrative: true`, you MUST say the numbers
   are illustrative demo data, not real filings.
4. **Missing data:** if `data_quality.missing` lists concepts, say the analysis
   is limited; never guess the missing numbers.
5. **Ranges, not points:** report the reconciliation range (low/base/high) and
   the scenario spread. Confidence labels are structured judgments, NOT
   calibrated probabilities.
6. **Risk screens:** Altman Z is a screening statistic, not a bankruptcy
   probability; it is not calibrated for banks/insurers.
7. **No investment advice:** outputs are research artifacts. Add that caveat.

## Worked example (MCP)

```
> calculate_valuation(ticker="AAPL")
{
  "company": {"ticker": "AAPL", "name": "Apple Inc.", ...},
  "models": [
    {"model": "dcf", "applicable": true, "value_per_share": ...,
     "assumptions": {"wacc": ..., "terminal_growth": 0.025, ...},
     "steps": ["Base revenue 416,161,...", ...],
     "limitations": ["Terminal value dominates ..."]}
  ],
  "reconciliation": {"low": ..., "base": ..., "high": ...,
                     "method": "base = median of family aggregates ..."},
  "scenarios": {"bear": {...}, "base": {...}, "bull": {...}, "sensitivity": [...]},
  "data_quality": {"missing": [...], "conflicts": [...], "sources": [...]},
  "is_illustrative": false
}
```

Report to the user, e.g.: "Under the stated assumptions (WACC x%, terminal
growth y%), DCF implies $A–$B/share; peer multiples imply $C–$D. The
reconciled range is $L–$H with a base of $M. Based on the FY2025 10-K. Key
limitations: terminal value contributes N% of EV; interest expense is not in
the concept set, so interest coverage was not computed. This is analysis, not
investment advice."

## What this tool will NOT do

- Fabricate missing financials (gaps are reported as gaps).
- Apply DCF to banks/insurers (sector rules route to residual income/DDM).
- Average all models into one number without family grouping and recorded weights.
- Return a confidence score claiming statistical calibration.
