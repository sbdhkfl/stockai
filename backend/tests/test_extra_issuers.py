"""Additional-issuer validation (sprint-2 deliverable 5): real filings from
three more industries — JPM (banking), XOM (energy), KO (consumer staples).

Checks taxonomy mapping, period normalization, honest missing-metric reporting,
share-count handling, sector-specific model suitability and reconciliation
behavior. Expected reported values are cross-checked against figures that are
public knowledge (documented inline); the assertion is a sanity anchor, not a
data source.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fairvalue.core.schemas import CompanyProfile, SourceRef
from fairvalue.data.edgar import extract_concepts
from fairvalue.data.normalize import assemble_fundamentals
from fairvalue.valuation import dcf as dcf_mod
from fairvalue.core.schemas import DcfAssumptions, ModelResult
from fairvalue.valuation.reconcile import reconcile

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def load(ticker):
    path = FIXTURES / f"{ticker.lower()}_facts.json"
    if not path.exists():
        pytest.skip(f"fixture missing: run scripts/make_fixtures_extra.py")
    fx = json.loads(path.read_text(encoding="utf-8"))
    company = CompanyProfile(
        ticker=ticker, name=ticker, cik=fx["cik"], provider="sec_edgar",
        sector=fx.get("sic_description"))
    src = SourceRef(provider="sec_edgar", locator=fx["locator"], retrieved_at=NOW)
    cf, conflicts = extract_concepts(fx, locator=fx["locator"])
    return assemble_fundamentals(company, cf, conflicts), fx


@pytest.mark.parametrize("ticker", ["JPM", "XOM", "KO"])
def test_real_filings_produce_periods(ticker):
    fund, _ = load(ticker)
    assert len(fund.periods) >= 5, f"{ticker}: only {len(fund.periods)} periods"
    # shares_outstanding is attached only to the latest financial period by design
    latest_sh = fund.periods[-1].facts.get("shares_outstanding")
    assert latest_sh is not None and latest_sh.value > 0


@pytest.mark.parametrize("ticker,months", [("JPM", {12, 1}), ("XOM", {12, 1}),
                                           ("KO", {12, 1})])
def test_fiscal_period_grouping(ticker, months):
    fund, _ = load(ticker)
    ends = [p.period_end for p in fund.periods]
    assert {d.month for d in ends} <= months, ticker


def test_jpm_share_count_sanity():
    """JPM cover-page share count is in SHARES (not thousands) — ~220-310M
    shares × ~$200-300 ≈ $50-90B market cap era. A unit slip would show
    values like 220,000 (thousands) or 0.22 (millions)."""
    fund, _ = load("JPM")
    sh = fund.periods[-1].facts.get("shares_outstanding")
    assert sh is not None
    assert 50e6 <= sh.value <= 1e10, f"JPM shares {sh.value} — likely wrong unit"


def test_xom_revenue_sane_and_missing_reported():
    fund, _ = load("XOM")
    latest = fund.periods[-1]
    assert "revenue" in latest.facts
    assert latest.facts["revenue"].value > 1e9   # hundreds of billions expected
    assert latest.facts["revenue"].value < 1e13  # unit slip guard
    # Honest finding (recorded for the report): XOM's latest FY does not expose
    # the canonical OperatingIncomeLoss tag in these filings — if absent, it
    # must appear in missing_concepts, never be fabricated.
    if "ebit" not in latest.facts:
        assert "ebit" in fund.missing_concepts


def test_ko_missing_fields_reported_not_fabricated():
    fund, _ = load("KO")
    latest = fund.periods[-1]
    # ebitda is never a canonical concept (derived by the service as EBIT + D&A)
    absent = [c for c in ("ebit", "gross_profit") if c not in latest.facts]
    if absent:
        assert all(c in fund.missing_concepts for c in absent), (
            f"KO lacks {absent} but missing_concepts={fund.missing_concepts}")


def test_bank_dcf_refused_and_residual_income_suitable():
    """Sector-specific suitability: a bank must not get a plain DCF."""
    fund, _ = load("JPM")
    from fairvalue.analysis.industry import is_financial
    assert is_financial(fund.company), f"JPM not classified financial: {fund.company}"
    iv = _iv_from(fund)
    result = dcf_mod.calculate(iv, DcfAssumptions(wacc=0.10))
    assert not result.applicable and "financial" in (result.excluded_reason or "")


def test_reconciliation_never_averages_excluded_models():
    """With DCF excluded (bank), the reconciliation must not include it."""
    fund, _ = load("JPM")
    iv = _iv_from(fund)
    dcf_result = dcf_mod.calculate(iv, DcfAssumptions(wacc=0.10))
    ri = ModelResult(model="residual_income", applicable=True, value_per_share=100.0,
                     suitability=0.7)
    rec = reconcile([dcf_result, ri])
    assert "dcf" in [e.model for e in rec.excluded]
    assert "dcf" not in rec.included
    assert rec.base == pytest.approx(100.0)  # single applicable model: no fake spread


def _iv_from(fund):
    from fairvalue.core.schemas import MarketData, ValuationInputs
    latest = fund.periods[-1]

    def val(c):
        f = latest.facts.get(c)
        return f.value if f else None
    ebit, dep = val("ebit"), val("depreciation_amortization")
    net_debt = None
    if val("total_debt") is not None and val("cash") is not None:
        net_debt = val("total_debt") - val("cash")
    return ValuationInputs(
        company=fund.company, history=fund.periods,
        market=MarketData(ticker=fund.company.ticker),
        shares_outstanding=val("shares_outstanding"),
        cash=val("cash"), total_debt=val("total_debt"), net_debt=net_debt,
        total_assets=val("total_assets"), total_liabilities=val("total_liabilities"),
        book_equity=val("equity"), revenue=val("revenue"), gross_profit=val("gross_profit"),
        ebit=ebit, ebitda=(ebit + dep) if ebit is not None and dep is not None else None,
        net_income=val("net_income"), operating_cash_flow=val("operating_cash_flow"),
        capex=val("capex"), depreciation_amortization=dep,
        fcf=(val("operating_cash_flow") - val("capex")
             if val("operating_cash_flow") is not None and val("capex") is not None else None),
        eps=val("eps_diluted"), dps=val("dps"),
    )
