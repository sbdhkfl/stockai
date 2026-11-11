"""Data layer: provider protocol, normalization and provider registry."""

from __future__ import annotations

from fairvalue.core.schemas import (
    ComparableCompany,
    CompanyProfile,
    Fundamentals,
    MarketData,
    PrecedentTransaction,
    Segment,
)
from fairvalue.data.base import ProviderError, clear_cache

__all__ = [
    "ProviderError",
    "clear_cache",
    "DemoDataProvider",
    "LiveDataProvider",
    "get_provider",
]


class DemoDataProvider:
    """Illustrative provider — every value labeled ``is_illustrative=True``."""

    name = "demo"

    def __init__(self) -> None:
        from fairvalue.data.demo import DemoProvider

        self._p = DemoProvider()

    def __getattr__(self, item: str):
        return getattr(self._p, item)


class LiveDataProvider:
    """Composite of real free sources: SEC EDGAR (fundamentals) + Stooq (prices)
    + FRED (macro). Peers/precedent transactions/segments have no free source and
    are intentionally empty — models depending on them report a clear exclusion
    reason rather than borrowing invented data."""

    name = "live"

    def __init__(self) -> None:
        from fairvalue.data.edgar import EdgarProvider
        from fairvalue.data.fred import FredProvider
        from fairvalue.data.stooq import StooqProvider

        self._edgar = EdgarProvider()
        self._stooq = StooqProvider()
        self._fred = FredProvider()

    def search_company(self, query: str) -> list[CompanyProfile]:
        return self._edgar.search_company(query)

    def get_fundamentals(self, ticker: str) -> Fundamentals:
        return self._edgar.get_fundamentals(ticker)

    def get_market_data(self, ticker: str) -> MarketData | None:
        return self._stooq.get_market_data(ticker)

    def get_peers(self, ticker: str) -> list[ComparableCompany]:
        return []

    def get_transactions(self, ticker: str) -> list[PrecedentTransaction]:
        return []

    def get_segments(self, ticker: str) -> list[Segment]:
        return []

    def get_rate(self, series: str) -> float | None:
        return self._fred.get_rate(series)


def get_provider(demo: bool = False):
    """Explicit selection only: ``demo=True`` returns labeled illustrative data;
    there is no silent fallback from live to demo (ARCHITECTURE.md §4.5)."""
    if demo:
        return DemoDataProvider()
    return LiveDataProvider()
