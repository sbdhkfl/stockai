"""initial reports table

Revision ID: 0001_reports
Revises:
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_reports"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "valuation_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("ticker", sa.String(length=16), nullable=False, index=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("is_illustrative", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("recon_base", sa.Float(), nullable=True),
        sa.Column("recon_low", sa.Float(), nullable=True),
        sa.Column("recon_high", sa.Float(), nullable=True),
        sa.Column("dcf_wacc", sa.Float(), nullable=True),
        sa.Column("market_price", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("valuation_reports")
