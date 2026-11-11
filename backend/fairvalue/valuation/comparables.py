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

# ---------------------------------------------------------------------------
# Contract adapter: ValuationInputs -> ModelResult
# ---------------------------------------------------------------------------
from ..core.schemas import ValuationInputs, ComparablesAssumptions, ModelResult


def _peer_multiple(peer, kind):
    if kind == "ev_ebitda":
        return peer.enterprise_value / peer.ebitda if peer.enterprise_value and peer.ebitda and peer.ebitda > 0 else None
    if kind == "ev_sales":
        return peer.enterprise_value / peer.revenue if peer.enterprise_value and peer.revenue and peer.revenue > 0 else None
    if kind == "pe":
        if peer.price and peer.shares_outstanding and peer.net_income and peer.net_income > 0:
            return (peer.price * peer.shares_outstanding) / peer.net_income
        return None
    if kind == "pb":
        if peer.price and peer.shares_outstanding and peer.equity and peer.equity > 0:
            return (peer.price * peer.shares_outstanding) / peer.equity
        return None
    raise FairValueError(f"unknown multiple kind '{kind}'")


def run_model(inputs: ValuationInputs, a: ComparablesAssumptions) -> ModelResult:
    base = dict(assumptions=a.model_dump())
    if not inputs.peers:
        return ModelResult(model="comparables", applicable=False,
                           excluded_reason="no peer companies provided", **base)
    if not inputs.shares_outstanding:
        return ModelResult(model="comparables", applicable=False,
                           excluded_reason="shares outstanding missing", **base)
    latest = inputs.history[-1] if inputs.history else None
    results, steps, warnings = {}, [], []
    for kind in a.multiples:
        mults = [m for p in inputs.peers if (m := _peer_multiple(p, kind)) is not None]
        if len(mults) < a.min_peers:
            warnings.append(f"{kind}: only {len(mults)} usable peers (min {a.min_peers})")
            continue
        stat = statistics.median(mults) if a.statistic == "median" else statistics.mean(mults)
        # target metric: EV-level for ev_*, equity-level for pe/pb (level pairing rule)
        if kind == "ev_ebitda":
            target, level = inputs.ebitda, "EV"
        elif kind == "ev_sales":
            target, level = inputs.revenue, "EV"
        elif kind == "pe":
            target, level = inputs.eps, "equity"
        else:
            target, level = (inputs.book_equity / inputs.shares_outstanding
                             if inputs.book_equity else None), "equity"
        if not target or target <= 0:
            warnings.append(f"{kind}: target metric missing or <= 0 — skipped")
            continue
        implied = stat * target
        if level == "EV":
            implied_equity = implied - (inputs.net_debt or 0.0)
            per_share = implied_equity / inputs.shares_outstanding
            steps.append(f"{kind}: median {stat:.2f}x x target {target:,.0f} -> EV "
                         f"{implied:,.0f}; equity {implied_equity:,.0f}; "
                         f"{per_share:.2f}/share")
        else:
            per_share = implied
            steps.append(f"{kind}: median {stat:.2f}x x target {target:.2f} -> "
                         f"{per_share:.2f}/share (equity level, no bridge)")
        results[kind] = per_share
    if not results:
        return ModelResult(model="comparables", applicable=False,
                           excluded_reason="no multiple produced a usable value",
                           warnings=warnings, **base)
    vals = sorted(results.values())
    mid = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals)//2-1] + vals[len(vals)//2]) / 2
    steps.append(f"per-share estimates {', '.join(f'{k}: {v:.2f}' for k, v in results.items())}"
                 f" -> central {mid:.2f}")
    return ModelResult(model="comparables", applicable=True, value_per_share=mid,
                       **base,
                       formula="implied value = peer median multiple x target metric "
                               "(EV multiples bridged to equity via net debt)",
                       steps=steps, warnings=warnings,
                       limitations=["peer set quality dominates; sector/size screening "
                                    "happens upstream of this module"])
