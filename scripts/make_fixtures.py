"""Record real SEC companyfacts entries as offline regression fixtures.

Run once (network) to refresh fixtures:
    python scripts/make_fixtures.py
Produces tests/fixtures/{ticker}_facts.json with raw XBRL entries for the tags
FAIRVALUE normalizes, exactly as SEC EDGAR returns them (trimmed to 10-K/20-F
filings from 2015 onward, plus full history for balance-sheet tags where
restatement examples live).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fairvalue.data.base import http_get  # noqa: E402
from fairvalue.data.edgar import (  # noqa: E402
    DEFAULT_UA,
    DEI_SHARES_TAG,
    FACTS_URL,
    COMBINED_DEBT_TAGS,
    TAG_MAP,
)
from fairvalue.data.edgar import EdgarProvider  # noqa: E402

TICKERS = ["AAPL", "JNJ", "WMT"]  # tech/healthcare/retail — different FY conventions
SINCE = "2015"
BALANCE_TAGS_KEEP_ALL = {"AssetsCurrent", "LiabilitiesCurrent", "StockholdersEquity",
                         "RetainedEarningsAccumulatedDeficit"}


def trim(entries: list[dict], *, keep_all: bool = False) -> list[dict]:
    out = []
    for e in entries:
        if keep_all or str(e.get("filed", "")) >= SINCE:
            out.append(e)
    return out


def main() -> None:
    provider = EdgarProvider()
    fixtures_dir = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    for ticker in TICKERS:
        cik = provider._cik(ticker)
        url = FACTS_URL.format(cik=cik)
        payload = json.loads(http_get(url, user_agent=DEFAULT_UA))
        facts = payload.get("facts", {})

        us_gaap = facts.get("us-gaap", {})
        wanted_tags: list[str] = []
        for tags in TAG_MAP.values():
            wanted_tags.extend(tags)
        wanted_tags.extend(COMBINED_DEBT_TAGS)

        fixture: dict = {"ticker": ticker, "cik": f"{cik:010d}", "locator": url, "us_gaap": {}, "dei": {}}
        for tag in sorted(set(wanted_tags)):
            node = us_gaap.get(tag)
            if not node:
                continue
            units = node.get("units", {})
            entries: list[dict] = []
            for unit, vals in units.items():
                entries.extend(trim(vals, keep_all=tag in BALANCE_TAGS_KEEP_ALL))
            if entries:
                fixture["us_gaap"][tag] = entries

        dei_node = facts.get("dei", {}).get(DEI_SHARES_TAG, {})
        dei_entries: list[dict] = []
        for vals in dei_node.get("units", {}).values():
            dei_entries.extend(trim(vals)[-10:])  # recent cover pages only
        fixture["dei"][DEI_SHARES_TAG] = dei_entries

        # submissions meta (SIC) for industry rules
        try:
            meta = json.loads(http_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                                       user_agent=DEFAULT_UA))
            fixture["sic"] = meta.get("sic")
            fixture["sic_description"] = meta.get("sicDescription")
        except Exception as exc:  # fixture still usable without meta
            print(f"  {ticker}: submissions meta failed: {exc}")

        path = fixtures_dir / f"{ticker.lower()}_facts.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        n_entries = sum(len(v) for v in fixture["us_gaap"].values()) + len(fixture["dei"].get(DEI_SHARES_TAG, []))
        print(f"{ticker}: {len(fixture['us_gaap'])} tags, {n_entries} entries -> {path.name}")


if __name__ == "__main__":
    main()
