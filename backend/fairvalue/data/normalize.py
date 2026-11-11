"""Normalization: XBRL/raw facts -> canonical concepts, with dedupe,
restatement (conflict) detection and missing-data tracking.

Rules (ARCHITECTURE.md §4):
- one Fact per (concept, period_end): the most recently *filed* value wins,
  older duplicates are dropped (duplicate prevention);
- if two filings report different values for the same key, that is a
  restatement and is recorded as a conflict, never silently ignored;
- ``capex`` is normalized to a positive magnitude;
- nothing is ever inferred to fill a gap — gaps become ``missing_concepts``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fairvalue.core.schemas import (
    CANONICAL_CONCEPTS,
    FLOW_CONCEPTS,
    Fact,
    Fundamentals,
    PeriodFinancials,
    SourceRef,
)

# us-gaap / dei tag candidates per canonical concept, highest priority first.
TAG_MAP: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "ebit": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "total_debt": ["DebtLongtermAndShorttermCombinedAmount", "LongTermDebt"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "shares_outstanding": ["CommonStockSharesOutstanding", "CommonStockSharesIssued"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "dps": ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
    "ebitda": [],  # never a tag: derived by the service as ebit + D&A (documented)
}

#: used only when the primary total_debt tags are absent
COMBINED_DEBT_TAGS = ["LongTermDebtNoncurrent", "LongTermDebtCurrent"]

DEI_SHARES_TAG = "EntityCommonStockSharesOutstanding"

UNIT_BY_CONCEPT = {
    "shares_outstanding": "shares",
    "eps_diluted": "USD/shares",
    "dps": "USD/shares",
}

ANNUAL_FORMS = ("10-K", "10-K/A", "20-F", "20-F/A")


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def select_annual_entries(entries: list[dict], concept: str) -> list[dict]:
    """Keep only annual (FY, 10-K/20-F) observations; flows need a ~1-year duration."""
    out = []
    for e in entries:
        if not str(e.get("form", "")).startswith(("10-K", "20-F")):
            continue
        if e.get("fp") != "FY":
            continue
        end = e.get("end")
        if not end:
            continue
        if concept in FLOW_CONCEPTS and concept != "shares_outstanding":
            start = e.get("start")
            if not start:
                continue
            days = (_parse_day(end) - _parse_day(start)).days
            if not (300 <= days <= 380):  # quarterly or stub periods are not annual
                continue
        out.append(e)
    return out


def normalize_entries(
    concept: str,
    entries: list[dict],
    *,
    provider: str,
    locator: str | None,
    is_illustrative: bool = False,
) -> tuple[list[Fact], list[str]]:
    """Deduplicate raw XBRL entries into one Fact per period, reporting restatements."""
    facts: dict[date, Fact] = {}
    conflicts: list[str] = []
    seen: dict[date, set[float]] = {}
    now = datetime.now(timezone.utc)
    unit = UNIT_BY_CONCEPT.get(concept, "USD")

    for e in sorted(select_annual_entries(entries, concept), key=lambda x: x.get("filed", "")):
        end = _parse_day(e["end"])
        val = float(e["val"])
        if concept == "capex":
            val = abs(val)  # cash-flow-stated outflows normalized to positive spend
        filed = datetime.fromisoformat(e["filed"]).replace(tzinfo=timezone.utc) if e.get("filed") else now

        if end in facts:
            seen.setdefault(end, {facts[end].value}).add(val)
            if len(seen[end]) > 1:
                msg = f"{concept} @{end}: restated {sorted(seen[end])} (latest filing wins)"
                if msg not in conflicts:
                    conflicts.append(msg)
        else:
            seen[end] = {val}

        facts[end] = Fact(  # later filings overwrite earlier ones (sorted by filed)
            concept=concept,
            value=val,
            unit=unit,
            period_start=_parse_day(e["start"]) if e.get("start") else None,
            period_end=end,
            fiscal_year=int(e.get("fy") or end.year),
            fiscal_period="FY",
            is_estimate=False,
            form=e.get("form"),
            filed_at=filed,
            is_illustrative=is_illustrative,
            source=SourceRef(provider=provider, locator=locator, retrieved_at=now),
        )
    return sorted(facts.values(), key=lambda f: f.period_end), conflicts


def build_periods(concept_facts: dict[str, list[Fact]]) -> tuple[list[PeriodFinancials], list[str]]:
    """Group per-concept facts into fiscal periods (ascending). Missing canonical
    concepts (no fact in the *latest* period) are reported, never filled."""
    by_key: dict[tuple[int, date], dict[str, Fact]] = {}
    for concept, facts in concept_facts.items():
        for f in facts:
            by_key.setdefault((f.fiscal_year, f.period_end), {})[concept] = f

    periods = [
        PeriodFinancials(fiscal_year=ky[0], period_end=ky[1], facts=fs)
        for ky, fs in sorted(by_key.items(), key=lambda kv: kv[0][1])
    ]
    missing: list[str] = []
    if periods:
        latest = periods[-1]
        missing = [c for c in CANONICAL_CONCEPTS if c not in latest.facts and c != "ebitda"]
    return periods, missing


def assemble_fundamentals(company, concept_facts, conflicts) -> Fundamentals:
    periods, missing = build_periods(concept_facts)
    return Fundamentals(
        company=company, periods=periods, missing_concepts=missing, conflicts=conflicts
    )
