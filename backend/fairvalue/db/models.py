"""SQLAlchemy ORM models for report persistence.

The full ValuationReport is stored verbatim (JSON) — assumptions, per-model
steps, provenance and data-quality records survive round-trips untouched.
Indexed columns exist only for querying; they are never the source of truth.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ReportRecord(Base):
    __tablename__ = "valuation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    schema_version: Mapped[str] = mapped_column(String(16))
    engine_version: Mapped[str] = mapped_column(String(32))
    is_illustrative: Mapped[bool] = mapped_column(default=False)
    # queryable headline numbers (denormalized from the JSON for listing pages)
    recon_base: Mapped[float | None] = mapped_column(Float, nullable=True)
    recon_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    recon_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    dcf_wacc: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
