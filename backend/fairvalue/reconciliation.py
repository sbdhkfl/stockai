"""Model reconciliation (docs/SCENARIO_ANALYSIS.md §interpretation, master §8).

Never averages every model blindly:
1. filter by suitability, 2. require data completeness, 3. flag outliers vs median
(robust MAD), 4. explain spread, 5. emit a defensible range + confidence.

Confidence here is a structured judgment over data quality, model suitability and
assumption uncertainty — explicitly NOT a statistically calibrated probability.
"""
from dataclasses import dataclass
import math
import statistics
from .errors import FairValueError


@dataclass(frozen=True)
class ModelOutput:
    model: str
    value_per_share: float
    suitable: bool = True
    data_completeness: float = 1.0   # 0..1 share of required inputs present
    notes: str = ""


def _median(xs):
    return statistics.median(xs)


def _mad(xs, med):
    devs = sorted(abs(x - med) for x in xs)
    n = len(devs)
    return devs[n // 2] if n % 2 else (devs[n//2-1] + devs[n//2]) / 2


def reconcile(outputs: list, market_price: float = None,
              outlier_mads: float = 2.5) -> dict:
    if not outputs:
        raise FairValueError("no model outputs provided")
    suitable = [o for o in outputs if o.suitable
                and math.isfinite(o.value_per_share) and o.data_completeness >= 0.7]
    if not suitable:
        raise FairValueError("no suitable, sufficiently complete model outputs; "
                             "cannot produce a defensible valuation")

    values = [o.value_per_share for o in suitable]
    med = _median(values)
    mad = _mad(values, med)
    outliers, core = [], []
    for o in suitable:
        if mad > 0 and abs(o.value_per_share - med) > outlier_mads * mad:
            outliers.append({"model": o.model, "value": o.value_per_share,
                             "reason": f"> {outlier_mads} robust MADs from median"})
        else:
            core.append(o)

    core_values = [o.value_per_share for o in core] or values
    core_values.sort()
    lo, hi = core_values[0], core_values[-1]

    # Explain the spread rather than hide it.
    spread_pct = (hi - lo) / abs(med) if med != 0 else None

    # Confidence: data quality x suitability x assumption agreement.
    mean_completeness = sum(o.data_completeness for o in core) / len(core)
    if len(core) >= 3 and spread_pct is not None and spread_pct < 0.35:
        agreement = "high"
    elif spread_pct is not None and spread_pct < 0.75:
        agreement = "moderate"
    else:
        agreement = "low"
    confidence = {
        "data_completeness": round(mean_completeness, 3),
        "model_agreement": agreement,
        "caveat": "structured judgment over data quality, model suitability and "
                  "assumption uncertainty; NOT a statistically calibrated probability",
    }
    if market_price is not None and lo <= market_price <= hi:
        confidence["market_price_within_range"] = True

    return {
        "fair_value_range": [lo, hi],
        "median": med,
        "models_used": [o.model for o in core],
        "outliers_excluded": outliers,
        "spread_pct": None if spread_pct is None else round(spread_pct, 4),
        "confidence": confidence,
        "explanation": (
            f"{len(core)} suitable models agree within "
            f"{round(spread_pct*100, 1) if spread_pct is not None else 'n/a'}% "
            f"(median {round(med, 2)}); {len(outliers)} outlier(s) excluded and "
            "reported for investigation, not silently dropped"),
    }
