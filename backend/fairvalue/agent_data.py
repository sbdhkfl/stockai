"""Agent-supplied financial data — universal structured input interface.

Design principle (docs/AGENT_TASKS.md, agent-data round):
    AI agent = data retrieval and research.
    FAIRVALUE AI = validation and calculation.

Any MCP-compatible agent can submit structured financials for ANY ticker
(no allowlist); this module validates the submission and assembles a
``ValuationInputs`` for the existing engine. Nothing here fetches data, and
nothing is fabricated: absent concepts become ``missing``, not defaults.

Provenance taxonomy (req 7):
    reported          — the agent sourced it from a filing/official statement
    agent_estimate    — the agent's own estimate (e.g. consensus figure)
    user_assumption   — the end user's stated assumption (e.g. WACC)
    calculated        — derived by FAIRVALUE AI from supplied facts (labeled)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from fairvalue.core.schemas import (
    CANONICAL_CONCEPTS, ComparableCompany, CompanyProfile, Fact, MarketData,
    PeriodFinancials, PrecedentTransaction, Segment, SourceRef, ValuationInputs)


class ProvenanceKind(str, Enum):
    reported = "reported"
    agent_estimate = "agent_estimate"
    user_assumption = "user_assumption"
    calculated = "calculated"


#: concepts the engine derives itself; agent-supplied values are refused
DERIVED_CONCEPTS = {"ebitda", "fcf"}
DERIVED_RULES = {"ebitda": "ebit + depreciation_amortization",
                 "fcf": "operating_cash_flow - capex"}

SUPPLIED_UNIT_OVERRIDES = {"shares_outstanding": "shares",
                           "eps_diluted": "USD/shares", "dps": "USD/shares"}


class SuppliedFact(BaseModel):
    concept: str
    value: float
    period_end: date
    period_start: date | None = None
    fiscal_year: int | None = None   # derived from period_end when absent
    currency: str | None = None      # None -> company currency
    unit: str | None = None          # None -> canonical default for the concept
    provenance: ProvenanceKind = ProvenanceKind.reported
    source: str | None = None        # free-text locator, e.g. "10-K p.42, filed 2026-11-03"

    @field_validator("value")
    @classmethod
    def _finite(cls, v):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("value must be finite")
        return v


class SuppliedPeriod(BaseModel):
    period_end: date
    period_start: date | None = None
    fiscal_period: Literal["FY", "Q1", "Q2", "Q3", "Q4", "TTM"] = "FY"
    facts: list[SuppliedFact]

    @field_validator("facts")
    @classmethod
    def _nonempty(cls, v):
        if not v:
            raise ValueError("period has no facts")
        return v


class SuppliedMarket(BaseModel):
    price: float | None = None
    as_of: date | None = None
    shares_outstanding: float | None = None
    beta: float | None = None
    provenance: ProvenanceKind = ProvenanceKind.reported
    source: str | None = None


class SuppliedFxRate(BaseModel):
    """Conversion rate INTO the company currency, with its own provenance."""
    from_currency: str
    rate: float                      # 1 unit of from_currency = rate × company currency
    as_of: date | None = None
    provenance: ProvenanceKind = ProvenanceKind.reported
    source: str | None = None


class AgentSuppliedCompany(BaseModel):
    """Universal submission envelope. Any valid ticker symbol is accepted —
    there is deliberately NO ticker allowlist (req 3)."""
    ticker: str = Field(min_length=1, max_length=16)
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str = "USD"
    accounting_standard: str | None = None   # e.g. "US-GAAP", "IFRS" (echoed, req 5)
    is_illustrative: bool = False    # must be explicit; never a silent demo (req 10)
    periods: list[SuppliedPeriod] = Field(min_length=1)
    market: SuppliedMarket | None = None
    # macro inputs the agent retrieved (agent = data retrieval); rates are
    # assumptions-adjacent market data, never invented here
    risk_free_rate: float | None = Field(None, gt=0.0, lt=1.0)
    erp: float | None = Field(None, gt=0.0, lt=1.0)
    fx_rates: list[SuppliedFxRate] = Field(default_factory=list)
    peers: list[SuppliedPeer] = Field(default_factory=list)
    transactions: list[SuppliedTransaction] = Field(default_factory=list)
    segments: list[SuppliedSegment] = Field(default_factory=list)

    @field_validator("ticker")
    @classmethod
    def _ticker_shape(cls, v):
        t = v.strip().upper()
        if not t or any(ch in t for ch in " /\\"):
            raise ValueError("invalid ticker")
        return t


class SuppliedPeer(BaseModel):
    ticker: str
    name: str | None = None
    price: float | None = None
    shares_outstanding: float | None = None
    enterprise_value: float | None = None
    ebitda: float | None = None
    ebit: float | None = None
    net_income: float | None = None
    equity: float | None = None
    revenue: float | None = None


class SuppliedTransaction(BaseModel):
    target: str
    acquirer: str | None = None
    announced: date | None = None
    enterprise_value: float | None = None
    ebitda: float | None = None
    revenue: float | None = None


class SuppliedSegment(BaseModel):
    name: str
    metric: str = "ebitda"
    value: float
    multiple: float | None = None


class AgentDataIssue(BaseModel):
    rule: str
    field: str
    message: str
    severity: str  # error | warning


class AgentDataResult(BaseModel):
    inputs: ValuationInputs
    issues: list[AgentDataIssue] = Field(default_factory=list)
    provenance_summary: list[dict[str, str]] = Field(default_factory=list)
    derived_concepts: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------

def _convert(value: float, currency: str | None, company_currency: str,
             fx: dict[str, SuppliedFxRate], issues: list[AgentDataIssue],
             field: str) -> float:
    if not currency or currency == company_currency:
        return value
    rate = fx.get(currency)
    if rate is None:
        issues.append(AgentDataIssue(
            rule="currency_mismatch", field=field,
            message=f"value in {currency} without an fx_rate for {currency} -> "
                    f"{company_currency}: fact rejected, not converted at a guessed rate",
            severity="error"))
        raise ValueError(f"missing fx rate for {currency}")
    return value * rate.rate


def _check_relationships(periods: list[PeriodFinancials],
                         issues: list[AgentDataIssue]) -> None:
    for p in periods:
        f = p.facts
        a, l, e = f.get("total_assets"), f.get("total_liabilities"), f.get("equity")
        if a and l and e and a.value:
            diff = abs(a.value - (l.value + e.value)) / abs(a.value)
            if diff > 0.01:
                issues.append(AgentDataIssue(
                    rule="balance_identity", field=f"assets@{p.period_end}",
                    message=f"assets {a.value:,.0f} != liabilities+equity "
                            f"{l.value + e.value:,.0f} (diff {diff:.1%}) — "
                            "supplied as-is, flagged for the caller",
                    severity="warning"))
        ni, sh, eps = f.get("net_income"), f.get("shares_outstanding"), f.get("eps_diluted")
        if ni and sh and eps and sh.value > 0:
            implied = ni.value / sh.value
            if abs(implied - eps.value) > 0.25 * max(abs(eps.value), 1e-9):
                issues.append(AgentDataIssue(
                    rule="eps_consistency", field=f"eps_diluted@{p.period_end}",
                    message=f"net_income/shares implies EPS {implied:.4f} vs supplied "
                            f"{eps.value:.4f} (>25% apart) — check share units or per-share basis",
                    severity="warning"))
        for concept, fact in f.items():
            if concept in ("revenue", "shares_outstanding", "total_assets") and fact.value < 0:
                issues.append(AgentDataIssue(
                    rule="negative_value", field=f"{concept}@{p.period_end}",
                    message=f"{concept} is negative where the domain forbids it",
                    severity="error"))


def build_valuation_inputs(data: AgentSuppliedCompany) -> AgentDataResult:
    """Validate a submission and assemble engine inputs. Pure function — no
    providers, no fetching, no defaults invented. Raises ValueError on hard
    errors (nothing salvageable)."""
    issues: list[AgentDataIssue] = []
    fx = {r.from_currency: r for r in data.fx_rates}
    now = datetime.now(timezone.utc)
    source = SourceRef(provider="agent_supplied", locator=None, retrieved_at=now)
    periods: list[PeriodFinancials] = []
    provenance: list[dict[str, str]] = []
    derived: list[str] = []
    unknown: set[str] = set()

    for sp in sorted(data.periods, key=lambda p: p.period_end):
        facts: dict[str, Fact] = {}
        per_end: dict[str, list[SuppliedFact]] = {}
        for sf in sp.facts:
            if sf.concept in DERIVED_CONCEPTS:
                issues.append(AgentDataIssue(
                    rule="derived_concept_supplied", field=f"{sf.concept}@{sp.period_end}",
                    message=f"'{sf.concept}' is derived by rule ({DERIVED_RULES[sf.concept]}); "
                            "supply its inputs instead — a directly supplied value is "
                            "rejected to keep provenance honest",
                    severity="error"))
                continue
            if sf.concept not in CANONICAL_CONCEPTS:
                unknown.add(sf.concept)
                continue
            per_end.setdefault(sf.concept, []).append(sf)
        for concept, sfs in per_end.items():
            values = {f.value for f in sfs}
            if len(values) > 1:
                issues.append(AgentDataIssue(
                    rule="duplicate_conflict", field=f"{concept}@{sp.period_end}",
                    message=f"agent supplied conflicting values {sorted(values)} for the "
                            "same concept/period — fact rejected (provide one value or "
                            "separate periods)",
                    severity="error"))
                continue
            sf = sfs[0]
            try:
                value = _convert(sf.value, sf.currency, data.currency, fx, issues,
                                 f"{concept}@{sp.period_end}")
            except ValueError:
                continue
            if sf.period_start and 0 < (sf.period_end - sf.period_start).days < 300:
                issues.append(AgentDataIssue(
                    rule="short_period", field=f"{concept}@{sp.period_end}",
                    message=f"flow concept spans {(sf.period_end - sf.period_start).days} "
                            "days — not an annual period; check quarterly/stub data",
                    severity="warning"))
            facts[concept] = Fact(
                concept=concept, value=value,
                unit=sf.unit or SUPPLIED_UNIT_OVERRIDES.get(concept, "USD"),
                basis="duration" if (sf.period_start or sp.period_start) else "instant",
                period_start=sf.period_start or sp.period_start,
                period_end=sp.period_end,
                fiscal_year=sf.fiscal_year or sp.period_end.year,
                fiscal_period=sp.fiscal_period,
                is_estimate=sf.provenance == ProvenanceKind.agent_estimate,
                is_illustrative=data.is_illustrative,
                source=SourceRef(provider=f"agent:{sf.provenance.value}",
                                 locator=sf.source, retrieved_at=now))
            provenance.append({"concept": concept, "period_end": str(sp.period_end),
                               "provenance": sf.provenance.value,
                               "source": sf.source or "not provided"})
        # derived (labeled calculated, never silent)
        ebit, dep = facts.get("ebit"), facts.get("depreciation_amortization")
        if ebit and dep and "ebitda" not in facts:
            facts["ebitda"] = Fact(concept="ebitda", value=ebit.value + dep.value,
                                   period_end=sp.period_end, fiscal_year=sp.period_end.year,
                                   is_estimate=ebit.is_estimate or dep.is_estimate,
                                   is_illustrative=data.is_illustrative,
                                   source=SourceRef(provider="agent:calculated",
                                                    locator="derived: ebit + D&A",
                                                    retrieved_at=now))
            provenance.append({"concept": "ebitda", "period_end": str(sp.period_end),
                               "provenance": "calculated",
                               "source": "derived: ebit + D&A"})
            derived.append(f"ebitda@{sp.period_end}")
        ocf, capex = facts.get("operating_cash_flow"), facts.get("capex")
        if ocf and capex and "fcf" not in facts:
            facts["fcf"] = Fact(concept="fcf", value=ocf.value - abs(capex.value),
                                period_end=sp.period_end, fiscal_year=sp.period_end.year,
                                is_illustrative=data.is_illustrative,
                                source=SourceRef(provider="agent:calculated",
                                                 locator="derived: ocf - capex",
                                                 retrieved_at=now))
            provenance.append({"concept": "fcf", "period_end": str(sp.period_end),
                               "provenance": "calculated",
                               "source": "derived: ocf - capex"})
            derived.append(f"fcf@{sp.period_end}")
        if facts:
            periods.append(PeriodFinancials(fiscal_year=sp.period_end.year,
                                            period_end=sp.period_end, facts=facts))

    if unknown:
        issues.append(AgentDataIssue(
            rule="unknown_concept", field=", ".join(sorted(unknown)),
            message=f"concepts not in the canonical set were rejected, not stored: "
                    f"{sorted(unknown)} (extend CANONICAL_CONCEPTS upstream to accept them)",
            severity="warning"))
    _check_relationships(periods, issues)
    if not periods:
        raise ValueError("no usable periods after validation: "
                         + "; ".join(i.message for i in issues if i.severity == "error"))
    hard = [i for i in issues if i.severity == "error"]
    if hard and not periods:
        raise ValueError("; ".join(i.message for i in hard))

    latest = periods[-1]

    def val(c: str) -> float | None:
        f = latest.facts.get(c)
        return f.value if f else None

    ebit, dep = val("ebit"), val("depreciation_amortization")
    market = None
    if data.market:
        price = data.market.price
        if price is not None and price <= 0:
            issues.append(AgentDataIssue(rule="negative_value", field="market.price",
                                         message="price must be positive when supplied",
                                         severity="error"))
            price = None
        market = MarketData(
            ticker=data.ticker, price=price, as_of=data.market.as_of,
            currency=data.currency, shares_outstanding=data.market.shares_outstanding,
            beta=data.market.beta, is_illustrative=data.is_illustrative,
            source=SourceRef(provider=f"agent:{data.market.provenance.value}",
                             locator=data.market.source, retrieved_at=now))
        provenance.append({"concept": "market.price", "period_end": str(data.market.as_of or ""),
                           "provenance": data.market.provenance.value,
                           "source": data.market.source or "not provided"})

    net_debt = None
    if val("total_debt") is not None or val("cash") is not None:
        net_debt = (val("total_debt") or 0.0) - (val("cash") or 0.0)
    shares = val("shares_outstanding") or (data.market.shares_outstanding if data.market else None)
    if shares is not None and shares <= 0:
        issues.append(AgentDataIssue(rule="negative_value", field="shares_outstanding",
                                     message="shares outstanding must be positive",
                                     severity="error"))
        shares = None

    missing = [c for c in CANONICAL_CONCEPTS
               if c not in latest.facts and c not in ("ebitda",)]
    inputs = ValuationInputs(
        company=CompanyProfile(ticker=data.ticker, name=data.name or data.ticker,
                               sector=data.sector, industry=data.industry,
                               currency=data.currency, provider="agent_supplied",
                               accounting_standard=data.accounting_standard,
                               is_illustrative=data.is_illustrative),
        market=market, history=periods, shares_outstanding=shares,
        cash=val("cash"), total_debt=val("total_debt"), net_debt=net_debt,
        total_assets=val("total_assets"), total_liabilities=val("total_liabilities"),
        book_equity=val("equity"), revenue=val("revenue"),
        gross_profit=val("gross_profit"), ebit=ebit,
        ebitda=(ebit + dep) if ebit is not None and dep is not None else None,
        net_income=val("net_income"), operating_cash_flow=val("operating_cash_flow"),
        capex=val("capex"), depreciation_amortization=dep,
        fcf=val("fcf"), eps=val("eps_diluted"), dps=val("dps"),
        peers=[ComparableCompany(**p.model_dump()) for p in data.peers],
        transactions=[PrecedentTransaction(**t.model_dump()) for t in data.transactions],
        segments=[Segment(**seg.model_dump()) for seg in data.segments],
    )
    return AgentDataResult(inputs=inputs, issues=issues,
                           provenance_summary=provenance, derived_concepts=derived,
                           missing_concepts=sorted(missing))
