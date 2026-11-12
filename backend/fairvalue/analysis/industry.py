"""Industry-specific calculation rules.

Sector/industry context changes which metrics are *meaningful*: suppressing an
inapplicable metric with an explanatory note is the correct behavior — printing
a number nobody should use is not (spec §6: "Do not force irrelevant metrics
onto every company"). All rules are pure functions over shared schemas.
"""

from __future__ import annotations

from fairvalue.core.schemas import CompanyProfile, HealthMetrics, RiskAssessment, ValuationMultiples

FINANCIAL_KEYWORDS = ("bank", "insurance", "credit", "financial", "savings", "investment trust")
REIT_KEYWORDS = ("reit", "real estate investment")
SECTOR_FINANCIAL = "finance"


def _text(company: CompanyProfile) -> str:
    return f"{company.sector or ''} {company.industry or ''}".lower()


def is_financial(company: CompanyProfile) -> bool:
    t = _text(company)
    return SECTOR_FINANCIAL in t or any(k in t for k in FINANCIAL_KEYWORDS)


def is_reit(company: CompanyProfile) -> bool:
    return any(k in _text(company) for k in REIT_KEYWORDS)


def apply_industry_rules(
    company: CompanyProfile,
    health: HealthMetrics,
    multiples: ValuationMultiples,
    risks: RiskAssessment,
) -> tuple[HealthMetrics, ValuationMultiples, RiskAssessment]:
    """Adjust the three analysis results for sector context (returns new models)."""
    if not company.sector and not company.industry:
        health.notes.append("industry rules not applied: sector/industry unknown for this company")
        return health, multiples, risks

    if is_financial(company):
        if health.debt_to_ebitda is not None or health.net_debt_to_ebitda is not None:
            health.notes.append(
                "financial firm: debt/EBITDA suppressed — debt is the raw material of a bank's business, "
                "not leverage in the industrial sense (sector-standard capital ratios are not in the "
                "canonical concept set)"
            )
        health.debt_to_ebitda = None
        health.net_debt_to_ebitda = None
        if health.roic is not None:
            health.notes.append(
                "ROIC shown for a financial firm is computed from the same canonical concepts; "
                "interpret alongside sector capital-adequacy measures, not industrial peers"
            )
        if multiples.ev_ebitda is not None or multiples.ev_fcf is not None:
            multiples.notes.append("financial firm: EV-based multiples suppressed (enterprise value is ill-defined for banks)")
        multiples.ev_ebitda = None
        multiples.ev_fcf = None
        multiples.fcf_yield = None
        if risks.altman_zone is not None:
            risks.flags = [f for f in risks.flags if "Altman" not in f]
            risks.data_gaps.append("Altman Z suppressed: the model is not calibrated for financial firms")
            risks.altman_z = None
            risks.altman_zone = None
        risks.leverage_notes.append(
            "financial-sector leverage rules active: use equity/assets and regulatory capital ratios instead"
        )

    if is_reit(company):
        health.notes.append(
            "REIT context: FFO/AFFO are the sector-standard earnings measures; the free-cash-flow figures "
            "here are GAAP-based and typically depressed by property capex"
        )

    if risks.altman_zone is not None:
        mfg = "manufactur" in _text(company)
        if not mfg:
            risks.data_gaps.append(
                "Altman Z was calibrated on manufacturers — treat the zone as an indicative screen only"
            )

    return health, multiples, risks
