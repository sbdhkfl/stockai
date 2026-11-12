"""Precedent Transactions — acquisition multiples of past M&A deals.

Formula
-------
multiple = statistic(EV_target / metric_target)  (× (1 + control premium))
EV  = multiple × company metric
Equity = EV − net debt ; value/share = Equity / shares
"""

from __future__ import annotations

from statistics import mean, median

from fairvalue.core.schemas import ModelResult, PrecedentAssumptions, ValuationInputs
from fairvalue.valuation.base import not_applicable

MODEL = "precedents"

LIMITATIONS = [
    "Deal multiples embed control premiums and the cycle in which each deal was announced.",
    "Targets differ in size/growth from the subject company; synergies are priced into the deal, not achievable standalone.",
    "Few disclosed transactions per sector make any statistic noisy — the count is reported with the result.",
]


def calculate(iv: ValuationInputs, a: PrecedentAssumptions) -> ModelResult:
    if not iv.transactions:
        return not_applicable(
            MODEL,
            "no transaction data source configured (precedent deals are not available from free feeds)",
            limitation=LIMITATIONS[0],
        )
    if not iv.shares_outstanding or iv.net_debt is None:
        return not_applicable(MODEL, "shares outstanding or net debt missing")

    metric_name = "ebitda" if a.multiple == "ev_ebitda" else "revenue"
    company_metric = iv.ebitda if a.multiple == "ev_ebitda" else iv.revenue
    if company_metric is None or company_metric <= 0:
        return not_applicable(MODEL, f"company {metric_name} missing or non-positive")

    multiples: list[float] = []
    steps: list[str] = []
    for t in iv.transactions:
        m_val = t.ebitda if a.multiple == "ev_ebitda" else t.revenue
        if t.enterprise_value is None or not m_val or m_val <= 0:
            steps.append(f"{t.target}: metric or EV missing — skipped")
            continue
        m = t.enterprise_value / m_val
        multiples.append(m)
        when = t.announced.isoformat() if t.announced else "date unknown"
        steps.append(f"{t.target} ({when}): EV {t.enterprise_value:,.0f} / {metric_name} {m_val:,.0f} = {m:.1f}x")

    if len(multiples) < a.min_transactions:
        return not_applicable(
            MODEL,
            f"only {len(multiples)} usable transaction(s), need {a.min_transactions}",
            limitation=LIMITATIONS[2],
        )

    stat = median if a.statistic == "median" else mean
    m = float(stat(multiples)) * (1 + a.control_premium)
    ev = m * company_metric
    equity = ev - iv.net_debt
    value = equity / float(iv.shares_outstanding)

    steps.append(f"{a.statistic} multiple {m:.1f}x{' incl. control premium' if a.control_premium else ''}")
    steps.append(
        f"EV {ev:,.0f} − net debt {iv.net_debt:,.0f} = equity {equity:,.0f} ÷ "
        f"{iv.shares_outstanding:,.0f} shares = {value:,.2f}/share"
    )

    years = [t.announced.year for t in iv.transactions if t.announced]
    warnings = []
    if years and max(years) < 2020:
        warnings.append(f"newest transaction announced {max(years)} — multiples may be stale vs today's cycle")

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        enterprise_value=ev,
        equity_value=equity,
        confidence="medium" if len(multiples) >= 3 else "low",
        suitability=min(1.0, 0.45 + 0.08 * len(multiples)),
        assumptions=a.model_dump(),
        formula="value/share = [statistic(deal EV/metric)·(1+premium)·company metric − net debt] / shares",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
