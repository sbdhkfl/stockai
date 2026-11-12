"""Sum-of-the-Parts — value each business segment, then aggregate.

Formula
-------
each segment: metric × segment multiple  (EBITDA × EV/EBITDA, or revenue × EV/Sales)
EV = Σ segment values ; Equity = EV − net debt  (equity-multiple segments aggregate directly)
value/share = Equity / shares

Every segment must carry a multiple (assumption map or the segment's own
configured multiple); a segment without one makes the model inapplicable —
silently dropping it would understate value.
"""

from __future__ import annotations

from fairvalue.core.schemas import ModelResult, SotpAssumptions, ValuationInputs
from fairvalue.valuation.base import not_applicable

MODEL = "sotp"

LIMITATIONS = [
    "Requires segment-level data that public feeds do not provide; it is only available when segments are supplied.",
    "Segment multiples must reflect each unit's own growth and margins — a single wrong multiple distorts the sum.",
    "No synergy or corporate-cost (overhead) discount is applied unless the caller includes it in the inputs.",
]


def calculate(iv: ValuationInputs, a: SotpAssumptions) -> ModelResult:
    if not iv.segments:
        return not_applicable(
            MODEL,
            "no segment data supplied (segment reporting is not available from free feeds)",
            limitation=LIMITATIONS[0],
        )
    if not iv.shares_outstanding:
        return not_applicable(MODEL, "shares outstanding missing")

    needed_metric = "ebitda" if a.multiple_metric == "ev_ebitda" else "revenue"
    wrong = [s.name for s in iv.segments if s.metric != needed_metric]
    if wrong:
        return not_applicable(
            MODEL,
            f"multiple_metric={a.multiple_metric} requires segment metric '{needed_metric}'; "
            f"mismatched segment(s): {', '.join(wrong)}",
        )

    missing_mult = [s.name for s in iv.segments if a.segment_multiples.get(s.name, s.multiple) is None]
    if missing_mult:
        return not_applicable(MODEL, f"missing multiple for segment(s): {', '.join(missing_mult)}")

    steps: list[str] = [f"{len(iv.segments)} segments, metric {needed_metric} × {a.multiple_metric} multiple:"]
    ev_total = 0.0
    for s in iv.segments:
        mult = float(a.segment_multiples.get(s.name, s.multiple))
        part = s.value * mult
        ev_total += part
        steps.append(f"  {s.name}: {s.metric} {s.value:,.0f} × {mult:.1f}x = {part:,.0f}")

    if iv.net_debt is None:
        return not_applicable(MODEL, "net debt missing — cannot bridge summed EV to equity")

    equity = ev_total - iv.net_debt
    value = equity / float(iv.shares_outstanding)
    steps.append(
        f"Σ segment EV {ev_total:,.0f} − net debt {iv.net_debt:,.0f} = equity {equity:,.0f} ÷ "
        f"{iv.shares_outstanding:,.0f} = {value:,.2f}/share"
    )

    largest = max(s.value for s in iv.segments)
    total = sum(s.value for s in iv.segments)
    warnings = []
    if total and largest / total > 0.7:
        warnings.append("one segment is >70% of the sum — SOTP adds little over a whole-company multiple")

    return ModelResult(
        model=MODEL,
        applicable=True,
        value_per_share=value,
        enterprise_value=ev_total,
        equity_value=equity,
        confidence="medium",
        suitability=0.7 if len(iv.segments) >= 2 else 0.5,
        assumptions=a.model_dump(),
        formula="equity = Σ(segment metric × multiple) − net debt",
        steps=steps,
        limitations=LIMITATIONS,
        warnings=warnings,
    )
