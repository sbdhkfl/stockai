"""Discounted Cash Flow — free cash flow to the firm (FCFF).

Formula
-------
FCF_t = EBIT_t · (1 − tax) + D&A_t − Capex_t − ΔNWC_t
EV    = Σ_t FCF_t / (1+WACC)^t  +  TV / (1+WACC)^n
TV    = FCF_n·(1+g)/(WACC−g)          (Gordon, g < WACC)
      | EBITDA_n · exit_EV/EBITDA      (exit multiple)
Equity = EV − net debt ;  value/share = Equity / shares
"""

from __future__ import annotations

from fairvalue.core.schemas import DcfAssumptions, ModelResult, ValuationInputs
from fairvalue.valuation.base import historical_rates, not_applicable

MODEL = "dcf"

LIMITATIONS = [
    "Terminal value dominates when WACC − terminal growth is small; the range is highly sensitive to both.",
    "Assumes forecast margins/capex intensity persist; it is not a forecast of the company's actual plans.",
    "Net debt and share count use the latest reported balance sheet, not market-consensus adjustments.",
]


def calculate(iv: ValuationInputs, a: DcfAssumptions) -> ModelResult:
    # Deferred import: analysis.industry pulls the analysis package, which
    # imports valuation modules — cycle only if done at module load.
    from fairvalue.analysis.industry import is_financial

    if is_financial(iv.company):
        return not_applicable(
            MODEL,
            "DCF(FCFF) is not suitable for financial firms: interest is operating, "
            "not a financing cost — use residual income or DDM",
        )
    if iv.revenue is None or iv.ebit is None:
        return not_applicable(MODEL, "revenue/ebit missing from latest reported period")
    if not iv.shares_outstanding or iv.shares_outstanding <= 0:
        return not_applicable(MODEL, "shares outstanding missing")
    if iv.net_debt is None:
        return not_applicable(MODEL, "net debt unknown (cash and/or total debt missing)")

    rev0 = iv.revenue
    margin = a.target_operating_margin if a.target_operating_margin is not None else iv.ebit / rev0

    if a.capex_pct_revenue is not None:
        capex_pct = a.capex_pct_revenue
    else:
        hist = historical_rates(iv, "capex", "revenue")
        if not hist:
            return not_applicable(MODEL, "capex/revenue history unavailable and capex_pct_revenue not set")
        capex_pct = sum(hist) / len(hist)

    if a.depreciation_pct_revenue is not None:
        dep_pct = a.depreciation_pct_revenue
    else:
        dep_hist = historical_rates(iv, "depreciation_amortization", "revenue")
        dep_pct = sum(dep_hist) / len(dep_hist) if dep_hist else capex_pct  # stated fallback assumption

    steps: list[str] = [
        f"Base revenue {rev0:,.0f}; operating margin {margin:.1%} "
        f"({'assumed target' if a.target_operating_margin is not None else 'latest reported'}); "
        f"tax {a.tax_rate:.0%}; capex {capex_pct:.1%} of revenue; D&A {dep_pct:.1%} of revenue; "
        f"ΔNWC {a.nwc_pct_revenue_change:.1%} of revenue change.",
        f"Revenue growth {a.revenue_growth:+.1%}/yr for {a.forecast_years} years; WACC {a.wacc:.2%}; "
        f"terminal: {a.terminal_method}"
        + (f" @ {a.exit_ev_ebitda:.1f}x" if a.terminal_method == "exit_multiple" else f", g={a.terminal_growth:.2%}"),
    ]

    pv_sum = 0.0
    prev_rev = rev0
    last_fcf = 0.0
    last_ebitda = 0.0
    for t in range(1, a.forecast_years + 1):
        rev = prev_rev * (1 + a.revenue_growth)
        ebit = rev * margin
        nopat = ebit * (1 - a.tax_rate)
        da = rev * dep_pct
        capex = rev * capex_pct
        dnwc = (rev - prev_rev) * a.nwc_pct_revenue_change
        fcf = nopat + da - capex - dnwc
        pv = fcf / (1 + a.wacc) ** t
        pv_sum += pv
        last_fcf, last_ebitda = fcf, ebit + da
        steps.append(
            f"Y{t}: revenue {rev:,.0f} → EBIT {ebit:,.0f} → NOPAT {nopat:,.0f}; "
            f"+D&A {da:,.0f} −capex {capex:,.0f} −ΔNWC {dnwc:,.0f} = FCF {fcf:,.0f} "
            f"(PV {pv:,.0f} @ {a.wacc:.2%})"
        )
        prev_rev = rev

    if a.terminal_method == "gordon":
        tv = last_fcf * (1 + a.terminal_growth) / (a.wacc - a.terminal_growth)
        steps.append(
            f"Terminal (Gordon): {last_fcf:,.0f}·(1+{a.terminal_growth:.2%})/({a.wacc:.2%}−{a.terminal_growth:.2%}) = {tv:,.0f}"
        )
    else:
        tv = last_ebitda * float(a.exit_ev_ebitda)
        steps.append(f"Terminal (exit multiple): EBITDA {last_ebitda:,.0f} × {a.exit_ev_ebitda:.1f} = {tv:,.0f}")

    tv_pv = tv / (1 + a.wacc) ** a.forecast_years
    ev = pv_sum + tv_pv
    equity = ev - (iv.net_debt or 0.0)
    shares = iv.shares_outstanding
    if a.annual_share_growth:
        shares = shares * (1 + a.annual_share_growth) ** a.forecast_years
    value = equity / shares

    steps.append(
        f"PV(FCF 1..{a.forecast_years}) {pv_sum:,.0f} + PV(terminal) {tv_pv:,.0f} = EV {ev:,.0f}; "
        f"− net debt {iv.net_debt:,.0f} = equity {equity:,.0f} ÷ {shares:,.0f} shares = {value:,.2f}/share"
    )

    warnings: list[str] = []
    tv_share = tv_pv / ev if ev else 0.0
    if tv_share > 0.75:
        warnings.append(f"terminal value is {tv_share:.0%} of EV — result dominated by the terminal assumption")
    if a.terminal_method == "gordon" and a.wacc - a.terminal_growth < 0.02:
        warnings.append("WACC − terminal growth < 2pp: Gordon terminal is unstable here")
    if margin < 0:
        warnings.append("negative operating margin: DCF assumes margins recover to the target")
    if a.annual_share_growth:
        warnings.append("dilution applies the end-of-forecast share count to the whole equity value (conservative)")

    suitability = 0.7
    if len(iv.history) >= 3:
        suitability += 0.15
    if iv.fcf is not None and iv.fcf > 0:
        suitability += 0.1
    if len(iv.history) < 3:
        suitability -= 0.2

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        enterprise_value=ev,
        equity_value=equity,
        confidence="high" if len(iv.history) >= 5 and iv.fcf and iv.fcf > 0 else "medium",
        suitability=max(0.1, min(1.0, suitability)),
        assumptions=a.model_dump(),
        formula="EV = Σ FCFF_t/(1+WACC)^t + TV/(1+WACC)^n; equity = EV − net debt",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
