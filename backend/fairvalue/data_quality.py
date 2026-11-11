"""Data quality engine (docs/DATA_VALIDATION.md).

Validation never repairs data silently: it classifies issues with severity
('error' blocks valuation, 'warning' attaches to output).
"""
import math
from dataclasses import dataclass

PROVENANCE_KINDS = ("reported", "guidance", "estimate", "model_assumption",
                    "ai_interpretation")


@dataclass(frozen=True)
class Issue:
    rule: str
    field: str
    message: str
    severity: str
    value_seen: object = None


def _issue(rule, field, message, severity, value=None):
    return Issue(rule, field, message, severity, value)


def check_provenance(kind: str, field: str = "provenance_kind") -> Issue:
    if kind not in PROVENANCE_KINDS:
        return _issue("provenance_kind", field,
                      f"unknown provenance kind '{kind}'; must be one of "
                      f"{PROVENANCE_KINDS}", "error", kind)
    return None


def check_required(value, field: str) -> Issue:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return _issue("missing_value", field, "required value missing or NaN", "error")
    return None


def check_magnitude(value: float, field: str, low: float, high: float) -> Issue:
    """Plausibility band to catch wrong-unit ingestion (e.g. thousands vs millions)."""
    if value is not None and math.isfinite(value) and not (low <= value <= high):
        return _issue("wrong_unit", field,
                      f"value {value} outside plausible band [{low}, {high}] "
                      "for declared unit — possible thousands/millions confusion",
                      "warning", value)
    return None


def check_currency_consistency(currencies: dict) -> list:
    """currencies: {field: currency_code}. One composite must be single-currency."""
    codes = {c for c in currencies.values() if c}
    if len(codes) > 1:
        return [_issue("currency_mismatch", ", ".join(currencies),
                       f"mixed currencies {sorted(codes)} in one composite; "
                       "convert with a dated FX rate and record it", "error")]
    return []


def check_period_alignment(fiscal_period_ends: dict, max_days: int = 35) -> list:
    """fiscal_period_ends: {field: (year, month, day)} — naive date tuples."""
    ends = [d for d in fiscal_period_ends.values() if d]
    if len({(m, d) for (_, m, d) in ends}) > 1:
        day_diff = max(d for (_, _, d) in ends) - min(d for (_, _, d) in ends)
        if day_diff > 0:  # different day-of-month on same-month ends
            pass
    months = {(y, m) for (y, m, _) in ends}
    if len(months) > 1:
        return [_issue("period_mismatch", "composite",
                       f"financial periods span {sorted(months)}; ratios mix "
                       "accounting periods", "warning")]
    return []


def check_duplicates(records: list, key_fields=("company", "statement", "line_item",
                                                "period", "source")) -> list:
    seen, issues = set(), []
    for r in records:
        key = tuple(r.get(k) for k in key_fields)
        if key in seen:
            issues.append(_issue("duplicate_record", str(key),
                                 "duplicate record for same company/statement/"
                                 "line_item/period/source", "error", key))
        seen.add(key)
    return issues


def check_restatement(records: list) -> list:
    issues = []
    for r in records:
        if r.get("restatement_of"):
            issues.append(_issue("restatement", r.get("line_item", "?"),
                                 "restated value supersedes original; newest kept, "
                                 "both retained for audit", "warning",
                                 r.get("restatement_of")))
    return issues


def check_negative(value: float, field: str) -> Issue:
    if value is not None and math.isfinite(value) and value < 0:
        return _issue("negative_value", field,
                      f"{field} is negative where the domain forbids it", "error", value)
    return None


def check_outlier(values: list, field: str, mad_threshold: float = 5.0) -> list:
    """Robust outlier: distance from median > 5 * MAD (median absolute deviation)."""
    clean = [v for v in values if v is not None and math.isfinite(v)]
    if len(clean) < 3:
        return []
    s = sorted(clean)
    med = s[len(s) // 2] if len(s) % 2 else (s[len(s)//2 - 1] + s[len(s)//2]) / 2
    devs = sorted(abs(v - med) for v in clean)
    n = len(devs)
    mad = devs[n // 2] if n % 2 else (devs[n//2 - 1] + devs[n//2]) / 2
    if mad == 0:
        return []  # constant series: nothing to flag
    return [_issue("outlier", field,
                   f"value {v} deviates > {mad_threshold} robust MADs from median {med}",
                   "warning", v)
            for v in clean if abs(v - med) > mad_threshold * mad]


def check_share_counts(basic: float, diluted: float) -> list:
    if basic is None or diluted is None:
        return []
    if diluted < basic:
        return [_issue("share_count_inconsistency", "shares",
                       f"diluted ({diluted}) < basic ({basic}); impossible", "error")]
    if basic > 0 and (diluted - basic) / basic > 0.20:
        return [_issue("share_count_inconsistency", "shares",
                       f"dilution gap {(diluted-basic)/basic:.0%} > 20%: verify "
                       "dilution methodology", "warning")]
    return []


def check_staleness(last_period_end_days_ago: float, limit_days: int = 550) -> Issue:
    if last_period_end_days_ago is None:
        return _issue("stale_data", "period_end", "no statement period available",
                      "warning")
    if last_period_end_days_ago > limit_days:
        return _issue("stale_data", "period_end",
                      f"latest statement is {int(last_period_end_days_ago)} days old "
                      f"(> {limit_days})", "warning", last_period_end_days_ago)
    return None


def validate(value, field: str, *, required: bool = True, provenance: str = None,
             plausible: tuple = None, allow_negative: bool = True) -> list:
    """Convenience composite validator for a single field."""
    issues = []
    if provenance:
        i = check_provenance(provenance, field)
        if i:
            issues.append(i)
    if required:
        i = check_required(value, field)
        if i:
            issues.append(i)
            return issues
    if value is not None and math.isfinite(value):
        if not allow_negative:
            i = check_negative(value, field)
            if i:
                issues.append(i)
        if plausible:
            i = check_magnitude(value, field, *plausible)
            if i:
                issues.append(i)
    return issues
