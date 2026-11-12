"""CLI tests — run through main() with parsed argv; demo engine path and
report-on-API path (real uvicorn thread server)."""
import json

import pytest

from fairvalue import cli
from fairvalue.sdk import FairValueClient


def run(*argv):
    return cli.main(list(argv))


def _caps(capsys):
    return json.loads(capsys.readouterr().out)


def test_valuation_json_demo(capsys):
    assert run("--demo", "valuation", "CRVN") == 0
    d = _caps(capsys)
    assert d["company"]["ticker"] == "CRVN"
    assert d["is_illustrative"] is True
    assert d["reconciliation"]["base"] is not None


def test_valuation_models_subset_demo(capsys):
    assert run("valuation", "AUR", "--demo", "--models", "dcf", "epv") == 0
    d = _caps(capsys)
    assert {m["model"] for m in d["models"]} == {"dcf", "epv"}


def test_valuation_text_summary(capsys):
    assert run("--demo", "valuation", "CRVN", "--text") == 0
    out = capsys.readouterr().out
    assert "Fair-value range" in out and "ILLUSTRATIVE" in out


def test_company_found_and_missing(capsys):
    assert run("--demo", "company", "CRVN") == 0
    assert _caps(capsys)["ticker"] == "CRVN"
    assert run("--demo", "company", "ZZZZ") == 1


def test_health_demo(capsys):
    assert run("--demo", "health", "AUR") == 0
    d = _caps(capsys)
    assert "net_margin" in d


def test_risks_demo_reports_gaps_honestly(capsys):
    assert run("--demo", "risks", "CRVN") == 0
    d = _caps(capsys)
    assert "data_gaps" in d and "flags" in d


def test_scenarios_demo(capsys):
    assert run("--demo", "scenarios", "CRVN") == 0
    d = _caps(capsys)
    assert d["bear"]["value_per_share"] < d["base"]["value_per_share"] < d["bull"]["value_per_share"]


def test_statements_demo(capsys):
    assert run("--demo", "statements", "AUR") == 0
    d = _caps(capsys)
    assert d["periods"] and d["periods"][-1]["facts"]


def test_search_demo(capsys):
    assert run("--demo", "search", "aurora") == 0
    assert _caps(capsys)[0]["ticker"] == "AUR"


def test_report_requires_api():
    assert run("report", "r-xyz") == 2  # honest error: needs a running API


def test_api_roundtrip(server_url, capsys):
    with FairValueClient(base_url=server_url) as c:
        rep = c.valuation("AUR", demo=True)
    assert run("--api-url", server_url, "report", rep.report_id) == 0
    d = _caps(capsys)
    assert d["company"]["ticker"] == "AUR"


def test_bad_ticker_via_api_is_typed_error(server_url):
    assert run("--api-url", server_url, "company", "NOPE") == 2
