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
    # validation-only view: consolidated equity (parent + noncontrolling interests)
    "equity_including_nci": [
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "StockholdersEquity",
    ],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
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
    """Deduplicate raw XBRL entries into one Fact per period, reporting restatements.

    - duration facts keep their actual ``start``/``end`` and ``basis='duration'``;
    - instant facts have no start and ``basis='instant'``;
    - accession number and filing date are preserved on every fact;
    - when filings disagree on the same period (restatement/amendment), the most
      recently filed value wins and the disagreement is reported as a conflict.
    """
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
        start = e.get("start")

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
            basis="duration" if start else "instant",
            period_start=_parse_day(start) if start else None,
            period_end=end,
            # XBRL ``fy`` is the *filing's* fiscal-year context: comparative rows in a
            # newer 10-K carry the newer fy and would split/duplicate periods.
            # The calendar year of period_end is the only stable period identifier.
            fiscal_year=end.year,
            fiscal_period="FY",
            is_estimate=False,
            form=e.get("form"),
            accession=e.get("accn"),
            filed_at=filed,
            is_illustrative=is_illustrative,
            source=SourceRef(provider=provider, locator=locator, retrieved_at=now),
        )
    return sorted(facts.values(), key=lambda f: f.period_end), conflicts


def build_periods(concept_facts: dict[str, list[Fact]]) -> tuple[list[PeriodFinancials], list[str]]:
    """Group per-concept facts into fiscal periods keyed by ``period_end`` (ascending).

    ``shares_outstanding`` (a dei cover-page instant with its own filing date) never
    creates a period of its own: it is attached to the latest financial period.
    Missing canonical concepts in the latest period are reported, never filled.
    """
    by_key: dict[date, dict[str, Fact]] = {}
    share_fact: Fact | None = None
    for concept, facts in concept_facts.items():
        for f in facts:
            if concept == "shares_outstanding":
                share_fact = f
                continue
            by_key.setdefault(f.period_end, {})[concept] = f

    periods = [
        PeriodFinancials(fiscal_year=end.year, period_end=end, facts=fs)
        for end, fs in sorted(by_key.items())
    ]
    if share_fact is not None and periods:
        last = periods[-1]
        periods[-1] = last.model_copy(
            update={
                "facts": {
                    **last.facts,
                    "shares_outstanding": share_fact.model_copy(
                        update={"period_start": None, "period_end": last.period_end,
                                "fiscal_year": last.fiscal_year}
                    ),
                }
            }
        )
    missing: list[str] = []
    if periods:
        latest = periods[-1]
        missing = [c for c in CANONICAL_CONCEPTS if c not in latest.facts and c != "ebitda"]
    return periods, missing


def validate_statements(periods: list[PeriodFinancials]) -> list[str]:
    """Structural checks on normalized statements.

    Successful retrieval is NOT proof of a correct statement (AGENT_TASKS rule):
    every period with a full balance sheet must satisfy A = L + E within 1%,
    and impossible values are flagged. Results are reported, never repaired.
    """
    errors: list[str] = []
    for p in periods:
        f = p.facts
        a, l = f.get("total_assets"), f.get("total_liabilities")
        # balance check needs CONSOLIDATED equity: parent equity + NCI, when reported
        e = f.get("equity_including_nci") or f.get("equity")
        if a and l and e and a.value:
            diff = abs(a.value - (l.value + e.value)) / abs(a.value)
            if diff > 0.01:
                errors.append(
                    f"balance sheet does not balance @{p.period_end}: assets {a.value:,.0f} vs "
                    f"liabilities+equity {l.value + e.value:,.0f} (diff {diff:.1%}) — "
                    "possible noncontrolling interests, wrong equity tag, or data error"
                )
        e_parent = f.get("equity")
        if a and e_parent and e_parent.value > a.value * 1.001:
            errors.append(f"equity exceeds total assets @{p.period_end} ({e_parent.value:,.0f} > {a.value:,.0f})")
        cash = f.get("cash")
        if a and cash and cash.value > a.value * 1.001:
            errors.append(f"cash exceeds total assets @{p.period_end}")
        re_ = f.get("retained_earnings")
        if a and re_ and abs(re_.value) > abs(a.value) * 2:
            errors.append(
                f"retained earnings implausible @{p.period_end}: {re_.value:,.0f} vs total assets {a.value:,.0f}"
            )
        sh = f.get("shares_outstanding")
        if sh is not None and sh.value <= 0:
            errors.append(f"non-positive shares outstanding @{p.period_end}")
        rev = f.get("revenue")
        if rev is not None and rev.value < 0:
            errors.append(f"negative revenue @{p.period_end}: {rev.value:,.0f}")
    return errors


def assemble_fundamentals(company, concept_facts, conflicts) -> Fundamentals:
    periods, missing = build_periods(concept_facts)
    return Fundamentals(
        company=company,
        periods=periods,
        missing_concepts=missing,
        conflicts=conflicts,
        validation_errors=validate_statements(periods),
    )
