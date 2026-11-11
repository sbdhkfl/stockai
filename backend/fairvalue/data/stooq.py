"""Free end-of-day price history via Stooq (no key, CSV).

If the fetch fails the caller gets a MarketData with ``price=None`` and a
warning — the engine never invents a price. Downstream, valuation reports then
state ``market price: unavailable`` instead of comparing against a fake number.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fairvalue.core.schemas import MarketData, PricePoint, SourceRef
from fairvalue.data.base import ProviderError, http_get

CSV_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
USER_AGENT = "FAIRVALUE-AI/0.1 (open-source valuation research)"


def _symbol(ticker: str) -> str:
    t = ticker.strip().lower()
    return t if "." in t else f"{t}.us"


class StooqProvider:
    name = "stooq"

    def get_market_data(self, ticker: str, *, limit: int = 400) -> MarketData | None:
        url = CSV_URL.format(symbol=_symbol(ticker))
        try:
            raw = http_get(url, user_agent=USER_AGENT).decode("utf-8", errors="replace")
        except ProviderError as exc:
            return MarketData(
                ticker=ticker.upper(),
                price=None,
                warnings=[f"price history unavailable: {exc.message}"],
                source=SourceRef(provider=self.name, locator=url, retrieved_at=datetime.now(timezone.utc)),
            )
        lines = [ln for ln in raw.strip().splitlines() if ln and not ln.lower().startswith("date")]
        points: list[PricePoint] = []
        for ln in lines:
            parts = ln.split(",")
            if len(parts) < 5:
                continue
            try:
                points.append(PricePoint(day=date.fromisoformat(parts[0]), close=float(parts[4])))
            except ValueError:
                continue
        if not points:
            return MarketData(
                ticker=ticker.upper(),
                price=None,
                warnings=["price history empty (delisted, unknown symbol, or blocked)"],
                source=SourceRef(provider=self.name, locator=url, retrieved_at=datetime.now(timezone.utc)),
            )
        points = points[-limit:]
        last = points[-1]
        return MarketData(
            ticker=ticker.upper(),
            price=last.close,
            as_of=last.day,
            price_history=points,
            is_illustrative=False,
            source=SourceRef(provider=self.name, locator=url, retrieved_at=datetime.now(timezone.utc)),
        )
