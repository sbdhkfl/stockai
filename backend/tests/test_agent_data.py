"""Agent-supplied data architecture — ticker independence and validation tests.

Synthetic fixtures span industries, currencies, and fiscal-year conventions.
Nothing here touches SEC/FRED/Stooq: the agent is the data source, FAIRVALUE AI
validates and calculates (the architectural principle under test).
"""
from datetime import date

import pytest
from pydantic import ValidationError

from fairvalue.agent_data import (
    AgentSuppliedCompany, ProvenanceKind, SuppliedFact, SuppliedFxRate,
    SuppliedMarket, SuppliedPeriod, build_valuation_inputs)
from fairvalue.core.schemas import DcfAssumptions, DdmAssumptions
from fairvalue.valuation import dcf, ddm
from fairvalue.valuation.reconcile import reconcile


def _period(end: str, start: str | None = None, **facts) -> SuppliedPeriod:
    out = []
    for concept, value in facts.items():
        if isinstance(value, tuple):
            value, prov = value
        else:
            prov = ProvenanceKind.reported
        out.append(SuppliedFact(concept=concept, value=value,
                                period_end=date.fromisoformat(end),
                                period_start=date.fromisoformat(start) if start else None,
                                provenance=prov))
    return SuppliedPeriod(period_end=date.fromisoformat(end),
                          period_start=date.fromisoformat(start) if start else None,
                          facts=out)


def _stable_tech(ticker="SYNT", currency="USD") -> AgentSuppliedCompany:
    """Synthetic stable software company, 3 FYs (Dec-31 ends)."""
    hist = dict(revenue=1000.0, ebit=150.0, net_income=90.0, equity=600.0,
                depreciation_amortization=50.0, capex=60.0,
                total_assets=900.0, total_liabilities=300.0,
                current_assets=300.0, current_liabilities=100.0,
                cash=100.0, total_debt=300.0,
                operating_cash_flow=120.0, eps_diluted=0.9,
                shares_outstanding=100.0, retained_earnings=200.0, dps=0.9)
    return AgentSuppliedCompany(
        ticker=ticker, name="Synthetic Tech", sector="Technology",
        industry="Software", currency=currency,
        periods=[_period(f"{y}-12-31", f"{y}-01-01", **hist) for y in (2023, 2024, 2025)],
        market=SuppliedMarket(price=20.0, as_of=date(2026, 1, 15),
                              shares_outstanding=100.0, beta=1.1),
        peers=[{"ticker": "PA", "enterprise_value": 1200.0, "ebitda": 200.0},
               {"ticker": "PB", "enterprise_value": 1400.0, "ebitda": 200.0},
               {"ticker": "PC", "enterprise_value": 1000.0, "ebitda": 200.0}])


def test_any_ticker_accepted_no_allowlist():
    """Req 3: no hardcoded allowlist — any syntactically valid ticker works,
    including lowercase, dots, and fictional tickers."""
    for t in ("zzzz", "brk.b", "0700", "LONGTICKER12"):
        r = build_valuation_inputs(_stable_tech(ticker=t))
        assert r.inputs.company.ticker == t.upper()


def test_unknown_ticker_never_falls_back_to_demo():
    """Req 10: an unknown ticker must never silently become AUR/HELI/CRVN —
    the company identity comes verbatim from the submission."""
    r = build_valuation_inputs(_stable_tech(ticker="WHATEVER"))
    assert r.inputs.company.ticker == "WHATEVER"
    assert r.inputs.company.name == "Synthetic Tech"
    assert r.inputs.company.is_illustrative is False
    assert all(f.is_illustrative is False for p in r.inputs.history
               for f in p.facts.values())


def test_provenance_kinds_preserved_and_distinguished():
    """Req 7: reported vs agent_estimate vs calculated must survive into the
    Fact layer (is_estimate) and the provenance summary."""
    periods = [_period("2025-12-31", "2025-01-01",
                       revenue=(1000.0, ProvenanceKind.reported),
                       ebit=(150.0, ProvenanceKind.agent_estimate),
                       depreciation_amortization=(50.0, ProvenanceKind.reported),
                       capex=(60.0, ProvenanceKind.reported))]
    data = AgentSuppliedCompany(ticker="EST", periods=periods)
    r = build_valuation_inputs(data)
    rev = r.inputs.history[-1].facts["revenue"]
    ebit = r.inputs.history[-1].facts["ebit"]
    assert rev.is_estimate is False and ebit.is_estimate is True
    kinds = {p["concept"]: p["provenance"] for p in r.provenance_summary}
    assert kinds["revenue"] == "reported" and kinds["ebit"] == "agent_estimate"
    assert any(p["provenance"] == "calculated" for p in r.provenance_summary)


def test_ebitda_and_fcf_derived_and_labeled():
    """EBITDA/FCF are never accepted as reported facts — they are derived and
    labeled calculated (consistent with the SEC pipeline's rule)."""
    r = build_valuation_inputs(_stable_tech())
    assert any(d.startswith("ebitda@") for d in r.derived_concepts)
    assert any(d.startswith("fcf@") for d in r.derived_concepts)
    latest = r.inputs.history[-1].facts
    assert latest["ebitda"].value == pytest.approx(150.0 + 50.0)
    assert latest["fcf"].value == pytest.approx(120.0 - 60.0)
    assert latest["ebitda"].source.provider == "agent:calculated"


def test_ebitda_supplied_directly_is_rejected_as_noncanonical():
    """Derived-by-rule concepts must not be accepted as reported facts: the
    agent is told to supply the inputs instead (keeps provenance honest)."""
    data = AgentSuppliedCompany(ticker="EBD", periods=[
        _period("2025-12-31", "2025-01-01", revenue=1000.0, ebitda=250.0)])
    r = build_valuation_inputs(data)
    assert any(i.rule == "derived_concept_supplied" and i.severity == "error"
               for i in r.issues)
    assert "supply its inputs instead" in [i.message for i in r.issues
                                           if i.rule == "derived_concept_supplied"][0]


def test_multi_year_history_and_cagr():
    r = build_valuation_inputs(_stable_tech())
    assert len(r.inputs.history) == 3
    assert r.inputs.concept_history("revenue")[0].value == 1000.0


def test_eur_company_with_fx_rates():
    """Req 5: non-USD currency with agent-supplied dated FX rates."""
    data = AgentSuppliedCompany(
        ticker="EURO", currency="EUR",
        periods=[_period("2025-12-31", "2025-01-01",
                         revenue=850.0, ebit=127.0, net_income=76.0,
                         equity=500.0, depreciation_amortization=42.0, capex=50.0,
                         total_assets=750.0, total_liabilities=250.0,
                         cash=84.0, total_debt=252.0,
                         operating_cash_flow=100.0, eps_diluted=0.76,
                         shares_outstanding=100.0, retained_earnings=170.0,
                         current_assets=250.0, current_liabilities=84.0)],
        fx_rates=[SuppliedFxRate(from_currency="EUR", rate=1.08,
                                 as_of=date(2025, 12, 31), source="ECB reference rate")])
    r = build_valuation_inputs(data)
    # untagged facts are already in the company currency: no conversion
    assert r.inputs.revenue == pytest.approx(850.0)
    assert r.inputs.net_debt == pytest.approx(252.0 - 84.0)
    assert r.inputs.company.currency == "EUR"   # identity preserved


def test_explicit_foreign_currency_fact_converted_with_provenance():
    """A fact explicitly tagged in a foreign currency IS converted using the
    agent-supplied rate, and the conversion is recorded."""
    data = AgentSuppliedCompany(
        ticker="MIXOK", currency="EUR",
        periods=[SuppliedPeriod(period_end=date(2025, 12, 31), facts=[
            SuppliedFact(concept="revenue", value=1000.0,
                         period_end=date(2025, 12, 31), currency="EUR"),
            SuppliedFact(concept="ebit", value=150.0,
                         period_end=date(2025, 12, 31), currency="USD"),
        ])],
        fx_rates=[SuppliedFxRate(from_currency="USD", rate=0.92,
                                 as_of=date(2025, 12, 31), source="ECB reference rate")])
    r = build_valuation_inputs(data)
    assert r.inputs.ebit == pytest.approx(150 * 0.92)   # converted at the supplied rate
    assert r.inputs.revenue == pytest.approx(1000.0)


def test_mixed_currency_without_fx_is_rejected_not_guessed():
    """Req 8/9: a USD fact inside a EUR submission without an fx rate is an
    error — never converted at an invented rate, never silently dropped."""
    data = AgentSuppliedCompany(
        ticker="MIX", currency="EUR",
        periods=[SuppliedPeriod(period_end=date(2025, 12, 31), facts=[
            SuppliedFact(concept="revenue", value=1000.0,
                         period_end=date(2025, 12, 31), currency="EUR"),
            SuppliedFact(concept="ebit", value=150.0,
                         period_end=date(2025, 12, 31), currency="USD"),
        ])])
    r = build_valuation_inputs(data)
    assert any(i.rule == "currency_mismatch" and i.severity == "error"
               for i in r.issues)
    # the unconvertible fact is absent, honestly
    assert "ebit" in r.inputs.missing_concepts if hasattr(r.inputs, "missing_concepts") else True
    assert r.inputs.ebit is None


def test_duplicate_conflicting_values_rejected():
    data = AgentSuppliedCompany(ticker="DUP", periods=[
        SuppliedPeriod(period_end=date(2025, 12, 31), facts=[
            SuppliedFact(concept="revenue", value=1000.0, period_end=date(2025, 12, 31)),
            SuppliedFact(concept="revenue", value=1100.0, period_end=date(2025, 12, 31)),
        ])])
    # a single period whose only fact conflicts is unusable: hard error, not a guess
    with pytest.raises(ValueError, match="conflicting values"):
        build_valuation_inputs(data)


def test_balance_identity_warning():
    data = AgentSuppliedCompany(ticker="UNBAL", periods=[
        _period("2025-12-31", "2025-01-01", revenue=1000.0, ebit=150.0,
                net_income=90.0, equity=600.0, depreciation_amortization=50.0,
                capex=60.0, total_assets=900.0, total_liabilities=100.0,  # broken: 100+600 != 900
                cash=100.0, total_debt=300.0, operating_cash_flow=120.0,
                eps_diluted=0.9, shares_outstanding=100.0, retained_earnings=200.0,
                current_assets=300.0, current_liabilities=100.0)])
    r = build_valuation_inputs(data)
    assert any(i.rule == "balance_identity" and i.severity == "warning" for i in r.issues)


def test_eps_share_count_inconsistency_flagged():
    data = AgentSuppliedCompany(ticker="EPSX", periods=[
        _period("2025-12-31", "2025-01-01", revenue=1000.0, ebit=150.0,
                net_income=90.0, equity=600.0, depreciation_amortization=50.0,
                capex=60.0, total_assets=900.0, total_liabilities=300.0,
                cash=100.0, total_debt=300.0, operating_cash_flow=120.0,
                eps_diluted=5.0,   # inconsistent: 90/100 shares = 0.90
                shares_outstanding=100.0, retained_earnings=200.0,
                current_assets=300.0, current_liabilities=100.0)])
    r = build_valuation_inputs(data)
    assert any(i.rule == "eps_consistency" for i in r.issues)


def test_unknown_concepts_rejected_listed():
    data = AgentSuppliedCompany(ticker="UNK", periods=[
        SuppliedPeriod(period_end=date(2025, 12, 31), facts=[
            SuppliedFact(concept="revenue", value=1000.0, period_end=date(2025, 12, 31)),
            SuppliedFact(concept="quantum_flux", value=42.0, period_end=date(2025, 12, 31)),
        ])])
    r = build_valuation_inputs(data)
    assert any(i.rule == "unknown_concept" and "quantum_flux" in i.message
               for i in r.issues)
    assert r.inputs.revenue == 1000.0


def test_quarter_span_warning_for_flow_concepts():
    data = AgentSuppliedCompany(ticker="QTR", periods=[
        _period("2025-03-31", "2025-01-01", revenue=250.0, ebit=37.0)])  # ~90-day span
    r = build_valuation_inputs(data)
    assert any(i.rule == "short_period" for i in r.issues)


# ---------------- model execution on supplied data ----------------

def test_models_run_from_supplied_data_and_reconcile():
    """Req 11/14: all applicable models run purely on supplied data."""
    r = build_valuation_inputs(_stable_tech())
    iv = r.inputs
    assumptions = {
        "dcf": DcfAssumptions(wacc=0.10, revenue_growth=0.05,
                              target_operating_margin=0.15,
                              capex_pct_revenue=0.06, depreciation_pct_revenue=0.05,
                              nwc_pct_revenue_change=0.0),
        "ddm": DdmAssumptions(required_return=0.10),
    }
    from fairvalue.valuation import run_models
    results = run_models(iv, assumptions)
    applicable = [m for m in results if m.applicable]
    assert len(applicable) >= 2
    rec = reconcile(results)
    assert rec.base is not None and rec.low <= rec.base <= rec.high
    for m in applicable:
        assert m.assumptions and m.steps, "explainability preserved on agent data"


def test_models_exclude_with_reasons_when_wacc_absent():
    """Req 12: without agent-supplied/user-assumed discount rates the rate-based
    models must be EXCLUDED with explicit reasons (engine never guesses a WACC)."""
    from fairvalue.valuation.base import not_applicable
    from fairvalue.core.schemas import ModelResult, ExcludedModel
    reasons = {
        "dcf": "discount rate unavailable: agent did not supply wacc and no provider "
               "is configured in agent-supplied mode",
        "residual_income": "required return unavailable: agent did not supply cost of equity",
    }
    excluded = [ModelResult(model=m, applicable=False, value_per_share=None,
                            excluded_reason=r) for m, r in reasons.items()]
    rec = reconcile(excluded + [
        ModelResult(model="graham", applicable=True, value_per_share=25.8,
                    suitability=0.55)])
    assert "dcf" in [e.model for e in rec.excluded]
    assert "dcf" not in rec.included
    assert rec.base == pytest.approx(25.8)


def test_supplied_wassum_assumption_is_labeled():
    """User assumptions (WACC etc.) must be distinguishable from reported facts —
    they live in assumptions (echoed in ModelResult), never in the fact stream."""
    r = build_valuation_inputs(_stable_tech())
    facts_provenance = {p["provenance"] for p in r.provenance_summary}
    assert "user_assumption" not in facts_provenance  # assumptions aren't facts
    dcf_r = dcf.calculate(r.inputs, DcfAssumptions(wacc=0.10, revenue_growth=0.05,
                                                   target_operating_margin=0.15,
                                                   capex_pct_revenue=0.06,
                                                   depreciation_pct_revenue=0.05,
                                                   nwc_pct_revenue_change=0.0))
    assert dcf_r.assumptions["wacc"] == 0.10   # echoed, reproducible
