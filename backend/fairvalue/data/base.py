"""Provider-independent financial data interfaces (ARCHITECTURE.md §6)."""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from fairvalue.core.schemas import (
    ComparableCompany,
    CompanyProfile,
    Fundamentals,
    MarketData,
    PrecedentTransaction,
    Segment,
)


class ProviderError(Exception):
    """A data provider failed. Carries a stable error code for the API layer."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@runtime_checkable
class FinancialDataProvider(Protocol):
    """Everything the service layer may ask a data source for.

    Implementations must never invent values: on missing data they return
    empty structures or ``None``, and surface problems as ``ProviderError``.
    """

    name: str

    def search_company(self, query: str) -> list[CompanyProfile]: ...

    def get_fundamentals(self, ticker: str) -> Fundamentals: ...

    def get_market_data(self, ticker: str) -> MarketData | None: ...

    def get_peers(self, ticker: str) -> list[ComparableCompany]: ...

    def get_transactions(self, ticker: str) -> list[PrecedentTransaction]: ...

    def get_segments(self, ticker: str) -> list[Segment]: ...

    def get_rate(self, series: str) -> float | None:
        """Macro series: 'risk_free_10y', 'inflation', 'fed_funds', 'gdp', 'unemployment'."""
        ...


# --- shared HTTP helper: UA-identifying header, backoff, tiny TTL cache -------------

_cache: dict[str, tuple[float, bytes]] = {}
CACHE_TTL = 300.0  # seconds; respects SEC/FRED by not re-hitting on every request


def http_get(url: str, *, user_agent: str, timeout: float = 30.0, retries: int = 3) -> bytes:
    """GET with required User-Agent, exponential backoff on 429/503, in-process TTL cache."""
    now = time.time()
    hit = _cache.get(url)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]

    import httpx

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = httpx.get(url, headers={"User-Agent": user_agent}, timeout=timeout, follow_redirects=True)
            if resp.status_code in (429, 503):
                time.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            _cache[url] = (time.time(), resp.content)
            return resp.content
        except httpx.HTTPError as exc:  # network / 5xx
            last_exc = exc
            time.sleep(1.0 * (attempt + 1))
    raise ProviderError("provider_unreachable", f"{url} unreachable after {retries} attempts: {last_exc}")


def clear_cache() -> None:
    _cache.clear()
