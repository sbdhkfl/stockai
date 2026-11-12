"""Report persistence (SQLAlchemy 2.x + Alembic).

Stores full ValuationReports as JSON alongside indexed queryable columns
(ticker, timestamps, engine/schema version, reconciliation base/low/high and
the DCF WACC assumption) so previous reports can be listed, retrieved and
audited with their assumptions and provenance intact.
"""
