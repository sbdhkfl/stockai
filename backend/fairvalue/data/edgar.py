"""SEC EDGAR provider — real reported fundamentals (free, public, no key).

Sources:
- company search: https://www.sec.gov/files/company_tickers.json
- fundamentals:   https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

SEC fair-access rules apply: descriptive User-Agent, modest request rate
(one companyfacts fetch per ticker, cached 5 min).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fairvalue.core.schemas import (
    ComparableCompany,
    CompanyProfile,
    Fundamentals,
    MarketData,
    PrecedentTransaction,
    Segment,
)
from fairvalue.data.base import ProviderError, http_get
from fairvalue.data.normalize import (
    COMBINED_DEBT_TAGS,
    DEI_SHARES_TAG,
    TAG_MAP,
    assemble_fundamentals,
    normalize_entries,
)

TICKER_INDEX_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
DEFAULT_UA = os.environ.get(
    "SEC_EDGAR_UA", "FAIRVALUE-AI/0.1 (open-source valuation research; contact@example.com)"
)


class EdgarProvider:
    name = "sec_edgar"

    def __init__(self, user_agent: str | None = None):
        self.user_agent = user_agent or DEFAULT_UA
        self._index: dict[str, dict] | None = None

    # -- search -----------------------------------------------------------------
    def _load_index(self) -> dict[str, dict]:
        if self._index is None:
            import json

            try:
                raw = json.loads(http_get(TICKER_INDEX_URL, user_agent=self.user_agent))
            except ProviderError:
                raise
            except ValueError as exc:
                raise ProviderError("provider_bad_response", f"SEC ticker index unreadable: {exc}") from exc
            self._index = {
                v["ticker"].upper(): v for v in raw.values() if isinstance(v, dict) and v.get("ticker")
            }
        return self._index

    def _cik(self, ticker: str) -> int:
        entry = self._load_index().get(ticker.upper())
        if not entry:
            raise ProviderError("company_not_found", f"No SEC-listed company for ticker {ticker!r}")
        return int(entry["cik_str"])

    def search_company(self, query: str) -> list[CompanyProfile]:
        q = query.strip().upper()
        idx = self._load_index()
        hits = []
        for ticker, v in idx.items():
            name = str(v.get("title", ""))
            if q in ticker or q in name.upper():
                hits.append(
                    CompanyProfile(
                        ticker=ticker, name=name, cik=str(v["cik_str"]).zfill(10), provider=self.name
                    )
                )
            if len(hits) >= 20:
                break
        return hits

    # -- fundamentals ------------------------------------------------------------
    def get_fundamentals(self, ticker: str) -> Fundamentals:
        import json

        cik = self._cik(ticker)
        locator = FACTS_URL.format(cik=cik)
        try:
            payload = json.loads(http_get(locator, user_agent=self.user_agent))
        except ProviderError:
            raise
        except ValueError as exc:
            raise ProviderError("provider_bad_response", f"companyfacts unreadable for {ticker}: {exc}") from exc

        concept_facts, conflicts = extract_concepts(payload.get("facts", {}), locator=locator)

        entry = self._load_index().get(ticker.upper(), {})
        company = CompanyProfile(
            ticker=ticker.upper(),
            name=str(entry.get("title", ticker.upper())),
            cik=str(cik).zfill(10),
            sector=self._sic_description(cik),
            provider=self.name,
        )
        return assemble_fundamentals(company, concept_facts, conflicts)

    def _sic_description(self, cik: int) -> str | None:
        """SEC SIC description from the submissions feed (used for industry rules)."""
        import json

        url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        try:
            meta = json.loads(http_get(url, user_agent=self.user_agent))
        except (ProviderError, ValueError):
            return None
        desc = meta.get("sicDescription")
        return str(desc) if desc else None

    # -- market / peers / transactions / segments / macro --------------------------
    def get_market_data(self, ticker: str) -> MarketData | None:
        return None  # EDGAR has no prices: price comes from the stooq provider

    def get_peers(self, ticker: str) -> list[ComparableCompany]:
        return []  # peers must be supplied by the caller or demo data

    def get_transactions(self, ticker: str) -> list[PrecedentTransaction]:
        return []

    def get_segments(self, ticker: str) -> list[Segment]:
        return []

    def get_rate(self, series: str) -> float | None:
        return None


def extract_concepts(
    facts: dict, *, locator: str, provider: str = "sec_edgar"
) -> tuple[dict[str, list], list[str]]:
    """Pure XBRL-facts → canonical-concept mapping (used by the provider and by
    offline regression tests over recorded real-filing fixtures).

    Returns ``(concept -> normalized facts, conflicts)``. Extraction never
    invents values: absent tags stay absent and surface as missing concepts.
    """
    concept_facts: dict[str, list] = {}
    conflicts: list[str] = []

    # taxonomy key spelling differs: live companyfacts uses "us-gaap",
    # recorded fixtures use "us_gaap". Accept both; unknown -> empty.
    def _tax(name: str) -> dict:
        return facts.get(name) or facts.get(name.replace("-", "_"), {})

    for concept, tags in TAG_MAP.items():
        collected: list = []
        for tag in tags:
            entries = _unit_entries(_tax("us-gaap"), tag, ("USD", "USD/shares"))
            if not entries:
                continue
            fs, cs = normalize_entries(
                concept, entries, provider=provider, locator=f"{locator}#us-gaap:{tag}"
            )
            # priority-tag merge: keep the first (highest-priority) tag per period
            collected.extend(f for f in fs if f.period_end not in {x.period_end for x in collected})
            conflicts.extend(cs)
        if collected:
            concept_facts[concept] = collected

    # total_debt fallback: sum of noncurrent + current when LongTermDebt is absent
    if "total_debt" not in concept_facts:
        debt_parts: dict = {}
        for tag in COMBINED_DEBT_TAGS:
            fs, cs = normalize_entries(
                "total_debt",
                _unit_entries(_tax("us-gaap"), tag, ("USD",)),
                provider=provider,
                locator=f"{locator}#us-gaap:{tag}",
            )
            conflicts.extend(cs)
            for f in fs:
                debt_parts.setdefault(f.period_end, []).append(f)
        if debt_parts:
            concept_facts["total_debt"] = _merge_debt_parts(debt_parts, locator, provider)

    # shares outstanding: dei cover-page count (own filing date; NEVER its own period)
    dei_node = _tax("dei").get(DEI_SHARES_TAG)
    shares = []
    if isinstance(dei_node, list):
        unit_iter = [dei_node]  # fixture shape: pre-trimmed entry list
    elif isinstance(dei_node, dict):
        unit_iter = list(dei_node.get("units", {}).values())
    else:
        unit_iter = []
    for unit_entries in unit_iter:
        fs, cs = normalize_entries(
            "shares_outstanding", unit_entries, provider=provider,
            locator=f"{locator}#dei:{DEI_SHARES_TAG}",
        )
        conflicts.extend(cs)
        shares.extend(fs)
    if shares:
        latest = max(shares, key=lambda f: f.filed_at or datetime.min.replace(tzinfo=timezone.utc))
        concept_facts["shares_outstanding"] = [latest]

    return concept_facts, sorted(set(conflicts))


def _unit_entries(taxonomy_facts: dict, tag: str, units: tuple[str, ...]) -> list[dict]:
    """Entry extraction tolerant of both shapes:
    - live companyfacts: node = {"units": {"USD": [entry, ...]}} (taxonomy-level dict)
    - recorded fixtures: node = [entry, ...] (pre-trimmed; unit info implied)
    Raises on unknown shapes so a broken offline pipeline cannot silently
    return zero facts (regression: fixtures once produced 0 periods)."""
    node = taxonomy_facts.get(tag)
    if node is None:
        return []
    if isinstance(node, list):
        return list(node)
    if isinstance(node, dict):
        out: list[dict] = []
        for unit in units:
            out.extend(node.get("units", {}).get(unit, []))
        return out
    raise ValueError(f"unrecognized XBRL node shape for {taxonomy}:{tag}: {type(node).__name__}")


def _merge_debt_parts(parts: dict, locator: str, provider: str):
    from fairvalue.core.schemas import Fact, SourceRef

    merged = []
    now = datetime.now(timezone.utc)
    for end, fs in sorted(parts.items()):
        # if a single filing already reported combined debt for this date, trust it
        combined = max(fs, key=lambda f: (f.filed_at or now))
        if len(fs) == 2:
            combined = Fact(
                concept="total_debt",
                value=sum(f.value for f in fs),
                unit="USD",
                period_end=end,
                fiscal_year=fs[0].fiscal_year,
                form=fs[0].form,
                filed_at=fs[0].filed_at,
                source=SourceRef(provider=provider, locator=locator, retrieved_at=now),
            )
        merged.append(combined)
    return merged
