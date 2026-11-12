"""Orchestration: providers → ValuationInputs → models → reconciliation →
analysis → scenarios → explanation → ValuationReport.

The service is the only place that knows how to assemble inputs and default
assumptions; API/MCP/SDK/CLI all call it, keeping behavior identical everywhere.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from fairvalue.analysis import (
    compute_growth,
    compute_health,
    compute_multiples,
    compute_risks,
    run_scenarios,
)
from fairvalue.analysis.industry import apply_industry_rules
from fairvalue.core.schemas import (
    ComparablesAssumptions,
    CompanyProfile,
    DataQuality,
    DcfAssumptions,
    DdmAssumptions,
    EpvAssumptions,
    GrahamAssumptions,
    MarketData,
    ModelResult,
    PrecedentAssumptions,
    ResidualIncomeAssumptions,
    SourceRef,
    SotpAssumptions,
    ValuationExplanation,
    ValuationInputs,
    ValuationReport,
)
from fairvalue.data import ProviderError, get_provider
from fairvalue.explain import build_explanation
from fairvalue.valuation import MODEL_NAMES, reconcile, run_models
from fairvalue.valuation.base import not_applicable

DEFAULT_ERP = 0.05  # documented equity risk premium assumption (configurable per request)


class ValuationOptions(BaseModel):
    """Caller-tunable request options (API/SDK/CLI surface)."""

    demo: bool = False  # explicit only: never a silent fallback from live data
    price: float | None = Field(None, gt=0, description="override market price (must be provided by caller)")
    peer_tickers: list[str] = Field(default_factory=list, description="peer tickers to fetch for comparables")
    models: list[str] | None = Field(None, description="subset of model names to run; None = all")
    wacc: float | None = Field(None, gt=0, lt=1, description="explicit discount rate (else CAPM-derived)")
    erp: float | None = Field(None, gt=0, lt=1, description="equity risk premium used in CAPM")
    beta: float | None = Field(None, gt=0, description="beta override (else 1.0 with a note)")
    run_scenarios: bool = True


class LoadedInputs(BaseModel):
    inputs: ValuationInputs
    data_quality: DataQuality
    rates: dict[str, float | None] = Field(default_factory=dict)
    rate_notes: list[str] = Field(default_factory=list)


def _provider(opts: ValuationOptions):
    return get_provider(demo=opts.demo)


def load_inputs(
    provider,
    ticker: str,
    opts: ValuationOptions,
) -> LoadedInputs:
    """Assemble ValuationInputs + DataQuality from a provider. Missing data stays
    ``None`` and is listed in DataQuality — never substituted."""
    fundamentals = provider.get_fundamentals(ticker)
    latest = fundamentals.latest()
    facts = dict(latest.facts) if latest else {}

    def val(concept: str) -> float | None:
        f = facts.get(concept)
        return f.value if f else None

    history = fundamentals.periods
    warnings: list[str] = []
    sources: dict[str, SourceRef] = {}
    for p in history:
        for f in p.facts.values():
            key = f"{f.source.provider}:{f.source.locator}"
            sources.setdefault(key, f.source)

    # EBITDA: never a reported tag — derived as EBIT + D&A, disclosed as such.
    ebit, dep = val("ebit"), val("depreciation_amortization")
    ebitda = ebit + dep if ebit is not None and dep is not None else None
    if ebitda is not None:
        warnings.append("EBITDA derived as EBIT + D&A (both reported values); it is not a reported figure")
    ocf, capex = val("operating_cash_flow"), val("capex")
    fcf = ocf - capex if ocf is not None and capex is not None else None

    market = provider.get_market_data(ticker)
    if market is None and opts.price is None:
        market = MarketData(ticker=ticker.upper(), price=None, warnings=["no market data source returned data"])
    if market is not None:
        if market.source:
            sources[f"{market.source.provider}:{market.source.locator}"] = market.source
        if opts.price is not None:
            if market.price is not None and abs(market.price - opts.price) > 1e-9:
                warnings.append(
                    f"market price overridden by caller: feed said {market.price:g}, caller provided {opts.price:g}"
                )
            market = market.model_copy(update={"price": opts.price})
        elif market.price is None:
            warnings.append("market price unavailable — price-based comparisons omitted from the report")

    shares = val("shares_outstanding") or (market.shares_outstanding if market else None)
    if shares is None:
        warnings.append("shares outstanding missing — per-share values cannot be produced")

    peers = []
    if opts.peer_tickers:
        for pt in opts.peer_tickers:
            try:
                pf = provider.get_fundamentals(pt)
                pl = pf.latest()
                pm = provider.get_market_data(pt)
                if not pl or not pm or pm.price is None:
                    warnings.append(f"peer {pt.upper()}: fundamentals or price unavailable — skipped")
                    continue
                pval = lambda c: (pl.facts[c].value if c in pl.facts else None)  # noqa: E731
                p_ebit, p_dep = pval("ebit"), pval("depreciation_amortization")
                peers.append(
                    _peer_from(
                        pt.upper(), pm,
                        ebitda=(p_ebit + p_dep) if p_ebit is not None and p_dep is not None else None,
                        net_income=pval("net_income"), equity=pval("equity"), revenue=pval("revenue"),
                    )
                )
            except ProviderError as exc:
                warnings.append(f"peer {pt.upper()} failed: {exc.message}")
    else:
        peers = list(provider.get_peers(ticker))

    # macro rates
    erp = opts.erp if opts.erp is not None else DEFAULT_ERP
    beta = opts.beta
    if beta is None:
        beta = market.beta if market and market.beta else None
    rate_notes: list[str] = []
    if beta is None:
        beta = 1.0
        rate_notes.append("beta unavailable — CAPM uses beta = 1.0 (assumption, configurable via request)")
    rf = provider.get_rate("risk_free_10y")
    if rf is None:
        rate_notes.append("risk-free rate unavailable (FRED unreachable or blocked)")
    wacc = opts.wacc
    if wacc is None and rf is not None:
        wacc = rf + beta * erp
        rate_notes.append(
            f"WACC = risk-free {rf:.2%} + beta {beta:g} × ERP {erp:.2%} = {wacc:.2%} "
            "(debt cost ignored: no pre-tax borrowing-rate input — a simplification, stated as such)"
        )
    elif wacc is not None:
        rate_notes.append(f"caller supplied explicit WACC {wacc:.2%}")

    net_debt = (val("total_debt") or 0.0) - (val("cash") or 0.0) if (val("total_debt") is not None or val("cash") is not None) else None
    if val("total_debt") is None:
        warnings.append("total debt missing — net debt computed from cash only")
    if val("cash") is None:
        warnings.append("cash missing — net debt computed from debt only")

    inputs = ValuationInputs(
        company=fundamentals.company,
        market=market,
        history=history,
        shares_outstanding=shares,
        cash=val("cash"),
        total_debt=val("total_debt"),
        net_debt=net_debt,
        total_assets=val("total_assets"),
        total_liabilities=val("total_liabilities"),
        book_equity=val("equity"),
        revenue=val("revenue"),
        gross_profit=val("gross_profit"),
        ebit=ebit,
        ebitda=ebitda,
        net_income=val("net_income"),
        operating_cash_flow=ocf,
        capex=capex,
        depreciation_amortization=dep,
        fcf=fcf,
        eps=val("eps_diluted"),
        dps=val("dps"),
        risk_free_rate=rf,
        equity_risk_premium=erp,
        peers=peers,
        transactions=list(provider.get_transactions(ticker)),
        segments=list(provider.get_segments(ticker)),
    )

    missing = list(fundamentals.missing_concepts)
    if shares is None:
        missing.append("shares_outstanding")
    if market is None or market.price is None:
        missing.append("market_price")

    dq = DataQuality(
        missing=sorted(set(missing)),
        conflicts=list(fundamentals.conflicts),
        warnings=warnings + [f"statement validation: {e}" for e in fundamentals.validation_errors],
        sources=sorted(sources.values(), key=lambda s: s.provider),
    )
    rates = {"risk_free_rate": rf, "equity_risk_premium": erp, "beta": beta, "wacc": wacc}
    return LoadedInputs(inputs=inputs, data_quality=dq, rates=rates, rate_notes=rate_notes)


def _peer_from(ticker: str, market: MarketData, **kw):
    from fairvalue.core.schemas import ComparableCompany

    shares = market.shares_outstanding
    mcap = (market.price * shares) if market.price is not None and shares else None
    return ComparableCompany(
        ticker=ticker,
        price=market.price,
        shares_outstanding=shares,
        enterprise_value=(mcap + kw.pop("net_debt", 0.0)) if mcap is not None else None,
        **kw,
    )


def build_assumptions(
    inputs: ValuationInputs, rates: dict[str, float | None], opts: ValuationOptions
) -> tuple[dict[str, object], list[ModelResult]]:
    """Build each model's assumptions; models whose *parameters* cannot be
    derived get an explicit exclusion result (recorded, never silently dropped)."""
    assumptions: dict[str, object] = {}
    exclusions: list[ModelResult] = []

    wacc = rates.get("wacc")
    coe = None
    rf, beta, erp = rates.get("risk_free_rate"), rates.get("beta"), rates.get("equity_risk_premium")
    if rf is not None and beta is not None and erp is not None:
        coe = rf + beta * erp

    if opts.wacc is not None:
        wacc = opts.wacc  # explicit caller value always wins
    if wacc is not None:
        assumptions["dcf"] = DcfAssumptions(wacc=wacc)
        assumptions["epv"] = EpvAssumptions(wacc=wacc)
    else:
        reason = "discount rate unavailable: risk-free rate fetch failed and no wacc supplied"
        exclusions.append(not_applicable("dcf", reason))
        exclusions.append(not_applicable("epv", reason))
    if coe is not None:
        assumptions["ddm"] = DdmAssumptions(required_return=coe)
        assumptions["residual_income"] = ResidualIncomeAssumptions(cost_of_equity=coe)
    else:
        reason = "required return unavailable: CAPM inputs (risk-free rate) missing and not supplied"
        exclusions.append(not_applicable("ddm", reason))
        exclusions.append(not_applicable("residual_income", reason))

    assumptions["comparables"] = ComparablesAssumptions()
    assumptions["precedents"] = PrecedentAssumptions()
    assumptions["graham"] = GrahamAssumptions()
    assumptions["asset_based"] = AssetAssumptions()
    assumptions["sotp"] = _sotp_assumptions(inputs)

    if opts.models:
        allowed = set(opts.models)
        assumptions = {k: v for k, v in assumptions.items() if k in allowed}
        exclusions = [e for e in exclusions if e.model in allowed]
    return assumptions, exclusions


def AssetAssumptions():
    from fairvalue.core.schemas import AssetBasedAssumptions

    return AssetBasedAssumptions()


def _sotp_assumptions(inputs: ValuationInputs) -> SotpAssumptions:
    metrics = {s.metric for s in inputs.segments}
    metric = "ev_sales" if metrics and metrics == {"revenue"} else "ev_ebitda"
    return SotpAssumptions(multiple_metric=metric)


def run_valuation(provider, ticker: str, opts: ValuationOptions | None = None) -> ValuationReport:
    opts = opts or ValuationOptions()
    loaded = load_inputs(provider, ticker, opts)
    iv, dq = loaded.inputs, loaded.data_quality

    assumptions, param_exclusions = build_assumptions(iv, loaded.rates, opts)
    results = run_models(iv, assumptions)  # type: ignore[arg-type]
    by_name = {r.model: r for r in param_exclusions}
    by_name.update({r.model: r for r in results})
    ordered = [by_name[n] for n in MODEL_NAMES if n in by_name]

    reconciliation = reconcile(ordered)
    health = compute_health(iv)
    multiples = compute_multiples(iv)
    growth = compute_growth(iv)
    risks = compute_risks(iv)
    health, multiples, risks = apply_industry_rules(iv.company, health, multiples, risks)

    scenarios = None
    dcf_result = by_name.get("dcf")
    # Scenarios are DCF-based: skip them whenever the DCF itself is excluded
    # (financial firm, missing data) — bear/bull numbers for a rejected model
    # would contradict the reconciliation.
    if (
        opts.run_scenarios
        and isinstance(assumptions.get("dcf"), DcfAssumptions)
        and dcf_result is not None
        and dcf_result.applicable
    ):
        scenarios = run_scenarios(iv, assumptions["dcf"])  # type: ignore[arg-type]

    missing = list(dq.missing)
    if loaded.rate_notes:
        dq.warnings.extend(loaded.rate_notes)

    explanation = build_explanation(
        company_name=iv.company.name,
        ticker=iv.company.ticker,
        results=ordered,
        reconciliation=reconciliation,
        price=iv.price,
        health=health,
        risks=risks,
        missing_data=missing,
        conflicts=dq.conflicts,
        is_illustrative=iv.company.is_illustrative or bool(iv.market and iv.market.is_illustrative),
    )

    return ValuationReport(
        generated_at=datetime.now(timezone.utc),
        company=iv.company,
        market=iv.market,
        inputs=iv,
        models=ordered,
        reconciliation=reconciliation,
        scenarios=scenarios,
        health=health,
        multiples=multiples,
        growth=growth,
        risks=risks,
        explanation=explanation,
        data_quality=dq,
        is_illustrative=iv.company.is_illustrative or bool(iv.market and iv.market.is_illustrative),
    )


def search_companies(query: str, *, demo: bool = False) -> list[CompanyProfile]:
    if not query.strip():
        return []
    return get_provider(demo=demo).search_company(query)


def run_valuation_from_data(
    data, opts: ValuationOptions | None = None
) -> ValuationReport:
    """Valuation from agent-supplied data — the agent retrieves, we validate
    and calculate. No external provider is touched (SEC/FRED/Stooq-independent);
    the model pipeline below is the exact same one provider data flows through.

    Caller/submission assumptions win over defaults: explicit ``opts.erp``
    overrides the submission's ``erp``; ``opts.wacc`` overrides CAPM.
    """
    from fairvalue.data.static import StaticProvider

    opts = opts or ValuationOptions()
    if opts.erp is None and data.erp is not None:
        opts = opts.model_copy(update={"erp": data.erp})
    return run_valuation(StaticProvider(data), data.ticker, opts)
