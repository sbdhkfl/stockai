"""Record real SEC companyfacts fixtures for additional issuers (sprint-2
validation deliverable): JPM (financial), XOM (energy), KO (consumer staples).

Same recording contract as scripts/make_fixtures.py (Lead-owned); kept separate
to avoid overlapping edits. Run once with network access:
    python scripts/make_fixtures_extra.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fairvalue.data.base import http_get  # noqa: E402
from fairvalue.data.edgar import (  # noqa: E402
    COMBINED_DEBT_TAGS, DEFAULT_UA, DEI_SHARES_TAG, FACTS_URL, TAG_MAP)

TICKERS = {"JPM": 19617, "XOM": 34088, "KO": 21344}
BALANCE_TAGS_KEEP_ALL = {"AssetsCurrent", "LiabilitiesCurrent", "StockholdersEquity",
                         "RetainedEarningsAccumulatedDeficit"}


def trim(entries: list[dict], *, keep_all: bool = False) -> list[dict]:
    return [e for e in entries if keep_all or str(e.get("filed", "")) >= "2015"]


def main() -> None:
    fixtures_dir = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    for ticker, cik in TICKERS.items():
        url = FACTS_URL.format(cik=cik)
        payload = json.loads(http_get(url, user_agent=DEFAULT_UA))
        facts = payload.get("facts", {})
        us_gaap = facts.get("us-gaap", {})
        wanted: list[str] = [t for tags in TAG_MAP.values() for t in tags]
        wanted.extend(COMBINED_DEBT_TAGS)
        fixture: dict = {"ticker": ticker, "cik": f"{cik:010d}", "locator": url,
                         "us_gaap": {}, "dei": {}}
        for tag in sorted(set(wanted)):
            node = us_gaap.get(tag)
            if not node:
                continue
            entries: list[dict] = []
            for unit, vals in node.get("units", {}).items():
                entries.extend(trim(vals, keep_all=tag in BALANCE_TAGS_KEEP_ALL))
            if entries:
                fixture["us_gaap"][tag] = entries
        dei_node = facts.get("dei", {}).get(DEI_SHARES_TAG, {})
        dei_entries: list[dict] = []
        for vals in dei_node.get("units", {}).values():
            dei_entries.extend(trim(vals)[-10:])
        fixture["dei"][DEI_SHARES_TAG] = dei_entries
        try:
            meta = json.loads(http_get(
                f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                user_agent=DEFAULT_UA))
            fixture["sic"] = meta.get("sic")
            fixture["sic_description"] = meta.get("sicDescription")
        except Exception as exc:
            print(f"  {ticker}: submissions meta failed: {exc}")
        path = fixtures_dir / f"{ticker.lower()}_facts.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        n = sum(len(v) for v in fixture["us_gaap"].values()) + len(fixture["dei"].get(DEI_SHARES_TAG, []))
        print(f"{ticker}: {len(fixture['us_gaap'])} tags, {n} entries -> {path.name}")


if __name__ == "__main__":
    main()
