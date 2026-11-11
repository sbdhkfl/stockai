"""Data quality engine tests."""
import pytest
from fairvalue.data_quality import (validate, check_currency_consistency,
                                    check_duplicates, check_outlier,
                                    check_share_counts, check_staleness,
                                    check_period_alignment, PROVENANCE_KINDS)


def test_provenance_kinds_enforced():
    issues = validate(100.0, "revenue", provenance="reported")
    assert issues == []
    issues = validate(100.0, "revenue", provenance="alien_guesstimate")
    assert issues and issues[0].rule == "provenance_kind"
    assert issues[0].severity == "error"


def test_missing_value_blocks():
    issues = validate(None, "ebitda")
    assert issues[0].rule == "missing_value" and issues[0].severity == "error"
    issues = validate(float("nan"), "ebitda")
    assert issues[0].rule == "missing_value"


def test_wrong_unit_plausibility_band():
    # revenue declared in millions but a thousands-scale value slips through
    issues = validate(5000.0, "revenue_musd", plausible=(10, 900))
    assert any(i.rule == "wrong_unit" for i in issues)
    assert validate(500.0, "revenue_musd", plausible=(10, 900)) == []


def test_negative_where_forbidden():
    issues = validate(-5.0, "shares_outstanding", allow_negative=False)
    assert issues[0].rule == "negative_value" and issues[0].severity == "error"
    # negatives allowed where economically meaningful (net debt, FCF)
    assert validate(-200.0, "net_debt") == []


def test_currency_mismatch():
    issues = check_currency_consistency({"revenue": "USD", "ebitda": "EUR"})
    assert issues[0].rule == "currency_mismatch" and issues[0].severity == "error"
    assert check_currency_consistency({"revenue": "USD", "ebitda": "USD"}) == []


def test_period_mismatch():
    issues = check_period_alignment({"revenue": (2023, 12, 31), "ebitda": (2024, 3, 31)})
    assert any(i.rule == "period_mismatch" for i in issues)
    assert check_period_alignment({"revenue": (2023, 12, 31),
                                   "ebitda": (2023, 12, 31)}) == []


def test_duplicates_detected():
    rec = {"company": "X", "statement": "IS", "line_item": "revenue",
           "period": "2023", "source": "10-K"}
    assert check_duplicates([rec, dict(rec)]) and len(check_duplicates([rec])) == 0


def test_outlier_robust_mad():
    series = [10.0, 10.5, 10.2, 9.8, 10.1, 500.0]
    issues = check_outlier(series, "fcf")
    assert len(issues) == 1 and issues[0].value_seen == 500.0
    assert check_outlier([10.0, 10.1], "fcf") == []      # too few points
    assert check_outlier([7.0, 7.0, 7.0, 7.0], "fcf") == []  # MAD=0 series


def test_share_count_rules():
    assert check_share_counts(100.0, 103.0) == []
    assert check_share_counts(100.0, 95.0)[0].severity == "error"   # diluted < basic
    assert check_share_counts(100.0, 130.0)[0].severity == "warning"  # >20% gap
    assert check_share_counts(None, None) == []                     # absent -> no opinion


def test_staleness():
    assert check_staleness(100) is None
    assert check_staleness(800).rule == "stale_data"
    assert check_staleness(None).severity == "warning"


def test_estimate_is_not_reported():
    """The engine can only carry the tag; the kind must survive into output."""
    assert "estimate" in PROVENANCE_KINDS and "reported" in PROVENANCE_KINDS
