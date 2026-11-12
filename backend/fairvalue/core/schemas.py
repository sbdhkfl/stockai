"""Shared data contracts for FAIRVALUE AI.

This module is the binding interface between CORE, API, MCP, SDK, CLI and the
dashboard, and the agreed contract with Deep AI Code (ARCHITECTURE.md §3).
No valuation logic lives here.

Conventions:
- ``None`` means *missing data*. It is never replaced by 0 or an invented value.
- ``capex`` is a positive magnitude (spend).
- Every ``Fact`` carries provenance (``SourceRef``).
- ``is_illustrative=True`` marks synthetic demo data so it can never be
  mistaken for reported financials anywhere downstream.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "1.0"

FiscalPeriod = Literal["FY", "Q1", "Q2", "Q3", "Q4", "TTM"]
Confidence = Literal["low", "medium", "high"]

#: Canonical concepts every provider normalizes into.
CANONICAL_CONCEPTS: tuple[str, ...] = (
    "revenue",
    "gross_profit",
    "ebit",
    "ebitda",
    "net_income",
    "operating_cash_flow",
    "capex",
    "depreciation_amortization",
    "cash",
    "total_debt",
    "total_assets",
    "total_liabilities",
    "current_assets",
    "current_liabilities",
    "equity",
    "shares_outstanding",
    "eps_diluted",
    "dps",
)

FLOW_CONCEPTS = frozenset(
    {
        "revenue",
        "gross_profit",
        "ebit",
        "ebitda",
        "net_income",
        "operating_cash_flow",
        "capex",
        "depreciation_amortization",
        "eps_diluted",
        "dps",
    }
)

# ---------------------------------------------------------------------------
# Provenance & normalized facts
# ---------------------------------------------------------------------------


class SourceRef(BaseModel):
    """Where a number came from. Mandatory on every Fact."""

    provider: str
    locator: str | None = None
    retrieved_at: datetime
    license: str | None = None


class Fact(BaseModel):
    """One normalized financial number for one reporting period.

    ``basis`` distinguishes duration facts (flows: start+end, e.g. revenue for a
    fiscal year) from instant facts (balances at ``period_end`` alone, e.g. cash).
    ``accession``/``filed_at`` preserve the exact filing provenance for audit.
    """

    concept: str
    value: float
    unit: str = "USD"
    basis: Literal["duration", "instant"] = "instant"
    period_start: date | None = None
    period_end: date
    fiscal_year: int
    fiscal_period: FiscalPeriod = "FY"
    is_estimate: bool = False
    form: str | None = None
    accession: str | None = None
    filed_at: datetime | None = None
    is_illustrative: bool = False
    source: SourceRef


class CompanyProfile(BaseModel):
    ticker: str
    name: str
    cik: str | None = None
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    currency: str = "USD"
    accounting_standard: str | None = None  # e.g. "US-GAAP" / "IFRS" when known
    business_description: str | None = None
    provider: str = "unknown"
    is_illustrative: bool = False


class PeriodFinancials(BaseModel):
    fiscal_year: int
    period_end: date
    facts: dict[str, Fact]


class Fundamentals(BaseModel):
    company: CompanyProfile
    periods: list[PeriodFinancials]  # ascending by period_end
    missing_concepts: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)  # restatements / cross-source disagreements
    validation_errors: list[str] = Field(default_factory=list)  # structural statement checks

    def latest(self) -> PeriodFinancials | None:
        return self.periods[-1] if self.periods else None


# ---------------------------------------------------------------------------
# Market, comparables, transactions, segments
# ---------------------------------------------------------------------------


class PricePoint(BaseModel):
    day: date
    close: float


class MarketData(BaseModel):
    ticker: str
    price: float | None = None
    as_of: date | None = None
    currency: str = "USD"
    shares_outstanding: float | None = None
    market_cap: float | None = None
    beta: float | None = None
    price_history: list[PricePoint] = Field(default_factory=list)
    is_illustrative: bool = False
    source: SourceRef | None = None
    warnings: list[str] = Field(default_factory=list)


class ComparableCompany(BaseModel):
    """A peer with raw fundamentals; multiples are computed, not stored."""

    ticker: str
    name: str | None = None
    enterprise_value: float | None = None
    ebitda: float | None = None
    ebit: float | None = None
    net_income: float | None = None
    equity: float | None = None
    revenue: float | None = None
    price: float | None = None
    shares_outstanding: float | None = None
    is_illustrative: bool = False


class PrecedentTransaction(BaseModel):
    target: str
    acquirer: str | None = None
    announced: date | None = None
    enterprise_value: float | None = None
    ebitda: float | None = None
    revenue: float | None = None
    is_illustrative: bool = False


class Segment(BaseModel):
    """A business unit for sum-of-the-parts valuation."""

    name: str
    metric: Literal["revenue", "ebitda", "ebit", "net_income"]
    value: float
    multiple: float | None = None  # set via SotpAssumptions.segment_multiples
    is_illustrative: bool = False


# ---------------------------------------------------------------------------
# Valuation inputs (handed to every model)
# ---------------------------------------------------------------------------


class ValuationInputs(BaseModel):
    company: CompanyProfile
    market: MarketData | None = None
    history: list[PeriodFinancials] = Field(default_factory=list)  # ascending

    shares_outstanding: float | None = None
    cash: float | None = None
    total_debt: float | None = None
    net_debt: float | None = None  # total_debt - cash, computed by the service
    total_assets: float | None = None
    total_liabilities: float | None = None
    book_equity: float | None = None

    revenue: float | None = None
    gross_profit: float | None = None
    ebit: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    capex: float | None = None
    depreciation_amortization: float | None = None
    fcf: float | None = None  # ocf - capex
    eps: float | None = None
    dps: float | None = None

    risk_free_rate: float | None = None  # from FRED when available
    equity_risk_premium: float | None = None  # configured, not invented
    peers: list[ComparableCompany] = Field(default_factory=list)
    transactions: list[PrecedentTransaction] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _default_net_debt(self) -> "ValuationInputs":
        if self.net_debt is None and self.total_debt is not None and self.cash is not None:
            self.net_debt = self.total_debt - self.cash
        return self

    def concept_history(self, concept: str) -> list[Fact]:
        return [p.facts[concept] for p in self.history if concept in p.facts]

    @property
    def price(self) -> float | None:
        return self.market.price if self.market else None


# ---------------------------------------------------------------------------
# Per-model assumptions (validated, configurable, echoed into results)
# ---------------------------------------------------------------------------


class DcfAssumptions(BaseModel):
    forecast_years: int = Field(5, ge=1, le=15)
    wacc: float = Field(..., gt=0.0, lt=1.0)
    terminal_growth: float = Field(0.025, ge=-0.05, lt=1.0)
    tax_rate: float = Field(0.21, ge=0.0, le=0.75)
    revenue_growth: float = Field(0.05, ge=-0.5, le=1.0)  # annual, all forecast years
    target_operating_margin: float | None = Field(None, ge=-1.0, le=1.0)  # None = hold latest
    capex_pct_revenue: float | None = Field(None, ge=0.0, le=1.0)  # None = historical avg
    depreciation_pct_revenue: float | None = Field(None, ge=0.0, le=1.0)
    nwc_pct_revenue_change: float = Field(0.05, ge=-1.0, le=1.0)
    terminal_method: Literal["gordon", "exit_multiple"] = "gordon"
    exit_ev_ebitda: float | None = Field(None, gt=0.0)
    annual_share_growth: float = Field(0.0, ge=-0.2, le=0.2)  # dilution

    @model_validator(mode="after")
    def _check_terminal(self) -> "DcfAssumptions":
        if self.terminal_method == "gordon" and self.terminal_growth >= self.wacc:
            raise ValueError("terminal_growth must be below wacc")
        if self.terminal_method == "exit_multiple" and not self.exit_ev_ebitda:
            raise ValueError("exit_ev_ebitda required for exit_multiple terminal method")
        return self


class DdmAssumptions(BaseModel):
    required_return: float = Field(..., gt=0.0, lt=1.0)
    stage1_years: int = Field(5, ge=1, le=15)
    stage1_growth: float = Field(0.06, ge=-0.5, le=1.0)
    terminal_growth: float = Field(0.03, ge=-0.05, lt=1.0)

    @model_validator(mode="after")
    def _check(self) -> "DdmAssumptions":
        if self.terminal_growth >= self.required_return:
            raise ValueError("terminal_growth must be below required_return")
        return self


class ComparablesAssumptions(BaseModel):
    multiples: list[Literal["ev_ebitda", "pe", "ev_sales", "pb"]] = Field(
        default_factory=lambda: ["ev_ebitda", "pe"]
    )
    statistic: Literal["median", "mean"] = "median"
    min_peers: int = Field(2, ge=1)


class PrecedentAssumptions(BaseModel):
    multiple: Literal["ev_ebitda", "ev_sales"] = "ev_ebitda"
    statistic: Literal["median", "mean"] = "median"
    min_transactions: int = Field(2, ge=1)
    control_premium: float = Field(0.0, ge=0.0, le=1.0)


class ResidualIncomeAssumptions(BaseModel):
    cost_of_equity: float = Field(..., gt=0.0, lt=1.0)
    forecast_years: int = Field(10, ge=1, le=20)
    roe: float | None = Field(None, gt=-1.0, lt=1.0)  # None = avg of history
    retention_ratio: float = Field(0.4, ge=0.0, le=1.0)


class EpvAssumptions(BaseModel):
    wacc: float = Field(..., gt=0.0, lt=1.0)
    tax_rate: float = Field(0.21, ge=0.0, le=0.75)
    margin_normalization: Literal["latest", "historical_average"] = "historical_average"


class GrahamAssumptions(BaseModel):
    growth_rate: float | None = Field(None, ge=-0.1, le=0.2)  # None = derived, echoed
    quality_required: bool = True  # apply Graham's defensive screens as warnings


class AssetBasedAssumptions(BaseModel):
    asset_adjustments: float = Field(0.0)  # e.g. marked-to-market revaluation
    liability_adjustments: float = Field(0.0)


class SotpAssumptions(BaseModel):
    segment_multiples: dict[str, float] = Field(default_factory=dict)  # segment name -> multiple
    multiple_metric: Literal["ev_ebitda", "ev_sales"] = "ev_ebitda"


# ---------------------------------------------------------------------------
# Model outputs
# ---------------------------------------------------------------------------


class ModelResult(BaseModel):
    model: str
    applicable: bool
    value_per_share: float | None = None
    enterprise_value: float | None = None
    equity_value: float | None = None
    confidence: Confidence = "medium"
    suitability: float = Field(0.5, ge=0.0, le=1.0)
    assumptions: dict[str, object] = Field(default_factory=dict)
    formula: str = ""
    steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    excluded_reason: str | None = None


class ExcludedModel(BaseModel):
    model: str
    reason: str


class Reconciliation(BaseModel):
    included: list[str] = Field(default_factory=list)
    excluded: list[ExcludedModel] = Field(default_factory=list)
    family_values: dict[str, float] = Field(default_factory=dict)  # income/market/asset -> value/sh
    low: float | None = None
    base: float | None = None
    high: float | None = None
    method: str = ""
    notes: list[str] = Field(default_factory=list)


class DataQuality(BaseModel):
    missing: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenarios & sensitivity
# ---------------------------------------------------------------------------


class ScenarioSpec(BaseModel):
    """Deltas applied to the base DCF assumption set. All optional overrides."""

    name: Literal["bear", "base", "bull"]
    revenue_growth_delta: float = 0.0
    revenue_growth_multiplier: float = 1.0
    operating_margin_delta: float = 0.0
    tax_rate: float | None = Field(None, ge=0.0, le=0.75)
    wacc_delta: float = 0.0
    terminal_growth_delta: float = 0.0
    capex_pct_delta: float = 0.0
    nwc_pct_delta: float = 0.0
    annual_share_growth_delta: float = 0.0

    @model_validator(mode="after")
    def _positive_wacc_shift(self) -> "ScenarioSpec":
        if self.name == "bear" and self.wacc_delta < 0:
            raise ValueError("bear scenarios should not lower WACC below base")
        return self


class ScenarioResult(BaseModel):
    name: str
    value_per_share: float | None
    applied_assumptions: dict[str, object] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SensitivityPoint(BaseModel):
    wacc: float
    terminal_growth: float
    value_per_share: float | None


class ScenarioSet(BaseModel):
    bear: ScenarioResult
    base: ScenarioResult
    bull: ScenarioResult
    sensitivity: list[SensitivityPoint] = Field(default_factory=list)
    sensitivity_note: str = "DCF value per share across WACC (rows) × terminal growth (columns)"


# ---------------------------------------------------------------------------
# Analysis modules
# ---------------------------------------------------------------------------


class HealthMetrics(BaseModel):
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    fcf_margin: float | None = None
    roe: float | None = None
    roic: float | None = None
    current_ratio: float | None = None
    debt_to_ebitda: float | None = None
    net_debt_to_ebitda: float | None = None
    interest_coverage: float | None = None
    ocf_to_net_income: float | None = None
    revenue_cagr_3y: float | None = None
    notes: list[str] = Field(default_factory=list)


class ValuationMultiples(BaseModel):
    pe: float | None = None
    forward_pe: float | None = None  # needs estimates -> usually None
    peg: float | None = None
    ps: float | None = None
    pb: float | None = None
    ev_ebitda: float | None = None
    ev_fcf: float | None = None
    fcf_yield: float | None = None
    notes: list[str] = Field(default_factory=list)


class GrowthAnalysis(BaseModel):
    revenue_cagr: float | None = None
    revenue_cagr_3y: float | None = None
    net_income_cagr: float | None = None
    eps_cagr: float | None = None
    fcf_cagr: float | None = None
    estimates_available: bool = False
    notes: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    altman_z: float | None = None
    altman_zone: str | None = None  # safe / grey / distress
    leverage_notes: list[str] = Field(default_factory=list)
    interest_coverage: float | None = None
    consecutive_fcf_negative: int = 0
    flags: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Explanation & report
# ---------------------------------------------------------------------------


class ValuationExplanation(BaseModel):
    company: str
    headline: str
    methodology: str
    models_used: list[str] = Field(default_factory=list)
    models_excluded: list[ExcludedModel] = Field(default_factory=list)
    key_assumptions: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    what_would_invalidate: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    is_illustrative: bool = False


class ValuationReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    report_id: str | None = None
    generated_at: datetime
    company: CompanyProfile
    market: MarketData | None = None
    inputs: ValuationInputs
    models: list[ModelResult]
    reconciliation: Reconciliation
    scenarios: ScenarioSet | None = None
    health: HealthMetrics | None = None
    multiples: ValuationMultiples | None = None
    growth: GrowthAnalysis | None = None
    risks: RiskAssessment | None = None
    explanation: ValuationExplanation | None = None
    data_quality: DataQuality
    is_illustrative: bool = False


class ApiError(BaseModel):
    error: dict[str, str]
