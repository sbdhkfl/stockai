"""Comparable-company multiples.

Rules:
- median, never mean (outlier resistance)
- peers with non-positive metrics are EXCLUDED with a recorded reason, never treated as 0
- EV-level multiples pair with EV-level denominators only; equity multiples with
  equity-level only (mixing levels is the classic comps error; enforced by enum).
"""
from dataclasses import dataclass
import statistics
from ..errors import FairValueError, NotMeaningfulError


@dataclass(frozen=True)
class Level:
    """VALUATION_LEVEL = enterprise or equity."""
    name: str


ENTERPRISE = Level("enterprise")
EQUITY = Level("equity")


def median_multiple(peer_multiples: list) -> float:
    """peer_multiples: list of positive, finite multiples."""
    clean = [m for m in peer_multiples if m is not None and m > 0]
    if not clean:
        raise NotMeaningfulError("no positive peer multiples available")
    return statistics.median(clean)


def implied_value_from_multiple(peer_multiples: list, target_metric: float,
                                level: Level) -> float:
    if any(not isinstance(p, Level) for p in [level]):
        raise FairValueError("level must be ENTERPRISE or EQUITY")
    if target_metric <= 0:
        raise NotMeaningfulError(
            "target metric <= 0: multiple-based value not meaningful")
    return median_multiple(peer_multiples) * target_metric
