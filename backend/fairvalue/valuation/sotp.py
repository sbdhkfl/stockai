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
