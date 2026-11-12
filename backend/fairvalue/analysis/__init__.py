"""Analytical modules: financial health, multiples, growth, risk, scenarios.

All functions are pure and return ``None`` for values that cannot be computed
from reported data — gaps are surfaced, never filled (ARCHITECTURE.md §4).
"""

from __future__ import annotations

from fairvalue.analysis.health import compute_health
from fairvalue.analysis.multiples import compute_multiples
from fairvalue.analysis.growth import compute_growth
from fairvalue.analysis.risk import compute_risks
from fairvalue.analysis.scenario import run_scenarios, sensitivity_grid

__all__ = [
    "compute_health",
    "compute_multiples",
    "compute_growth",
    "compute_risks",
    "run_scenarios",
    "sensitivity_grid",
]
