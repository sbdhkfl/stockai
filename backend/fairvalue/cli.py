"""FAIRVALUE AI command-line interface.

Uses the SDK when ``--api-url`` is given (talks to a running REST API);
otherwise calls the financial engine directly (offline-capable with --demo).
No valuation logic lives here — the engine and service layer own the math.

Examples
--------
    python -m fairvalue.cli search "bank of"
    python -m fairvalue.cli company AAPL --demo
    python -m fairvalue.cli valuation AAPL --demo --text
    python -m fairvalue.cli health AAPL --demo
    python -m fairvalue.cli scenarios AAPL --demo
    python -m fairvalue.cli report r-abc123 --api-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from fairvalue.core.schemas import DcfAssumptions
from fairvalue.data import ProviderError, get_provider
from fairvalue.sdk import FairValueClient, SdkError
from fairvalue.service import ValuationOptions, run_valuation


def _client(args) -> FairValueClient:
    return FairValueClient(base_url=args.api_url,
                           api_key=args.api_key)


def _out(data: Any, text: bool = False):
    if not text:
        print(json.dumps(data, indent=2, default=str))
        return
    # compact human summaries for the two most common commands
    if isinstance(data, dict) and "models" in data and "reconciliation" in data:
        rec = data["reconciliation"]
        print(f"Company: {data['company'].get('name', data['company'].get('ticker'))}"
              f" ({data['company']['ticker']})")
        if data.get("is_illustrative"):
            print("WARNING: ILLUSTRATIVE DEMO DATA — not real filings")
        print(f"Fair-value range: {rec['low']:.2f} – {rec['high']:.2f}"
              f"  (base {rec['base']:.2f})" if rec.get("low") is not None else "No valuation range")
        print("Models:")
        for m in data["models"]:
            tag = "excluded" if not m.get("applicable") else f"{m['value_per_share']:.2f}/share"
            print(f"  {m['model']:<17} {tag}")
            if not m.get("applicable"):
                print(f"    reason: {m.get('excluded_reason')}")
        sc = data.get("scenarios")
        if sc:
            print(f"Scenarios (DCF): bear {sc['bear']['value_per_share']:.2f} | "
                  f"base {sc['base']['value_per_share']:.2f} | "
                  f"bull {sc['bull']['value_per_share']:.2f}")
        dq = data.get("data_quality", {})
        if dq.get("missing"):
            print(f"Missing data (reported, not filled): {', '.join(dq['missing'])}")
        print("Analysis only — not investment advice.")
    elif isinstance(data, dict) and "flags" in data:
        print(f"Altman Z: {data.get('altman_z')} ({data.get('altman_zone')})")
        for f in data.get("flags", []):
            print(f"  flag: {f}")
        for g in data.get("data_gaps", []):
            print(f"  data gap: {g}")
    else:
        print(json.dumps(data, indent=2, default=str))


def _direct(fn, ticker: str, demo: bool = False, *extra) -> Any:
    """Call the service layer directly (no HTTP); extra args forwarded after
    (provider, ticker)."""
    return fn(get_provider(demo=demo), ticker, *extra)


def cmd_valuation(args) -> int:
    if args.api_url:
        rep = _client(args).valuation(args.ticker, demo=args.demo)
        _out(rep.model_dump(), args.text)
        return 0
    try:
        rep = _direct(run_valuation, args.ticker, args.demo,
                      ValuationOptions(demo=args.demo, models=args.models))
    except ProviderError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    _out(rep.model_dump(), args.text)
    return 0


def _analysis(kind: str, args) -> int:
    if args.api_url:
        data = getattr(_client(args), kind)(args.ticker, demo=args.demo)
        _out(data.model_dump(), args.text)
        return 0
    from fairvalue.analysis import compute_health, compute_multiples, compute_risks
    try:
        from fairvalue.service import load_inputs
        loaded = load_inputs(get_provider(demo=args.demo), args.ticker,
                             ValuationOptions(demo=args.demo))
    except ProviderError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    if kind == "risks":
        _out(compute_risks(loaded.inputs).model_dump(), args.text)
    else:
        _out(compute_health(loaded.inputs).model_dump(), args.text)
    return 0


def cmd_health(args) -> int:
    return _analysis("health_metrics", args)


def cmd_risks(args) -> int:
    return _analysis("risks", args)


def cmd_company(args) -> int:
    if args.api_url:
        _out(_client(args).company(args.ticker, demo=args.demo).model_dump(), args.text)
        return 0
    from fairvalue.data.edgar import EdgarProvider
    from fairvalue.data import get_provider
    profiles = get_provider(demo=args.demo).search_company(args.ticker)
    exact = [p for p in profiles if p.ticker.upper() == args.ticker.upper()]
    if not exact:
        print(f"error: company '{args.ticker}' not found", file=sys.stderr)
        return 1
    _out(exact[0].model_dump(), args.text)
    return 0


def cmd_statements(args) -> int:
    if args.api_url:
        _out(_client(args).statements(args.ticker, demo=args.demo).model_dump(), args.text)
        return 0
    try:
        fund = _direct(lambda p, t: p.get_fundamentals(t), args.ticker, args.demo)
    except ProviderError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    _out(fund.model_dump(), args.text)
    return 0


def cmd_scenarios(args) -> int:
    if args.api_url:
        _out(_client(args).scenarios(args.ticker, demo=args.demo).model_dump(), args.text)
        return 0
    from fairvalue.analysis import run_scenarios
    from fairvalue.service import load_inputs
    try:
        loaded = load_inputs(get_provider(demo=args.demo), args.ticker,
                             ValuationOptions(demo=args.demo))
    except ProviderError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    w = args.wacc if args.wacc else loaded.rates.get("wacc")
    if w is None:
        print("error [assumption_missing]: no WACC derivable; pass --wacc",
              file=sys.stderr)
        return 2
    _out(run_scenarios(loaded.inputs, DcfAssumptions(wacc=w)).model_dump(), args.text)
    return 0


def cmd_report(args) -> int:
    if not args.api_url:
        print("error: 'report' requires a running API — pass --api-url", file=sys.stderr)
        return 2
    _out(_client(args).report(args.report_id).model_dump(), args.text)
    return 0


def cmd_explain(args) -> int:
    if args.api_url:
        _out(_client(args).explain(args.ticker, demo=args.demo).model_dump(), args.text)
        return 0
    try:
        rep = _direct(run_valuation, args.ticker, args.demo,
                      ValuationOptions(demo=args.demo))
    except ProviderError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    _out(rep.explanation.model_dump(), args.text)
    return 0


def cmd_search(args) -> int:
    if args.api_url:
        _out([c.model_dump() for c in _client(args).search(args.query, demo=args.demo)],
             args.text)
        return 0
    from fairvalue.service import search_companies
    _out([c.model_dump() for c in search_companies(args.query, demo=args.demo)], args.text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fairvalue",
                                description="FAIRVALUE AI — transparent stock valuation")
    # argparse gotcha: subparser defaults overwrite main-parser values even when
    # the flag is absent, so shared flags use SUPPRESS defaults and the top-level
    # parser (which also lists them) owns the defaults.
    # argparse gotcha: subparser defaults overwrite main-parser values even when
    # the flag is absent. Global flags therefore have REAL defaults on the main
    # parser and SUPPRESS defaults on the subparsers, so flags work both before
    # and after the subcommand ("fairvalue --demo risks X" and "risks X --demo").
    main_flags = argparse.ArgumentParser(add_help=False)
    main_flags.add_argument("--api-url", default=None,
                            help="talk to a running REST API instead of the local engine")
    main_flags.add_argument("--api-key", default=None,
                            help="X-API-Key when the API requires one")
    main_flags.add_argument("--demo", action="store_true", default=False,
                            help="use clearly-labeled illustrative demo data (offline)")
    main_flags.add_argument("--text", action="store_true", default=False,
                            help="human summary instead of JSON")
    sub_flags = argparse.ArgumentParser(add_help=False)
    sub_flags.add_argument("--api-url", default=argparse.SUPPRESS)
    sub_flags.add_argument("--api-key", default=argparse.SUPPRESS)
    sub_flags.add_argument("--demo", action="store_true", default=argparse.SUPPRESS)
    sub_flags.add_argument("--text", action="store_true", default=argparse.SUPPRESS)
    p = argparse.ArgumentParser(prog="fairvalue", parents=[main_flags],
                                description="FAIRVALUE AI — transparent stock valuation")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", parents=[sub_flags]); s.add_argument("query"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("company", parents=[sub_flags]); s.add_argument("ticker"); s.set_defaults(fn=cmd_company)
    s = sub.add_parser("statements", parents=[sub_flags]); s.add_argument("ticker"); s.set_defaults(fn=cmd_statements)
    s = sub.add_parser("valuation", parents=[sub_flags]); s.add_argument("ticker")
    s.add_argument("--models", nargs="*", default=None); s.set_defaults(fn=cmd_valuation)
    s = sub.add_parser("health", parents=[sub_flags]); s.add_argument("ticker"); s.set_defaults(fn=cmd_health)
    s = sub.add_parser("risks", parents=[sub_flags]); s.add_argument("ticker"); s.set_defaults(fn=cmd_risks)
    s = sub.add_parser("scenarios", parents=[sub_flags]); s.add_argument("ticker")
    s.add_argument("--wacc", type=float, default=None); s.set_defaults(fn=cmd_scenarios)
    s = sub.add_parser("report", parents=[sub_flags]); s.add_argument("report_id"); s.set_defaults(fn=cmd_report)
    s = sub.add_parser("explain", parents=[sub_flags]); s.add_argument("ticker"); s.set_defaults(fn=cmd_explain)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except SdkError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    except ProviderError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
