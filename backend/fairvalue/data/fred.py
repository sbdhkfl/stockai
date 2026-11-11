"""FRED macro provider — free CSV endpoint, no API key required.

Uses https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES> which returns
plain CSV. Values are returned as published (percent units preserved and
converted where the WACC build needs decimals). Failures return ``None``:
macro data gaps are reported, never guessed.
"""

from __future__ import annotations

import pandas as pd

from fairvalue.data.base import ProviderError, http_get

CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
USER_AGENT = "FAIRVALUE-AI/0.1 (open-source valuation research; contact@example.com)"

# requested series -> FRED id
SERIES = {
    "risk_free_10y": "DGS10",
    "fed_funds": "FEDFUNDS",
    "inflation": "CPIAUCSL",
    "gdp": "GDP",
    "unemployment": "UNRATE",
}


class FredProvider:
    name = "fred"

    def get_series(self, series: str) -> float | None:
        """Latest observation for a series ('.' in FRED means missing)."""
        fred_id = SERIES.get(series)
        if not fred_id:
            return None
        try:
            raw = http_get(CSV_URL.format(series=fred_id), user_agent=USER_AGENT)
        except ProviderError:
            return None
        try:
            df = pd.read_csv(pd.io.common.BytesIO(raw))
        except Exception:
            return None
        col = df.columns[-1]  # observation_date,<value>
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if values.empty:
            return None
        latest = float(values.iloc[-1])
        if series == "risk_free_10y":
            return latest / 100.0  # percent -> decimal (10-year constant maturity)
        return latest

    def get_rate(self, series: str) -> float | None:
        return self.get_series(series)

    def inflation_rate(self) -> float | None:
        """Year-over-year CPI inflation as a decimal (for context/assumptions)."""
        try:
            raw = http_get(CSV_URL.format(series=SERIES["inflation"]), user_agent=USER_AGENT)
            df = pd.read_csv(pd.io.common.BytesIO(raw))
        except Exception:
            return None
        col = df.columns[-1]
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(values) < 13:
            return None
        return float(values.iloc[-1] / values.iloc[-13] - 1.0)
