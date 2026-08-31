"""
Migration 003 — Phase 3: Validation Mock Government Database Tables.

Creates three mock tables to stand in for real government API integrations:
  1. mock_sltd          — Interpol Stolen & Lost Travel Documents
  2. mock_blacklist     — National prohibited/watchlist persons
  3. mock_visa_records  — Valid visa-type / nationality combinations
  4. offline_sync_log   — Records offline decisions synced back to Postgres

Also seeds synthetic demo data for the Phase 3 and Phase 8 demo scenarios.

Revision ID: 003
Revises: 002
Create Date: 2026-08-31
"""

import datetime
import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. mock_sltd ────────────────────────────────────────────────────────
    op.create_table(
        "mock_sltd",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_number", sa.String(30), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("reporting_country", sa.String(3), nullable=False),
        sa.Column("reported_at", sa.Date(), nullable=False),
    )
    op.create_index(
        "ix_mock_sltd_document_number", "mock_sltd", ["document_number"], unique=True
    )

    # ── 2. mock_blacklist ────────────────────────────────────────────────────
    op.create_table(
        "mock_blacklist",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.String(10), nullable=True),
        sa.Column("document_number", sa.String(30), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="watchlist"),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_index("ix_mock_blacklist_name", "mock_blacklist", ["name"])
    op.create_index(
        "ix_mock_blacklist_doc_num", "mock_blacklist", ["document_number"]
    )
    op.create_unique_constraint(
        "uq_blacklist_name_dob", "mock_blacklist", ["name", "date_of_birth"]
    )

    # ── 3. mock_visa_records ─────────────────────────────────────────────────
    op.create_table(
        "mock_visa_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("visa_type", sa.String(30), nullable=False),
        sa.Column("nationality", sa.String(3), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("max_stay_days", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_visa_nationality", "mock_visa_records", ["visa_type", "nationality"]
    )

    # ── 4. offline_sync_log — receives offline decisions pushed by validation_service ─
    op.create_table(
        "offline_sync_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("decision_json", sa.Text(), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # ── Seed demo data ───────────────────────────────────────────────────────
    _seed_demo_data()


def _seed_demo_data() -> None:
    """
    Seed synthetic SLTD entries and blacklist records for Phase 3 and Phase 8 demo.

    Document numbers are clearly fictional (X9-prefix / Z-prefix / demo suffixes).
    No real person's data is used.
    """
    today = datetime.date.today()
    reported_two_years_ago = (today - datetime.timedelta(days=730)).isoformat()
    reported_one_year_ago = (today - datetime.timedelta(days=365)).isoformat()

    # ─ SLTD Entries (5 synthetic lost/stolen passports) ─
    sltd_entries = [
        {
            "document_number": "X9999999",
            "report_type": "stolen",
            "reporting_country": "IND",
            "reported_at": reported_two_years_ago,
        },
        {
            "document_number": "X8888888",
            "report_type": "lost",
            "reporting_country": "GBR",
            "reported_at": reported_one_year_ago,
        },
        {
            "document_number": "DEMO-SLTD-001",
            "report_type": "fraudulent",
            "reporting_country": "USA",
            "reported_at": reported_two_years_ago,
        },
        {
            "document_number": "Z0000001",
            "report_type": "stolen",
            "reporting_country": "DEU",
            "reported_at": reported_one_year_ago,
        },
        {
            "document_number": "INVALID-DOC-99",
            "report_type": "lost",
            "reporting_country": "AUS",
            "reported_at": reported_two_years_ago,
        },
    ]

    op.bulk_insert(
        sa.table(
            "mock_sltd",
            sa.column("document_number", sa.String),
            sa.column("report_type", sa.String),
            sa.column("reporting_country", sa.String),
            sa.column("reported_at", sa.Date),
        ),
        [
            {
                "document_number": e["document_number"],
                "report_type": e["report_type"],
                "reporting_country": e["reporting_country"],
                "reported_at": datetime.date.fromisoformat(e["reported_at"]),
            }
            for e in sltd_entries
        ],
    )

    # ─ Blacklist Entries (3 fictional prohibited persons) ─
    op.bulk_insert(
        sa.table(
            "mock_blacklist",
            sa.column("name", sa.String),
            sa.column("date_of_birth", sa.String),
            sa.column("document_number", sa.String),
            sa.column("severity", sa.String),
            sa.column("reason", sa.Text),
        ),
        [
            {
                "name": "JOHN DEMO BANNED",
                "date_of_birth": "1985-01-01",
                "document_number": "X9999999",
                "severity": "banned",
                "reason": "Synthetic demo entry: SLTD cross-match + prohibited travel history.",
            },
            {
                "name": "DEMO WATCHLIST PERSON",
                "date_of_birth": "1990-06-15",
                "document_number": None,
                "severity": "watchlist",
                "reason": "Synthetic demo entry: name+DOB watchlist flag.",
            },
            {
                "name": "INVESTIGATE DEMO SUBJECT",
                "date_of_birth": "1978-11-23",
                "document_number": "DEMO-SLTD-001",
                "severity": "investigate",
                "reason": "Synthetic demo entry: secondary inspection required.",
            },
        ],
    )

    # ─ Visa Validity Records (common traveller combinations) ─
    op.bulk_insert(
        sa.table(
            "mock_visa_records",
            sa.column("visa_type", sa.String),
            sa.column("nationality", sa.String),
            sa.column("is_valid", sa.Boolean),
            sa.column("max_stay_days", sa.Integer),
        ),
        [
            {"visa_type": "tourist", "nationality": "NPL", "is_valid": True, "max_stay_days": 90},
            {"visa_type": "tourist", "nationality": "BGD", "is_valid": True, "max_stay_days": 30},
            {"visa_type": "tourist", "nationality": "MMR", "is_valid": True, "max_stay_days": 28},
            {"visa_type": "tourist", "nationality": "BTN", "is_valid": True, "max_stay_days": 90},
            {"visa_type": "business", "nationality": "NPL", "is_valid": True, "max_stay_days": 180},
            {"visa_type": "business", "nationality": "BGD", "is_valid": True, "max_stay_days": 60},
            {"visa_type": "transit", "nationality": "NPL", "is_valid": True, "max_stay_days": 3},
            {"visa_type": "transit", "nationality": "MMR", "is_valid": True, "max_stay_days": 2},
            # Explicitly invalid combinations (for testing)
            {"visa_type": "diplomatic", "nationality": "BGD", "is_valid": False, "max_stay_days": None},
        ],
    )


def downgrade() -> None:
    op.drop_table("offline_sync_log")
    op.drop_constraint("uq_visa_nationality", "mock_visa_records", type_="unique")
    op.drop_table("mock_visa_records")
    op.drop_constraint("uq_blacklist_name_dob", "mock_blacklist", type_="unique")
    op.drop_index("ix_mock_blacklist_doc_num", table_name="mock_blacklist")
    op.drop_index("ix_mock_blacklist_name", table_name="mock_blacklist")
    op.drop_table("mock_blacklist")
    op.drop_index("ix_mock_sltd_document_number", table_name="mock_sltd")
    op.drop_table("mock_sltd")
