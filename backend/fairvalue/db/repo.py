"""Report repository: save / get / list ValuationReports with provenance intact."""
from __future__ import annotations

import json

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

import fairvalue
from fairvalue.core.schemas import ValuationReport
from fairvalue.db.models import ReportRecord


def save_report(session: Session, report: ValuationReport) -> str:
    """Store a report. Re-saving the same report_id is an upsert (latest wins),
    matching the normalization layer's restatement policy."""
    rid = report.report_id or f"r-{report.generated_at.strftime('%Y%m%d%H%M%S%f')}"
    if report.report_id is None:
        report = report.model_copy(update={"report_id": rid})
    payload = report.model_dump(mode="json")
    dcf_wacc = None
    for m in report.models:
        if m.model == "dcf" and m.assumptions.get("wacc") is not None:
            dcf_wacc = float(m.assumptions["wacc"])
    existing = session.scalar(select(ReportRecord).where(ReportRecord.report_id == rid))
    fields = dict(
        report_id=rid,
        ticker=report.company.ticker,
        company_name=report.company.name,
        generated_at=report.generated_at,
        schema_version=report.schema_version,
        engine_version=fairvalue.__version__,
        is_illustrative=report.is_illustrative,
        recon_base=report.reconciliation.base,
        recon_low=report.reconciliation.low,
        recon_high=report.reconciliation.high,
        dcf_wacc=dcf_wacc,
        market_price=(report.market.price if report.market else None),
        payload=payload,
    )
    if existing is None:
        session.add(ReportRecord(**fields))
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
    session.commit()
    return rid


def get_report(session: Session, report_id: str) -> ValuationReport | None:
    rec = session.scalar(select(ReportRecord).where(ReportRecord.report_id == report_id))
    return ValuationReport.model_validate(rec.payload) if rec else None


def list_reports(session: Session, ticker: str | None = None,
                 limit: int = 50) -> list[dict]:
    """Newest first. Returns the indexed (queryable) columns only — the full
    payload stays a DB retrieval away."""
    q = select(ReportRecord).order_by(desc(ReportRecord.generated_at)).limit(limit)
    if ticker:
        q = q.where(ReportRecord.ticker == ticker.upper())
    return [
        {"report_id": r.report_id, "ticker": r.ticker,
         "company_name": r.company_name,
         "generated_at": r.generated_at.isoformat(),
         "saved_at": r.saved_at.isoformat(),
         "schema_version": r.schema_version, "engine_version": r.engine_version,
         "is_illustrative": r.is_illustrative,
         "reconciliation": {"low": r.recon_low, "base": r.recon_base,
                            "high": r.recon_high},
         "dcf_wacc": r.dcf_wacc, "market_price": r.market_price}
        for r in session.scalars(q)
    ]
