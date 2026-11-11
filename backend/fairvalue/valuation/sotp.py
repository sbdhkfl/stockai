"""Sum-of-the-parts valuation.

value = sum(segment valuations) - net_debt - unallocated_corporate_costs.
Segments with missing disclosure are flagged and excluded; the result carries a
coverage ratio instead of silently extrapolating the missing piece.
"""
from dataclasses import dataclass
import math
from ..errors import FairValueError, NotMeaningfulError


@dataclass(frozen=True)
class Segment:
    name: str
    value: float          # already in EV or equity terms consistent across segments
    disclosed: bool = True


def sotp_value(segments: list, net_debt: float,
               unallocated_costs: float = 0.0) -> dict:
    if not segments:
        raise FairValueError("at least one segment required")
    if not (math.isfinite(net_debt) and math.isfinite(unallocated_costs)):
        raise FairValueError("sotp inputs must be finite")
    total = 0.0
    included = 0
    for s in segments:
        if not isinstance(s, Segment):
            raise FairValueError("segments must be Segment objects")
        if s.disclosed:
            if not math.isfinite(s.value):
                raise FairValueError(f"segment '{s.name}' value must be finite")
            total += s.value
            included += 1
    if included == 0:
        raise NotMeaningfulError("no segments disclosed: SOTP not computable")
    equity_value = total - net_debt - unallocated_costs
    return {"sotp_value": equity_value,
            "gross_segment_value": total,
            "coverage": included / len(segments),
            "excluded_segments": [s.name for s in segments if not s.disclosed]}

# ---------------------------------------------------------------------------
# Contract adapter: ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from statistics import median
from ..core.schemas import ValuationInputs, SotpAssumptions, ModelResult


def run_model(inputs: ValuationInputs, a: SotpAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    if not inputs.segments:
        return ModelResult(model="sotp", applicable=False,
                           excluded_reason="no segment disclosure", **base)
    if not inputs.shares_outstanding:
        return ModelResult(model="sotp", applicable=False,
                           excluded_reason="shares outstanding missing", **base)
    peer_mult = None
    if inputs.peers:
        ms = []
        for p in inputs.peers:
            key = "ebitda" if a.multiple_metric == "ev_ebitda" else "revenue"
            ev, m = p.enterprise_value, getattr(p, key)
            if ev and m and m > 0:
                ms.append(ev / m)
        peer_mult = median(ms) if ms else None
    total, warnings = 0.0, []
    for s in inputs.segments:
        m = a.segment_multiples.get(s.name) or peer_mult
        if not m:
            warnings.append(f"segment '{s.name}': no multiple available - excluded")
            continue
        total += s.value * m
    if total <= 0:
        return ModelResult(model="sotp", applicable=False,
                           excluded_reason="no segment could be valued", **base)
    equity = total - (inputs.net_debt or 0.0)
    steps = [f"sum of segment EVs = {total:,.0f}; equity = {equity:,.0f} after net debt "
             f"{inputs.net_debt or 0.0:,.0f}"]
    if peer_mult:
        steps.append(f"fallback peer median {a.multiple_metric} = {peer_mult:.2f}x "
                     "where segment multiples not supplied")
    return ModelResult(model="sotp", applicable=True,
                       value_per_share=equity / inputs.shares_outstanding,
                       enterprise_value=total, equity_value=equity,
                       **base,
                       formula="sum(segment metric x segment multiple) - net debt",
                       steps=steps, warnings=warnings,
                       limitations=["requires segment-level disclosure; conglomerate "
                                    "discount is not automatic"])
