"""ILLUSTRATIVE data provider — synthetic, clearly-labeled figures for offline
tests, CI and dashboard demo mode.

Every fact produced here carries ``is_illustrative=True`` end-to-end (FACT,
fundamentals, market data, report, API response, dashboard badge). This data is
never mixed with reported financials and never silently substitutes for them.
All money values are in millions of USD in the tables below; they are converted
to absolute USD when Facts are built.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fairvalue.core.schemas import (
    CANONICAL_CONCEPTS,
    FLOW_CONCEPTS,
    ComparableCompany,
    CompanyProfile,
    Fact,
    Fundamentals,
    MarketData,
    PeriodFinancials,
    PrecedentTransaction,
    PricePoint,
    Segment,
    SourceRef,
)

M = 1_000_000
NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)
SOURCE = SourceRef(provider="demo", locator="fairvalue.data.demo", retrieved_at=NOW, license="synthetic")

MONEY = (
    "revenue", "gross_profit", "ebit", "net_income", "operating_cash_flow", "capex",
    "depreciation_amortization", "cash", "total_debt", "total_assets", "total_liabilities",
    "current_assets", "current_liabilities", "equity",
)
ALIAS = {  # table key -> canonical concept (ebitda derived later, dps/eps explicit)
    "dep": "depreciation_amortization",
    "oca": "current_assets",
    "ocl": "current_liabilities",
    "shares": "shares_outstanding",
    "eps": "eps_diluted",
}

_COMPANIES: dict[str, dict[str, Any]] = {
    "AUR": {
        "name": "Aurora Software Inc.",
        "sector": "Technology",
        "industry": "Application Software",
        "price": 45.0,
        "shares": 810,
        "history": [
            {"fy": 2023, "end": "2023-12-31", "revenue": 4000, "gross_profit": 3040, "ebit": 920,
             "net_income": 700, "operating_cash_flow": 1050, "capex": 180, "dep": 120,
             "cash": 2500, "total_debt": 600, "total_assets": 7000, "total_liabilities": 3000,
             "oca": 3500, "ocl": 1400, "equity": 4000, "shares": 800, "eps": 0.875, "dps": 0.80},
            {"fy": 2024, "end": "2024-12-31", "revenue": 4400, "gross_profit": 3344, "ebit": 1012,
             "net_income": 770, "operating_cash_flow": 1150, "capex": 200, "dep": 130,
             "cash": 2800, "total_debt": 550, "total_assets": 7600, "total_liabilities": 3200,
             "oca": 3900, "ocl": 1500, "equity": 4400, "shares": 805, "eps": 0.9565, "dps": 0.85},
            {"fy": 2025, "end": "2025-12-31", "revenue": 4840, "gross_profit": 3678, "ebit": 1113,
             "net_income": 845, "operating_cash_flow": 1250, "capex": 220, "dep": 140,
             "cash": 3100, "total_debt": 500, "total_assets": 8200, "total_liabilities": 3350,
             "oca": 4300, "ocl": 1600, "equity": 4850, "shares": 810, "eps": 1.0432, "dps": 0.90},
        ],
        "peers": [
            {"ticker": "NOVA", "name": "Nova Systems", "price": 120, "shares": 500, "total_debt": 2000,
             "cash": 5000, "ebitda": 2200, "net_income": 1600, "equity": 20000, "revenue": 9000},
            {"ticker": "BLUX", "name": "Bluxo Corp", "price": 80, "shares": 700, "total_debt": 1000,
             "cash": 3000, "ebitda": 2400, "net_income": 1800, "equity": 25000, "revenue": 10000},
            {"ticker": "KITE", "name": "Kite Digital", "price": 55, "shares": 600, "total_debt": 500,
             "cash": 1500, "ebitda": 1100, "net_income": 750, "equity": 9000, "revenue": 4500},
            {"ticker": "ORBT", "name": "Orbit Suites", "price": 210, "shares": 300, "total_debt": 3000,
             "cash": 7000, "ebitda": 2600, "net_income": 2000, "equity": 30000, "revenue": 11000},
        ],
        "transactions": [
            {"target": "Streamly", "acquirer": "Nebula Corp", "announced": "2025-03-10",
             "enterprise_value": 26000, "ebitda": 1000, "revenue": 3200},
            {"target": "Cadence Apps", "acquirer": "NOVA", "announced": "2024-09-01",
             "enterprise_value": 17400, "ebitda": 650, "revenue": 2100},
        ],
        "segments": [
            {"name": "Cloud", "metric": "ebitda", "value": 900, "multiple": 25.0},
            {"name": "OnPrem", "metric": "ebitda", "value": 353, "multiple": 15.0},
        ],
    },
    "HELI": {
        "name": "Helios Energy Group",
        "sector": "Energy",
        "industry": "Integrated Oil & Gas",
        "price": 32.0,
        "shares": 1000,
        "history": [
            {"fy": 2023, "end": "2023-12-31", "revenue": 10500, "gross_profit": 3150, "ebit": 1500,
             "net_income": 1200, "operating_cash_flow": 2100, "capex": 1400, "dep": 2500,
             "cash": 3000, "total_debt": 7000, "total_assets": 24000, "total_liabilities": 14000,
             "oca": 6500, "ocl": 6200, "equity": 10000, "shares": 1000, "eps": 1.20, "dps": 1.30},
            {"fy": 2024, "end": "2024-12-31", "revenue": 11200, "gross_profit": 3360, "ebit": 1600,
             "net_income": 1300, "operating_cash_flow": 2250, "capex": 1450, "dep": 2550,
             "cash": 3200, "total_debt": 6800, "total_assets": 24500, "total_liabilities": 14000,
             "oca": 6800, "ocl": 6300, "equity": 10500, "shares": 1000, "eps": 1.30, "dps": 1.45},
            {"fy": 2025, "end": "2025-12-31", "revenue": 12000, "gross_profit": 3600, "ebit": 1800,
             "net_income": 1800, "operating_cash_flow": 2400, "capex": 1500, "dep": 2600,
             "cash": 3500, "total_debt": 6500, "total_assets": 25000, "total_liabilities": 14000,
             "oca": 7000, "ocl": 6500, "equity": 11000, "shares": 1000, "eps": 1.80, "dps": 1.60},
        ],
        "peers": [
            {"ticker": "TRIG", "name": "Triglav Petroleum", "price": 40, "shares": 700, "total_debt": 14000,
             "cash": 6000, "ebitda": 4800, "net_income": 3000, "equity": 20000, "revenue": 30000},
            {"ticker": "NORD", "name": "Nordvik Energy", "price": 60, "shares": 650, "total_debt": 16000,
             "cash": 6000, "ebitda": 6000, "net_income": 4200, "equity": 25000, "revenue": 35000},
            {"ticker": "DRMO", "name": "Dromos Oil", "price": 30, "shares": 500, "total_debt": 10000,
             "cash": 5000, "ebitda": 2900, "net_income": 1600, "equity": 15000, "revenue": 22000},
            {"ticker": "SLT", "name": "Salter Resources", "price": 55, "shares": 550, "total_debt": 12000,
             "cash": 4250, "ebitda": 4900, "net_income": 3300, "equity": 22000, "revenue": 32000},
        ],
        "transactions": [
            {"target": "Deltafield", "acquirer": "NORD", "announced": "2025-06-01",
             "enterprise_value": 36000, "ebitda": 5000, "revenue": 26000},
            {"target": "Petro Sud", "acquirer": "TRIG", "announced": "2024-11-15",
             "enterprise_value": 25000, "ebitda": 3400, "revenue": 18000},
        ],
        "segments": [],
    },
    "CRVN": {
        "name": "Caravan Retail Corp.",
        "sector": "Consumer Cyclical",
        "industry": "Specialty Retail",
        "price": 48.0,
        "shares": 500,
        "history": [
            {"fy": 2023, "end": "2023-12-31", "revenue": 17500, "gross_profit": 5600, "ebit": 1350,
             "net_income": 875, "operating_cash_flow": 1600, "capex": 800, "dep": 660,
             "cash": 1000, "total_debt": 4300, "total_assets": 11500, "total_liabilities": 7400,
             "oca": 5100, "ocl": 4000, "equity": 4100, "shares": 500, "eps": 1.75, "dps": 0.85},
            {"fy": 2024, "end": "2024-12-31", "revenue": 18700, "gross_profit": 5984, "ebit": 1480,
             "net_income": 950, "operating_cash_flow": 1750, "capex": 850, "dep": 680,
             "cash": 1100, "total_debt": 4150, "total_assets": 11700, "total_liabilities": 7450,
             "oca": 5300, "ocl": 4100, "equity": 4250, "shares": 500, "eps": 1.90, "dps": 0.90},
            {"fy": 2025, "end": "2025-12-31", "revenue": 20000, "gross_profit": 6400, "ebit": 1600,
             "net_income": 1050, "operating_cash_flow": 1900, "capex": 900, "dep": 700,
             "cash": 1200, "total_debt": 4000, "total_assets": 12000, "total_liabilities": 7500,
             "oca": 5500, "ocl": 4200, "equity": 4500, "shares": 500, "eps": 2.10, "dps": 1.00},
        ],
        "peers": [
            {"ticker": "MKTX", "name": "Market Square", "price": 60, "shares": 400, "total_debt": 6000,
             "cash": 3000, "ebitda": 3500, "net_income": 1800, "equity": 12000, "revenue": 28000},
            {"ticker": "GRSH", "name": "Groveshops Inc", "price": 75, "shares": 550, "total_debt": 8000,
             "cash": 3000, "ebitda": 5000, "net_income": 2600, "equity": 18000, "revenue": 40000},
            {"ticker": "PLND", "name": "Palisade Retail", "price": 40, "shares": 450, "total_debt": 5000,
             "cash": 2500, "ebitda": 2200, "net_income": 1100, "equity": 8000, "revenue": 16000},
            {"ticker": "BLMD", "name": "Bloomdale Co", "price": 35, "shares": 350, "total_debt": 4000,
             "cash": 3000, "ebitda": 1400, "net_income": 700, "equity": 6000, "revenue": 11000},
        ],
        "transactions": [
            {"target": "Threadline", "acquirer": "GRSH", "announced": "2025-04-20",
             "enterprise_value": 43000, "ebitda": 3400, "revenue": 24000},
            {"target": "Harbor Goods", "acquirer": "MKTX", "announced": "2024-08-05",
             "enterprise_value": 17500, "ebitda": 1450, "revenue": 11000},
        ],
        "segments": [
            {"name": "Retail North", "metric": "revenue", "value": 12000, "multiple": 1.4},
            {"name": "Retail South", "metric": "revenue", "value": 5000, "multiple": 1.0},
            {"name": "Digital", "metric": "revenue", "value": 3000, "multiple": 3.0},
        ],
    },
}


class DemoProvider:
    """Offline, fully illustrative provider used by tests and demo mode."""

    name = "demo"

    def __init__(self, companies: dict[str, dict[str, Any]] | None = None):
        self._data = companies or _COMPANIES

    def _entry(self, ticker: str) -> dict[str, Any]:
        key = ticker.upper()
        if key not in self._data:
            from fairvalue.data.base import ProviderError

            raise ProviderError("company_not_found", f"Unknown demo company {ticker!r}")
        return self._data[key]

    def search_company(self, query: str) -> list[CompanyProfile]:
        q = query.strip().lower()
        return [
            self._profile(t)
            for t, e in self._data.items()
            if q in t.lower() or q in str(e["name"]).lower()
        ]

    def _profile(self, ticker: str) -> CompanyProfile:
        e = self._entry(ticker)
        return CompanyProfile(
            ticker=ticker.upper(),
            name=e["name"],
            sector=e.get("sector"),
            industry=e.get("industry"),
            provider=self.name,
            is_illustrative=True,
        )

    def get_fundamentals(self, ticker: str) -> Fundamentals:
        e = self._entry(ticker)
        periods: list[PeriodFinancials] = []
        missing: set[str] = set()
        for row in e["history"]:
            facts: dict[str, Fact] = {}
            period_end = date.fromisoformat(row["end"])
            for key, val in row.items():
                if key in ("fy", "end"):
                    continue
                concept = ALIAS.get(key, key)
                if concept not in ("eps_diluted", "dps", "shares_outstanding"):
                    value = float(val) * M
                else:
                    value = float(val) * (M if concept == "shares_outstanding" else 1)
                facts[concept] = Fact(
                    concept=concept,
                    value=value,
                    unit={"shares_outstanding": "shares", "eps_diluted": "USD/shares", "dps": "USD/shares"}.get(
                        concept, "USD"
                    ),
                    basis="duration" if concept in FLOW_CONCEPTS else "instant",
                    period_start=period_end if concept in FLOW_CONCEPTS else None,
                    period_end=period_end,
                    fiscal_year=row["fy"],
                    is_estimate=False,
                    form="illustrative-filing",
                    accession=f"DEMO-{row['fy']}-{concept}",
                    filed_at=NOW,
                    is_illustrative=True,
                    source=SOURCE,
                )
            periods.append(PeriodFinancials(fiscal_year=row["fy"], period_end=period_end, facts=facts))
        periods.sort(key=lambda p: p.period_end)
        missing = {c for c in CANONICAL_CONCEPTS if c not in periods[-1].facts and c != "ebitda"}
        from fairvalue.data.normalize import validate_statements

        return Fundamentals(
            company=self._profile(ticker),
            periods=periods,
            missing_concepts=sorted(missing),
            conflicts=[],
            validation_errors=validate_statements(periods),
        )

    def get_market_data(self, ticker: str) -> MarketData | None:
        e = self._entry(ticker)
        history = _walk(ticker, base=float(e["price"]))
        return MarketData(
            ticker=ticker.upper(),
            price=float(e["price"]),
            as_of=history[-1].day,
            price_history=history,
            is_illustrative=True,
            source=SOURCE,
        )

    def get_peers(self, ticker: str) -> list[ComparableCompany]:
        out = []
        for p in self._entry(ticker)["peers"]:
            mcap = p["price"] * p["shares"]
            out.append(
                ComparableCompany(
                    ticker=p["ticker"],
                    name=p["name"],
                    enterprise_value=(mcap + p["total_debt"] - p["cash"]) * M,
                    ebitda=p["ebitda"] * M,
                    net_income=p["net_income"] * M,
                    equity=p["equity"] * M,
                    revenue=p["revenue"] * M,
                    price=p["price"],
                    shares_outstanding=p["shares"] * M,
                    is_illustrative=True,
                )
            )
        return out

    def get_transactions(self, ticker: str) -> list[PrecedentTransaction]:
        return [
            PrecedentTransaction(
                target=t["target"],
                acquirer=t.get("acquirer"),
                announced=date.fromisoformat(t["announced"]),
                enterprise_value=t["enterprise_value"] * M,
                ebitda=t["ebitda"] * M,
                revenue=t["revenue"] * M,
                is_illustrative=True,
            )
            for t in self._entry(ticker)["transactions"]
        ]

    def get_segments(self, ticker: str) -> list[Segment]:
        return [
            Segment(
                name=s["name"], metric=s["metric"], value=s["value"] * M,
                multiple=s.get("multiple"), is_illustrative=True,
            )
            for s in self._entry(ticker)["segments"]
        ]

    def get_rate(self, series: str) -> float | None:
        return {
            "risk_free_10y": 0.042,
            "fed_funds": 0.045,
            "inflation": 0.025,
            "unemployment": 4.2,
            "gdp": None,
        }.get(series)


def _walk(ticker: str, *, base: float, days: int = 260, seed: int = 0) -> list[PricePoint]:
    """Deterministic illustrative price walk (seeded — reproducible, labeled)."""
    import random
    from datetime import timedelta

    rng = random.Random(seed or sum(ord(c) for c in ticker))
    price = base * 0.82
    day = date(2025, 1, 2)
    out: list[PricePoint] = []
    for _ in range(days):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        price = max(0.5, price * (1 + rng.gauss(0.0007, 0.016)))
        out.append(PricePoint(day=day, close=round(price, 2)))
        day += timedelta(days=1)
    if out:
        out[-1] = PricePoint(day=out[-1].day, close=base)  # anchor to the stated current price
    return out
