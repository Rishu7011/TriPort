"""
Alembic Migration: 004 — Supabase schema (complete replacement).

This migration drops the old TriPort tables and creates the new 13-table
schema designed for Supabase (PostgreSQL 15 + pgvector).

It also:
  - Enables the pgvector extension (pre-installed on Supabase; safe no-op).
  - Creates the HNSW index on face_embeddings.embedding.
  - Seeds the demo checkpoint (CP-DEL-T3 → fixed UUID).
  - Seeds demo users (UUIDs match DEMO_USERS in security.py).
  - Seeds 2 demo watchlist entries with normalised (UPPERCASE) values.
  - Applies Row-Level Security to audit_ledger (deny UPDATE/DELETE).

Revision ID: 004
Revises: 003_phase3_validation_mock_tables
Create Date: 2026-09-02

Run:
  cd /Users/rishu/Desktop/TriPort
  alembic -c alembic.ini upgrade head
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
import uuid

# ── Revision identifiers ────────────────────────────────────────────────────
revision: str = "004"
down_revision: str | None = "003"
branch_labels = None
depends_on = None

# ── Deterministic seed UUIDs (must stay stable) ─────────────────────────────
# Checkpoint
CP_DEL_T3_UUID = "00000000-0000-0000-0000-000000000010"

# Users — must match DEMO_USERS in backend/orchestrator/auth/security.py
USER_OFFICER_UUID   = "00000000-0000-0000-0000-000000000001"
USER_SUPERVISOR_UUID = "00000000-0000-0000-0000-000000000002"
USER_AUDITOR_UUID   = "00000000-0000-0000-0000-000000000003"
USER_ADMIN_UUID     = "00000000-0000-0000-0000-000000000004"

# Watchlist seed entries
WL_VIKTOR_UUID = "00000000-0000-0000-0000-000000000020"
WL_JOHNDOE_UUID = "00000000-0000-0000-0000-000000000021"


def upgrade() -> None:
    # ── 0. Enable pgvector extension ─────────────────────────────────────────
    # Safe no-op on Supabase (pre-installed). Required for Vector column type.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── 1. Drop old tables (ordered to respect FKs) ─────────────────────────
    for tbl in [
        "tampering_results",
        "validation_results",
        "extracted_fields",
        "face_embeddings",
        "risk_scores",
        "audit_ledger",
        "blacklist",
        "documents",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")

    # ── 2. Create new tables ─────────────────────────────────────────────────

    # checkpoints
    op.create_table(
        "checkpoints",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("checkpoint_type", sa.Text, nullable=False),
        sa.Column("country_code", sa.Text, nullable=True),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("metadata", pg.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checkpoints_type", "checkpoints", ["checkpoint_type"])

    # users
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("badge_number", sa.Text, nullable=True),
        sa.Column(
            "checkpoint_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("checkpoints.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # person_clusters
    op.create_table(
        "person_clusters",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("highest_risk_band", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("metadata", pg.JSONB, nullable=True),
    )
    op.create_index("ix_person_clusters_last_seen", "person_clusters", ["last_seen_at"])

    # scan_events
    op.create_table(
        "scan_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "checkpoint_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("checkpoints.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "officer_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_type", sa.Text, nullable=False),
        sa.Column("inspection_status", sa.Text, nullable=False, server_default="standard_clearance"),
        sa.Column("doc_image_url", sa.Text, nullable=True),
        sa.Column("doc_face_crop_url", sa.Text, nullable=True),
        sa.Column("live_image_url", sa.Text, nullable=True),
        sa.Column("pipeline_snapshot", pg.JSONB, nullable=True),
        sa.Column("degraded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scan_events_uploaded_at", "scan_events", ["uploaded_at"])
    op.create_index("ix_scan_events_checkpoint_id", "scan_events", ["checkpoint_id"])
    op.create_index("ix_scan_events_inspection_status", "scan_events", ["inspection_status"])
    op.create_index("ix_scan_events_officer_id", "scan_events", ["officer_id"])
    op.create_index("ix_scan_events_document_type", "scan_events", ["document_type"])

    # extracted_fields
    op.create_table(
        "extracted_fields",
        sa.Column(
            "scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("field_name", sa.Text, primary_key=True),
        sa.Column("field_value", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("source", sa.Text, nullable=False, server_default="ocr"),
    )
    op.create_index(
        "ix_extracted_fields_field_name_value",
        "extracted_fields",
        ["field_name", "field_value"],
    )

    # tampering_results
    op.create_table(
        "tampering_results",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("flagged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("composite_score", sa.Float, nullable=True),
        sa.Column("checks", pg.JSONB, nullable=True),
        sa.Column("ela_heatmap_url", sa.Text, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # face_embeddings
    op.create_table(
        "face_embeddings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "person_cluster_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("person_clusters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # pgvector column — requires CREATE EXTENSION vector (done above)
        sa.Column("embedding", sa.Text, nullable=True),   # typed as Text here; migration alters below
        sa.Column("face_detected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("face_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("provider", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Alter embedding column to the actual vector type (pgvector not natively supported by alembic)
    op.execute("ALTER TABLE face_embeddings ALTER COLUMN embedding TYPE vector(512) USING NULL")
    op.create_index("ix_face_embeddings_person_cluster_id", "face_embeddings", ["person_cluster_id"])
    # HNSW index for ANN similarity search — chosen over IVFFlat because HNSW
    # handles incremental inserts without periodic re-indexing (IVFFlat centroids
    # degrade as new rows are inserted). m=16, ef_construction=64 are conservative
    # defaults suitable for Supabase free tier memory limits.
    op.execute(
        """
        CREATE INDEX face_embeddings_hnsw_idx
            ON face_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )

    # face_verification_results
    op.create_table(
        "face_verification_results",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("one_to_one_matched", sa.Boolean, nullable=True),
        sa.Column("match_score", sa.Float, nullable=True),
        sa.Column("cosine_similarity", sa.Float, nullable=True),
        sa.Column("dedup_has_duplicates", sa.Boolean, nullable=True),
        sa.Column(
            "dedup_person_cluster_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("person_clusters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dedup_hits", pg.JSONB, nullable=True),
        sa.Column("liveness_is_live", sa.Boolean, nullable=True),
        sa.Column("liveness_score", sa.Float, nullable=True),
        sa.Column("provider", sa.Text, nullable=True),
        sa.Column("bypassed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("bypassed_reason", sa.Text, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # risk_results
    op.create_table(
        "risk_results",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("band", sa.Text, nullable=True),
        sa.Column("reasons", pg.JSONB, nullable=True),
        sa.Column("sub_scores", pg.JSONB, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_risk_results_band", "risk_results", ["band"])
    op.create_index("ix_risk_results_score", "risk_results", ["score"])

    # officer_decisions
    op.create_table(
        "officer_decisions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "officer_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_officer_decisions_scan_event_id", "officer_decisions", ["scan_event_id"])
    op.create_index("ix_officer_decisions_officer_id", "officer_decisions", ["officer_id"])

    # cross_checkpoint_flags
    op.create_table(
        "cross_checkpoint_flags",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "person_cluster_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("person_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggering_scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("flag_type", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("related_scan_event_ids", pg.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "resolved_by",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cross_checkpoint_flags_cluster", "cross_checkpoint_flags", ["person_cluster_id"])
    op.create_index(
        "ix_cross_checkpoint_flags_type_severity",
        "cross_checkpoint_flags",
        ["flag_type", "severity"],
    )

    # watchlist_entries
    op.create_table(
        "watchlist_entries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("source", sa.Text, nullable=False, server_default="national"),
        sa.Column("source_reference", sa.Text, nullable=True),
        sa.Column("document_number", sa.Text, nullable=True),   # stored UPPERCASE+STRIP
        sa.Column("full_name", sa.Text, nullable=True),         # stored UPPERCASE+STRIP
        sa.Column("date_of_birth", sa.Text, nullable=True),
        sa.Column("nationality", sa.Text, nullable=True),
        sa.Column("severity", sa.Text, nullable=False, server_default="watch"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", pg.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "created_by",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_watchlist_document_number", "watchlist_entries", ["document_number"])
    op.create_index("ix_watchlist_full_name", "watchlist_entries", ["full_name"])
    op.create_index("ix_watchlist_is_active", "watchlist_entries", ["is_active"])

    # audit_ledger
    op.create_table(
        "audit_ledger",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("sequence_num", sa.BigInteger, nullable=False, unique=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column(
            "scan_event_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("scan_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payload", pg.JSONB, nullable=True),
        sa.Column("payload_hash", sa.Text, nullable=False),
        sa.Column("prev_record_hash", sa.Text, nullable=False),
        sa.Column("record_hash", sa.Text, nullable=False),
        sa.Column(
            "officer_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_ledger_scan_event_id", "audit_ledger", ["scan_event_id"])
    op.create_index("ix_audit_ledger_officer_id", "audit_ledger", ["officer_id"])

    # ── 3. Row-Level Security on audit_ledger (append-only enforcement) ───────
    # Deny UPDATE and DELETE at Postgres level for all roles.
    # On Supabase, RLS must also be enabled via the dashboard (or ALTER TABLE below).
    op.execute("ALTER TABLE audit_ledger ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_ledger_insert_only
            ON audit_ledger
            AS RESTRICTIVE
            FOR ALL
            USING (true)
            WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY audit_ledger_no_update
            ON audit_ledger
            AS RESTRICTIVE
            FOR UPDATE
            USING (false)
        """
    )
    op.execute(
        """
        CREATE POLICY audit_ledger_no_delete
            ON audit_ledger
            AS RESTRICTIVE
            FOR DELETE
            USING (false)
        """
    )

    # ── 4. Seed data ─────────────────────────────────────────────────────────

    # Seed checkpoint: CP-DEL-T3 (Delhi Terminal 3)
    op.execute(
        f"""
        INSERT INTO checkpoints (id, name, checkpoint_type, country_code, location, is_active)
        VALUES (
            '{CP_DEL_T3_UUID}',
            'Indira Gandhi International Airport — Terminal 3 Immigration',
            'airport',
            'IN',
            'New Delhi, India',
            true
        )
        ON CONFLICT (id) DO NOTHING
        """
    )

    # Seed demo users — bcrypt hashes for the demo passwords
    # These match DEMO_USERS in backend/orchestrator/auth/security.py
    # Hashes pre-computed (bcrypt, 12 rounds):
    #   officer123    → stored hash below
    #   supervisor123
    #   auditor123
    #   admin123
    # NOTE: In production, never embed password hashes in migrations.
    # For hackathon demo the static passwords are acceptable.
    _users = [
        (USER_OFFICER_UUID,    "officer@triport.gov",    "officer",    "Officer J. Miller",    "TP-7492",      CP_DEL_T3_UUID,  "$2b$12$wUdNr0Fc3vZnLl.r5NWrpuLjkd2SOcIjh6x6WLPBDqaG9ufJFYvzC"),
        (USER_SUPERVISOR_UUID, "supervisor@triport.gov", "supervisor", "Supervisor S. Rao",    "TP-SUP-014",   CP_DEL_T3_UUID,  "$2b$12$FLfJ6JxPyN1eOnXCqkJM2.Vxg.RSTuoJVL3HkYBNblxdz02K/gLTS"),
        (USER_AUDITOR_UUID,    "auditor@triport.gov",    "auditor",    "Auditor M. Chen",      "TP-AUD-990",   None,            "$2b$12$Ur2pHISSMcCYzfMhAiFfJeW.v41TnA0u7GRhFoEi8Q3IbYjqJblxi"),
        (USER_ADMIN_UUID,      "admin@triport.gov",      "admin",      "Administrator",        "TP-ADM-001",   None,            "$2b$12$N9GBhLl9VBxlpBKAMzS4HOQb4Hj0c3GxYLtq/L6TRLnFmVL1E3Pw2"),
    ]
    for uid, email, role, name, badge, cp_id, pw_hash in _users:
        cp_val = f"'{cp_id}'" if cp_id else "NULL"
        op.execute(
            f"""
            INSERT INTO users (id, email, password_hash, role, name, badge_number, checkpoint_id, is_active)
            VALUES ('{uid}', '{email}', '{pw_hash}', '{role}', '{name}', '{badge}', {cp_val}, true)
            ON CONFLICT (id) DO NOTHING
            """
        )

    # Seed demo watchlist entries (UPPERCASE+STRIP — as stored)
    op.execute(
        f"""
        INSERT INTO watchlist_entries
            (id, source, document_number, full_name, severity, reason, is_active)
        VALUES
            ('{WL_VIKTOR_UUID}', 'interpol', 'X9999999', 'VIKTOR KORZHOV',
             'banned', 'Interpol Red Notice - Document Forgery & Identity Theft', true),
            ('{WL_JOHNDOE_UUID}', 'national', 'B1234567', 'JOHN DOE SUSPECT',
             'suspect', 'Active Border Alert - Cross-Border Smuggling', true)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    # Drop all new tables in reverse FK order
    for tbl in [
        "audit_ledger",
        "watchlist_entries",
        "cross_checkpoint_flags",
        "officer_decisions",
        "risk_results",
        "face_verification_results",
        "face_embeddings",
        "tampering_results",
        "extracted_fields",
        "scan_events",
        "person_clusters",
        "users",
        "checkpoints",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
