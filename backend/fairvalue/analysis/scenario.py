"""Scenario engine: bear / base / bull DCF cases + WACC × terminal-growth
sensitivity grid.

Scenarios are *documented shifts of the base assumption set* — every applied
value is echoed in ``ScenarioResult.applied_assumptions`` so the report can be
reproduced exactly. Model outputs are never altered without a recalculation.
"""

from __future__ import annotations

from fairvalue.core.schemas import DcfAssumptions, ScenarioResult, ScenarioSet, ScenarioSpec, SensitivityPoint, ValuationInputs
from fairvalue.valuation import dcf as dcf_model

BEAR = ScenarioSpec(
    name="bear",
    revenue_growth_multiplier=0.5,
    operating_margin_delta=-0.03,
    wacc_delta=0.015,
    terminal_growth_delta=-0.005,
    capex_pct_delta=0.01,
    nwc_pct_delta=0.02,
    annual_share_growth_delta=0.01,
)
BULL = ScenarioSpec(
    name="bull",
    revenue_growth_multiplier=1.4,
    operating_margin_delta=0.03,
    wacc_delta=-0.005,
    terminal_growth_delta=0.005,
    capex_pct_delta=-0.005,
    nwc_pct_delta=-0.01,
)


def apply_spec(base: DcfAssumptions, spec: ScenarioSpec) -> DcfAssumptions:
    """Shift the base DCF assumptions; terminal growth is clamped below WACC so
    every scenario stays financially valid (a warning notes the clamp)."""
    kw = base.model_dump()
    kw["revenue_growth"] = min(1.0, max(-0.5, (base.revenue_growth + spec.revenue_growth_delta) * spec.revenue_growth_multiplier))
    if base.target_operating_margin is not None:
        kw["target_operating_margin"] = min(1.0, max(-1.0, base.target_operating_margin + spec.operating_margin_delta))
    kw["wacc"] = min(0.99, max(0.005, base.wacc + spec.wacc_delta))
    kw["terminal_growth"] = base.terminal_growth + spec.terminal_growth_delta
    if kw["terminal_method"] == "gordon":
        kw["terminal_growth"] = min(kw["terminal_growth"], kw["wacc"] - 0.005)
    if base.capex_pct_revenue is not None:
        kw["capex_pct_revenue"] = max(0.0, base.capex_pct_revenue + spec.capex_pct_delta)
    kw["nwc_pct_revenue_change"] = base.nwc_pct_revenue_change + spec.nwc_pct_delta
    kw["annual_share_growth"] = base.annual_share_growth + spec.annual_share_growth_delta
    if kw["terminal_method"] == "exit_multiple" and spec.wacc_delta == 0 and spec.terminal_growth_delta == 0:
        pass  # exit-multiple terminal unaffected by growth shifts
    return DcfAssumptions(**kw)


def _scenario(iv: ValuationInputs, base: DcfAssumptions, spec: ScenarioSpec) -> ScenarioResult:
    a = apply_spec(base, spec)
    result = dcf_model.calculate(iv, a)
    notes: list[str] = []
    if not result.applicable:
        notes.append(f"DCF not runnable: {result.excluded_reason}")
    return ScenarioResult(
        name=spec.name,
        value_per_share=result.value_per_share if result.applicable else None,
        applied_assumptions=a.model_dump(),
        notes=notes + result.warnings[:1],
    )


def run_scenarios(
    iv: ValuationInputs, base: DcfAssumptions, *, bear: ScenarioSpec = BEAR, bull: ScenarioSpec = BULL
) -> ScenarioSet:
    return ScenarioSet(
        bear=_scenario(iv, base, bear),
        base=_scenario(iv, base, ScenarioSpec(name="base")),
        bull=_scenario(iv, base, bull),
        sensitivity=sensitivity_grid(iv, base),
    )


def sensitivity_grid(
    iv: ValuationInputs, base: DcfAssumptions, *, wacc_steps: int = 5, g_steps: int = 5
) -> list[SensitivityPoint]:
    """DCF value/share for WACC ±1pp (rows) × terminal growth ±0.5pp (columns)."""
    points: list[SensitivityPoint] = []
    for i in range(wacc_steps):
        wacc = base.wacc + (i - (wacc_steps - 1) / 2) * 0.005
        for j in range(g_steps):
            g = base.terminal_growth + (j - (g_steps - 1) / 2) * 0.0025
            kw = base.model_dump()
            kw["wacc"] = wacc
            kw["annual_share_growth"] = kw["annual_share_growth"]  # unchanged
            if kw["terminal_method"] == "gordon":
                g = min(g, wacc - 0.0025)
                kw["terminal_growth"] = g
                if g <= -0.05:
                    points.append(SensitivityPoint(wacc=wacc, terminal_growth=g, value_per_share=None))
                    continue
            else:
                kw["terminal_growth"] = g  # unused by exit-multiple method
            try:
                res = dcf_model.calculate(iv, DcfAssumptions(**kw))
            except ValueError:
                points.append(SensitivityPoint(wacc=wacc, terminal_growth=g, value_per_share=None))
                continue
            points.append(
                SensitivityPoint(
                    wacc=wacc, terminal_growth=g,
                    value_per_share=res.value_per_share if res.applicable else None,
                )
            )
    return points
