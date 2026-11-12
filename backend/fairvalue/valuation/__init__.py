"""Valuation model registry: name -> calculate(inputs, assumptions).

Each model is a pure function with its own validated assumptions type. The
reconciliation layer lives in ``reconcile.py`` and is deliberately separate.
"""

from __future__ import annotations

from pydantic import BaseModel

from fairvalue.core.schemas import (
    AssetBasedAssumptions,
    ComparablesAssumptions,
    DcfAssumptions,
    DdmAssumptions,
    EpvAssumptions,
    GrahamAssumptions,
    ModelResult,
    PrecedentAssumptions,
    ResidualIncomeAssumptions,
    SotpAssumptions,
    ValuationInputs,
)
from fairvalue.valuation import (
    asset_based,
    comparables,
    dcf,
    ddm,
    epv,
    graham,
    precedents,
    residual_income,
    sotp,
)
from fairvalue.valuation.base import MODEL_NAMES
from fairvalue.valuation.reconcile import MODEL_FAMILIES, reconcile

MODEL_REGISTRY: dict[str, tuple] = {
    "dcf": (dcf.calculate, DcfAssumptions),
    "ddm": (ddm.calculate, DdmAssumptions),
    "comparables": (comparables.calculate, ComparablesAssumptions),
    "precedents": (precedents.calculate, PrecedentAssumptions),
    "residual_income": (residual_income.calculate, ResidualIncomeAssumptions),
    "epv": (epv.calculate, EpvAssumptions),
    "graham": (graham.calculate, GrahamAssumptions),
    "asset_based": (asset_based.calculate, AssetBasedAssumptions),
    "sotp": (sotp.calculate, SotpAssumptions),
}


def run_models(inputs: ValuationInputs, assumptions: dict[str, BaseModel]) -> list[ModelResult]:
    """Run the selected models in stable report order.

    ``assumptions`` maps model name -> that model's validated assumptions object;
    models absent from the map are skipped (caller decides the selection).
    Invalid assumption objects raise pydantic errors at construction time — the
    API validates them before this point.
    """
    results: list[ModelResult] = []
    for name in MODEL_NAMES:
        if name not in assumptions:
            continue
        calc, _cls = MODEL_REGISTRY[name]
        results.append(calc(inputs, assumptions[name]))
    return results


__all__ = [
    "MODEL_NAMES",
    "MODEL_REGISTRY",
    "MODEL_FAMILIES",
    "run_models",
    "reconcile",
]
