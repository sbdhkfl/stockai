"""Valuation multiples — computed from price + reported fundamentals only."""

from __future__ import annotations

from fairvalue.core.schemas import ValuationMultiples, ValuationInputs
from fairvalue.valuation.base import hist_cagr


def compute_multiples(iv: ValuationInputs) -> ValuationMultiples:
    notes: list[str] = []
    price = iv.price
    mcap = None
    ev = None
    if price is not None and iv.shares_outstanding:
        mcap = price * iv.shares_outstanding
    if mcap is not None and iv.net_debt is not None:
        ev = mcap + iv.net_debt

    pe = price / iv.eps if price is not None and iv.eps and iv.eps > 0 else None
    ps = mcap / iv.revenue if mcap and iv.revenue else None
    pb = mcap / iv.book_equity if mcap and iv.book_equity else None
    ev_ebitda = ev / iv.ebitda if ev is not None and iv.ebitda else None
    ev_fcf = ev / iv.fcf if ev is not None and iv.fcf else None
    fcf_yield = iv.fcf / mcap if mcap and iv.fcf is not None else None

    eps_growth = hist_cagr(iv.concept_history("eps_diluted"))
    peg = pe / (eps_growth * 100) if pe is not None and eps_growth and eps_growth > 0 else None

    if price is None:
        notes.append("market price unavailable — price-based multiples (P/E, P/S, P/B, PEG) not computed")
    if iv.eps is None:
        notes.append("EPS missing — P/E and PEG not computed")
    if eps_growth is None:
        notes.append("EPS CAGR undefined (needs ≥2 positive years) — PEG not computed")
    notes.append(
        "forward P/E requires analyst estimates, which this engine does not fabricate — reported as unavailable "
        "unless an estimates feed is configured"
    )

    return ValuationMultiples(
        pe=pe,
        forward_pe=None,
        peg=peg,
        ps=ps,
        pb=pb,
        ev_ebitda=ev_ebitda,
        ev_fcf=ev_fcf,
        fcf_yield=fcf_yield,
        notes=notes,
    )
