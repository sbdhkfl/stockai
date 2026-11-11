"""Scenario engine and sensitivity grids (docs/SCENARIO_ANALYSIS.md).

Bear/base/bull deltas move together for internal consistency; terminal growth is
re-clamped to WACC - 50bp after WACC shifts, and the clamp is recorded.
"""
from dataclasses import dataclass
from ..valuation.dcf import dcf_fcff
from ..errors import FairValueError


@dataclass(frozen=True)
class DCFInputs:
    fcff: list
    wacc: float
    terminal_growth: float
    net_debt: float
    diluted_shares: float


SCENARIOS = {
    "bear": {"fcff_factor": 0.70, "g_delta": -0.010, "wacc_delta": +0.015,
             "net_debt_factor": 1.10},
    "base": {"fcff_factor": 1.00, "g_delta": 0.000, "wacc_delta": 0.000,
             "net_debt_factor": 1.00},
    "bull": {"fcff_factor": 1.25, "g_delta": +0.005, "wacc_delta": -0.010,
             "net_debt_factor": 1.00},
}

MIN_G_MARGIN = 0.005  # keep g at least 50bp below WACC


def apply_scenario(inputs: DCFInputs, scenario: str) -> DCFInputs:
    if scenario not in SCENARIOS:
        raise FairValueError(f"unknown scenario '{scenario}'; use {list(SCENARIOS)}")
    s = SCENARIOS[scenario]
    fcff = [f * s["fcff_factor"] for f in inputs.fcff]
    wacc = inputs.wacc + s["wacc_delta"]
    g = inputs.terminal_growth + s["g_delta"]
    clamped = None
    if g >= wacc - MIN_G_MARGIN:
        g = wacc - MIN_G_MARGIN
        clamped = g
    if g < -0.02:  # sanity floor: perpetual decline beyond -2%/yr is implausible
        raise FairValueError("scenario produces implausible terminal growth < -2%")
    return DCFInputs(fcff=fcff, wacc=wacc, terminal_growth=g,
                     net_debt=inputs.net_debt * s["net_debt_factor"],
                     diluted_shares=inputs.diluted_shares), clamped


def run_scenario(inputs: DCFInputs, scenario: str) -> dict:
    adjusted, clamped = apply_scenario(inputs, scenario)
    r = dcf_fcff(adjusted.fcff, adjusted.wacc, adjusted.terminal_growth,
                 adjusted.net_debt, adjusted.diluted_shares)
    return {"scenario": scenario, "value_per_share": r.value_per_share,
            "equity_value": r.equity_value,
            "terminal_growth_clamped_to": clamped,
            "assumptions_used": {"wacc": adjusted.wacc,
                                 "terminal_growth": adjusted.terminal_growth,
                                 "net_debt": adjusted.net_debt}}


def run_all_scenarios(inputs: DCFInputs) -> dict:
    return {name: run_scenario(inputs, name) for name in ("bear", "base", "bull")}


def sensitivity_grid(inputs: DCFInputs, wacc_range: list, g_range: list) -> dict:
    """Per-share value across WACC x terminal-growth grid. Base inputs otherwise."""
    if not wacc_range or not g_range:
        raise FairValueError("sensitivity ranges must be non-empty")
    grid = {}
    for w in wacc_range:
        row = {}
        for g in g_range:
            if g >= w:
                row[round(g, 6)] = None  # Gordon undefined; recorded as None, not faked
                continue
            r = dcf_fcff(inputs.fcff, w, g, inputs.net_debt, inputs.diluted_shares)
            row[round(g, 6)] = r.value_per_share
        grid[round(w, 6)] = row
    return {"grid": grid, "rows": "wacc", "cols": "terminal_growth",
            "note": "value decreases with WACC and increases with terminal growth; "
                    "this grid is conditional on all other base assumptions"}
