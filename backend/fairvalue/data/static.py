"""Static provider: serves agent-supplied data through the provider protocol.

The service layer (load_inputs/run_valuation) only knows how to ask a
``FinancialDataProvider`` for facts, market data, rates and peers. This adapter
answers those questions from a single validated ``AgentSuppliedCompany``
submission — no SEC, no FRED, no Stooq, no network of any kind (req 15).
Because the service path is unchanged, all nine models, reconciliation,
scenarios and the explanation behave exactly as they do for provider data.
"""
from __future__ import annotations

from fairvalue.agent_data import AgentSuppliedCompany, build_valuation_inputs
from fairvalue.core.schemas import (
    CompanyProfile,
    ComparableCompany,
    Fundamentals,
    MarketData,
    PrecedentTransaction,
    Segment,
)


class StaticProvider:
    """FinancialDataProvider backed entirely by an agent submission."""

    name = "agent_supplied"

    def __init__(self, data: AgentSuppliedCompany) -> None:
        self._data = data
        self._result = build_valuation_inputs(data)  # raises ValueError on hard errors

    @property
    def result(self):
        """Validation artifact: issues, provenance summary, missing concepts."""
        return self._result

    def search_company(self, query: str) -> list[CompanyProfile]:
        q = query.strip().lower()
        profile = self._result.inputs.company
        if q and (q in profile.ticker.lower() or q in profile.name.lower()):
            return [profile]
        return []

    def get_fundamentals(self, ticker: str) -> Fundamentals:
        self._only(ticker)
        iv = self._result.inputs
        errors = [f"{i.rule}: {i.message}" for i in self._result.issues]
        return Fundamentals(
            company=iv.company,
            periods=list(iv.history),
            missing_concepts=list(self._result.missing_concepts),
            conflicts=[],
            validation_errors=errors,
        )

    def get_market_data(self, ticker: str) -> MarketData | None:
        self._only(ticker)
        return self._result.inputs.market

    def _only(self, ticker: str) -> None:
        # a submission covers exactly one company: never serve its data under
        # another ticker (peer requests must fail loudly, not silently match)
        from fairvalue.data.base import ProviderError
        if ticker.upper() != self._data.ticker.upper():
            raise ProviderError(
                "not_found",
                f"agent submission covers {self._data.ticker} only; "
                f"{ticker.upper()} was not supplied")

    def get_peers(self, ticker: str) -> list[ComparableCompany]:
        return list(self._result.inputs.peers)

    def get_transactions(self, ticker: str) -> list[PrecedentTransaction]:
        return list(self._result.inputs.transactions)

    def get_segments(self, ticker: str) -> list[Segment]:
        return list(self._result.inputs.segments)

    def get_rate(self, series: str) -> float | None:
        # only the series the agent actually supplied; everything else None
        if series == "risk_free_10y":
            return self._data.risk_free_rate
        return None
