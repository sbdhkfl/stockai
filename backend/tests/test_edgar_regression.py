"""SEC EDGAR pipeline regression tests.

Real-data fixtures (AAPL, JNJ, WMT — tech / healthcare-staples / retail with
three different fiscal-year conventions) were recorded from live
data.sec.gov companyfacts by scripts/make_fixtures.py. Synthetic cases cover
amendments, comparative periods, and the DEI cover-page share-count trap.

Regression context: the fixture loader once produced ZERO periods for real
10-K data (taxonomy key spelling us-gaap vs us_gaap, list-vs-node shapes) —
every test here exists so that failure can never silently return.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from fairvalue.core.schemas import CompanyProfile, SourceRef
from fairvalue.data.edgar import extract_concepts, DEI_SHARES_TAG
from fairvalue.data.normalize import (assemble_fundamentals, build_periods,
                                      validate_statements)

FIXTURES = Path(__file__).parent / "fixtures"
NOW = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

# JNJ's FY ends the Sunday nearest Dec 31 (can spill into early January);
# Walmart's ends Jan 31 (+ Feb 1 occasionally). Apple's is strictly late Sept.
EXPECTED_FY_MONTH = {"AAPL": {9}, "JNJ": {12, 1}, "WMT": {1, 2}}


def load(ticker):
    path = FIXTURES / f"{ticker.lower()}_facts.json"
    if not path.exists():
        pytest.skip(f"fixture missing: run scripts/make_fixtures.py")
    fx = json.loads(path.read_text(encoding="utf-8"))
    company = CompanyProfile(ticker=ticker, name=ticker, cik=fx["cik"],
                             provider="sec_edgar")
    src = SourceRef(provider="sec_edgar", locator=fx["locator"], retrieved_at=NOW)
    cf, conflicts = extract_concepts(fx, locator=fx["locator"])
    return assemble_fundamentals(company, cf, conflicts)


@pytest.mark.parametrize("ticker", ["AAPL", "JNJ", "WMT"])
def test_real_filings_produce_periods(ticker):
    """Regression: real companyfacts must never normalize to zero periods."""
    fund = load(ticker)
    assert len(fund.periods) >= 5, f"{ticker}: only {len(fund.periods)} periods"


@pytest.mark.parametrize("ticker,months", EXPECTED_FY_MONTH.items())
def test_periods_grouped_by_actual_fiscal_year_end(ticker, months):
    """Facts must group by the real reporting period end, not the filing's fy tag:
    Apple FYs end in September, Walmart's in late January, J&J's in December."""
    fund = load(ticker)
    ends = [p.period_end for p in fund.periods]
    assert all(d.month in months for d in ends), f"{ticker}: unexpected FY-end months {set(d.month for d in ends)}"


def test_dei_cover_page_never_creates_phantom_period():
    """The dei share count is an instant with its own filing date; it must be
    attached to the latest FINANCIAL period, never spawn a period of its own."""
    fund = load("AAPL")
    latest = fund.periods[-1]
    assert "shares_outstanding" in latest.facts
    assert latest.facts["shares_outstanding"].value > 0
    # no period exists that holds ONLY the share count
    for p in fund.periods:
        assert len(p.facts) >= 2, f"phantom period {p.period_end} with facts {list(p.facts)}"


def test_provenance_preserved_on_real_facts():
    fund = load("AAPL")
    rev = fund.periods[-1].facts["revenue"]
    assert rev.accession and rev.accession.startswith("000")
    assert rev.filed_at is not None
    assert rev.source.provider == "sec_edgar"
    assert rev.form in ("10-K", "10-K/A")


def test_restated_values_reported_not_silently_overwritten():
    """Real filings restate history; the engine must record conflicts while
    keeping the most recently filed value."""
    fund = load("AAPL")
    assert len(fund.conflicts) > 0
    assert all("restated" in c and "latest filing wins" in c for c in fund.conflicts)
    # latest-FILED wins (not necessarily the largest value — amendments can
    # restate downwards; e.g. Apple's 10-K/A restated 2008 current assets down)
    import re
    c = fund.conflicts[0]
    m = re.match(r"(\S+) @(\d{4}-\d{2}-\d{2}): restated \[(.+)\]", c)
    concept, end, vals = m.group(1), date.fromisoformat(m.group(2)), [
        float(v) for v in m.group(3).split(",")]
    period = next((p for p in fund.periods if p.period_end == end), None)
    assert period is not None and concept in period.facts
    stored = period.facts[concept]
    # independent check: the stored accession must be the most recently FILED
    # raw entry for that (concept, end) in the fixture
    fx = json.loads((FIXTURES / "aapl_facts.json").read_text(encoding="utf-8"))
    tag = {"current_assets": "AssetsCurrent"}.get(concept)
    entries = [e for e in fx["us_gaap"][tag]
               if e.get("end") == str(end) and e.get("form", "").startswith("10-K")]
    newest = max(entries, key=lambda e: e["filed"])
    assert stored.value == float(newest["val"])
    assert stored.accession == newest["accn"]
    assert float(newest["val"]) in vals


def test_comparative_periods_dont_duplicate():
    """A newer 10-K re-reports prior-year comparatives under its own fy tag;
    grouping by period_end must collapse them into one fact per period."""
    fund = load("WMT")
    ends = [p.period_end for p in fund.periods]
    assert len(ends) == len(set(ends))


def test_balance_sheet_validation_catches_synthetic_imbalance():
    fund = load("AAPL")
    assert fund.validation_errors == []  # real filings must balance
    # synthetic corruption: assets inflated 2x -> structural check must fire
    broken = []
    for p in fund.periods[-1:]:
        from fairvalue.core.schemas import PeriodFinancials
        fs = dict(p.facts)
        fs["total_assets"] = fs["total_assets"].model_copy(update={"value": fs["total_assets"].value * 2})
        broken.append(PeriodFinancials(fiscal_year=p.fiscal_year, period_end=p.period_end, facts=fs))
    errs = validate_statements(broken)
    assert any("does not balance" in e for e in errs)


def test_extract_never_fabricates_missing_concepts():
    fund = load("WMT")
    # Walmart does not report the canonical GrossProfit tag in these filings
    assert "gross_profit" in fund.missing_concepts
    latest = fund.periods[-1]
    assert "gross_profit" not in latest.facts


def test_unknown_node_shape_raises_not_silently_empty():
    with pytest.raises(ValueError):
        extract_concepts({"us-gaap": {"Assets": 42}}, locator="x")


def test_synthetic_amendment_conflict_and_latest_wins():
    """10-K/A amends a figure: latest filing wins, conflict recorded."""
    from fairvalue.data.normalize import normalize_entries
    entries = [
        {"end": "2024-12-31", "start": "2024-01-01", "val": 1000.0, "form": "10-K",
         "filed": "2025-02-20", "accn": "0000000000-25-000001", "fp": "FY"},
        {"end": "2024-12-31", "start": "2024-01-01", "val": 1100.0, "form": "10-K/A",
         "filed": "2025-06-01", "accn": "0000000000-25-000002", "fp": "FY"},
    ]
    facts, conflicts = normalize_entries("revenue", entries, provider="t", locator="l")
    assert len(facts) == 1
    assert facts[0].value == 1100.0           # amended value wins
    assert facts[0].accession == "0000000000-25-000002"
    assert conflicts and "restated" in conflicts[0]


def test_quarterly_and_stub_periods_rejected_for_flows():
    from fairvalue.data.normalize import normalize_entries
    entries = [
        {"end": "2025-03-31", "start": "2025-01-01", "val": 250.0, "form": "10-K",
         "filed": "2025-02-20", "accn": "a", "fp": "FY"},                       # quarterly
        {"end": "2025-08-01", "start": "2025-01-01", "val": 500.0, "form": "10-K",
         "filed": "2025-02-20", "accn": "a", "fp": "FY"},                       # stub
        {"end": "2025-12-31", "start": "2025-01-01", "val": 1000.0, "form": "10-K",
         "filed": "2025-02-20", "accn": "a", "fp": "FY"},                       # full year
    ]
    facts, _ = normalize_entries("revenue", entries, provider="t", locator="l")
    assert [f.period_end for f in facts] == [date(2025, 12, 31)]
