"""
DB Models — SQLAlchemy 2.0 ORM definitions for all TriPort tables.

Architecture:
  - Supabase (PostgreSQL 15 + pgvector) is the sole persistence layer.
  - 13 tables organised around a central `scan_events` fact table.
  - JSONB used for variable-shape data (tampering checks, risk sub-scores,
    pipeline snapshot). EAV used for OCR extracted fields.
  - face_embeddings uses pgvector Vector(512) with an HNSW index (defined in
    the Alembic migration, not here).
  - watchlist_entries normalises document_number / full_name to UPPERCASE+STRIP
    via a SQLAlchemy event listener so all lookups are case/whitespace agnostic.

Table overview:
  checkpoints          — physical border crossing stations
  users                — officers / supervisors / auditors / admins
  person_clusters      — biometric identity clusters (one per physical person)
  scan_events          — one row per document presented at a checkpoint (central fact)
  extracted_fields     — EAV OCR output per scan
  tampering_results    — composite + per-engine forensic scores (JSONB checks)
  face_embeddings      — 512-dim ArcFace vector per scan, linked to cluster
  face_verification_results — 1:1 match + liveness results per scan
  risk_results         — composite risk score + band + sub-scores JSONB
  officer_decisions    — officer verdicts (approve/flag/reject)
  cross_checkpoint_flags — fraud signals per person cluster
  watchlist_entries    — source-agnostic blacklist / watchlist
  audit_ledger         — append-only SHA-256 hash-chained event log
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    UUID,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Registry base — all models inherit from this."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now_ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# checkpoints
# ---------------------------------------------------------------------------
class Checkpoint(Base):
    """
    A physical border crossing station.
    checkpoint_type is free TEXT (airport/land_border/seaport/…) — new types
    are addable via data insert, not schema migration.
    """
    __tablename__ = "checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_type: Mapped[str] = mapped_column(Text, nullable=False)  # airport|land_border|seaport
    country_code: Mapped[str | None] = mapped_column(Text, nullable=True)  # ISO 3166-1 alpha-2
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Any future checkpoint-specific fields (concourse, lane, camera ID, etc.)
    extra_data: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan_events: Mapped[list["ScanEvent"]] = relationship(back_populates="checkpoint")
    users: Mapped[list["User"]] = relationship(back_populates="checkpoint")

    __table_args__ = (
        Index("ix_checkpoints_type", "checkpoint_type"),
    )


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    """
    Officers, supervisors, auditors, admins.
    UUIDs match DEMO_USERS in security.py so existing JWTs remain valid.
    checkpoint_id is nullable — HQ roles have no associated checkpoint.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # officer|supervisor|auditor|admin
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    badge_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checkpoints.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    checkpoint: Mapped["Checkpoint | None"] = relationship(back_populates="users")
    officer_decisions: Mapped[list["OfficerDecision"]] = relationship(back_populates="officer")
    audit_entries: Mapped[list["AuditLedgerEntry"]] = relationship(back_populates="officer")
    watchlist_entries_created: Mapped[list["WatchlistEntry"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="WatchlistEntry.created_by",
    )


# ---------------------------------------------------------------------------
# person_clusters
# ---------------------------------------------------------------------------
class PersonCluster(Base):
    """
    A biometric identity cluster — the entity that links all documents ever
    presented by the same physical person, even under different names.

    Created on first face embedding; updated on each new scan match.
    The cluster ID is the stable identity anchor across the system.
    """
    __tablename__ = "person_clusters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Denormalized — updated each scan; avoids a MAX() aggregate on risk_results for quick reads
    highest_risk_band: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Extensible cluster-level flags (e.g. interpol_watch: true)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


    # Relationships
    face_embeddings: Mapped[list["FaceEmbedding"]] = relationship(back_populates="person_cluster")
    cross_checkpoint_flags: Mapped[list["CrossCheckpointFlag"]] = relationship(
        back_populates="person_cluster",
        foreign_keys="CrossCheckpointFlag.person_cluster_id",
    )

    __table_args__ = (
        Index("ix_person_clusters_last_seen", "last_seen_at"),
    )


# ---------------------------------------------------------------------------
# scan_events  (central fact table — replaces old Document + in-memory ScanRecord)
# ---------------------------------------------------------------------------
class ScanEvent(Base):
    """
    One row per document screening run.
    The `id` is what the API refers to as `document_id` throughout.

    Key design decisions:
    - document_type and inspection_status are free TEXT — new values via data only.
    - Image fields store Supabase Storage URLs, never raw bytes or base64.
    - pipeline_snapshot (JSONB) caches the full PipelineResult — allows /pipeline
      endpoint to respond with a single row read, no joins.
    - Child tables (tampering_results, risk_results, etc.) hold structured data
      for filtering/aggregation queries.
    """
    __tablename__ = "scan_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    checkpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checkpoints.id", ondelete="SET NULL"),
        nullable=True,
    )
    officer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Free text — passport|visa|national_id|driving_license|permit|...
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    # standard_clearance|secondary_inspection|approved|rejected
    inspection_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="standard_clearance"
    )

    # Supabase Storage URLs (replaces inline base64)
    doc_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_face_crop_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    live_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full pipeline result snapshot — drives the /pipeline endpoint without joins.
    # Also serves as the forensic source of truth for the pipeline run.
    pipeline_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # True if one or more services failed during this pipeline run
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    checkpoint: Mapped["Checkpoint | None"] = relationship(back_populates="scan_events")
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="scan_event", cascade="all, delete-orphan"
    )
    tampering_result: Mapped["TamperingResult | None"] = relationship(
        back_populates="scan_event", cascade="all, delete-orphan", uselist=False
    )
    face_embedding: Mapped["FaceEmbedding | None"] = relationship(
        back_populates="scan_event", cascade="all, delete-orphan", uselist=False
    )
    face_verification_result: Mapped["FaceVerificationResult | None"] = relationship(
        back_populates="scan_event", cascade="all, delete-orphan", uselist=False
    )
    risk_result: Mapped["RiskResult | None"] = relationship(
        back_populates="scan_event", cascade="all, delete-orphan", uselist=False
    )
    officer_decisions: Mapped[list["OfficerDecision"]] = relationship(
        back_populates="scan_event", cascade="all, delete-orphan"
    )
    audit_entries: Mapped[list["AuditLedgerEntry"]] = relationship(back_populates="scan_event")
    cross_checkpoint_flags_triggered: Mapped[list["CrossCheckpointFlag"]] = relationship(
        back_populates="triggering_scan_event",
        foreign_keys="CrossCheckpointFlag.triggering_scan_event_id",
    )

    __table_args__ = (
        # Most frequent read patterns
        Index("ix_scan_events_uploaded_at", "uploaded_at"),
        Index("ix_scan_events_checkpoint_id", "checkpoint_id"),
        Index("ix_scan_events_inspection_status", "inspection_status"),
        Index("ix_scan_events_officer_id", "officer_id"),
        Index("ix_scan_events_document_type", "document_type"),
    )


# ---------------------------------------------------------------------------
# extracted_fields  (EAV — OCR output, one row per field per scan)
# ---------------------------------------------------------------------------
class ExtractedField(Base):
    """
    EAV-style OCR output.
    Composite PK (scan_event_id, field_name) — one field name per scan.
    `source` tracks which extraction method produced the value so the audit
    trail can distinguish OCR vs MRZ vs LLM fallback per field.
    """
    __tablename__ = "extracted_fields"

    scan_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # e.g. passport_number|name|date_of_expiry|nationality|date_of_birth
    field_name: Mapped[str] = mapped_column(Text, primary_key=True)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ocr|mrz|llm_fallback — which engine produced this value
    source: Mapped[str] = mapped_column(Text, nullable=False, default="ocr")

    # Relationships
    scan_event: Mapped["ScanEvent"] = relationship(back_populates="extracted_fields")

    __table_args__ = (
        # Enables fast exact-match blacklist lookups and passport-number cross-queries
        Index("ix_extracted_fields_field_name_value", "field_name", "field_value"),
    )


# ---------------------------------------------------------------------------
# tampering_results  (one row per scan, sub-engine scores in JSONB)
# ---------------------------------------------------------------------------
class TamperingResult(Base):
    """
    Forensic tampering detection output.

    JSONB `checks` stores all sub-engine results as an array:
      [{"check_type": "ela", "score": 0.72, "flagged": true, "detail": {...}}, ...]

    This means new sub-engines (e.g. watermark detection) are addable without
    schema migration. Cross-scan queries on individual check scores use JSONB
    path operators:
      WHERE (checks @> '[{"check_type": "ela", "flagged": true}]')
    """
    __tablename__ = "tampering_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="CASCADE"),
        unique=True,  # one-to-one
        nullable=False,
    )
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Array of {check_type, score, flagged, detail} — all 5 sub-engines
    checks: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Supabase Storage URL — replaces inline ela_heatmap_base64
    ela_heatmap_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan_event: Mapped["ScanEvent"] = relationship(back_populates="tampering_result")


# ---------------------------------------------------------------------------
# face_embeddings  (pgvector — 512-dim ArcFace vector, links to person_clusters)
# ---------------------------------------------------------------------------
class FaceEmbedding(Base):
    """
    Stores the 512-dimensional ArcFace/InsightFace embedding for a scan.
    Always produced by the local model regardless of face_verification_provider
    setting — AWS Rekognition does not expose raw embeddings.

    The HNSW index on `embedding` is created in the Alembic migration:
      CREATE INDEX face_embeddings_hnsw_idx ON face_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """
    __tablename__ = "face_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    person_cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("person_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 512-dimensional L2-normalised cosine-space embedding vector
    embedding: Mapped[list[float] | None] = mapped_column(Vector(512), nullable=True)

    face_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    face_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # local|insightface|arcface — which local model produced this embedding
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan_event: Mapped["ScanEvent"] = relationship(back_populates="face_embedding")
    person_cluster: Mapped["PersonCluster | None"] = relationship(back_populates="face_embeddings")

    __table_args__ = (
        Index("ix_face_embeddings_person_cluster_id", "person_cluster_id"),
        # HNSW index created separately in Alembic migration (not expressible here)
    )


# ---------------------------------------------------------------------------
# face_verification_results  (1:1 match + liveness per scan)
# ---------------------------------------------------------------------------
class FaceVerificationResult(Base):
    """
    1:1 biometric match result between document photo and live capture.
    Stored separately from the embedding to allow late population (the live
    verify-face endpoint is called after the initial upload).
    """
    __tablename__ = "face_verification_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # 1:1 match fields
    one_to_one_matched: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cosine_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 1:N dedup fields
    dedup_has_duplicates: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dedup_person_cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("person_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Array of {document_id, similarity, person_cluster_id}
    dedup_hits: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Liveness fields
    liveness_is_live: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # aws_rekognition|local|insightface
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)

    bypassed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bypassed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan_event: Mapped["ScanEvent"] = relationship(back_populates="face_verification_result")


# ---------------------------------------------------------------------------
# risk_results  (composite risk score per scan)
# ---------------------------------------------------------------------------
class RiskResult(Base):
    """
    Composite risk score output from the risk engine.
    sub_scores JSONB stores the full SubScores object
    (validation, tampering, face, blacklist, cross_checkpoint sub-objects).
    """
    __tablename__ = "risk_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    band: Mapped[str | None] = mapped_column(Text, nullable=True)  # low|medium|high|critical

    # ["MRZ checksum failed on DOB", "Blacklist hit: document_number", ...]
    reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Full SubScores breakdown — validation/tampering/face/blacklist/cross_checkpoint
    sub_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan_event: Mapped["ScanEvent"] = relationship(back_populates="risk_result")

    __table_args__ = (
        Index("ix_risk_results_band", "band"),
        Index("ix_risk_results_score", "score"),
    )


# ---------------------------------------------------------------------------
# officer_decisions
# ---------------------------------------------------------------------------
class OfficerDecision(Base):
    """
    Officer verdict for a scan.
    Not UNIQUE on scan_event_id — a decision can be revised, and the full
    history is preserved (latest decision is the one that counts operationally).
    """
    __tablename__ = "officer_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    officer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)  # approve|flag|reject|escalate
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan_event: Mapped["ScanEvent"] = relationship(back_populates="officer_decisions")
    officer: Mapped["User | None"] = relationship(back_populates="officer_decisions")

    __table_args__ = (
        Index("ix_officer_decisions_scan_event_id", "scan_event_id"),
        Index("ix_officer_decisions_officer_id", "officer_id"),
    )


# ---------------------------------------------------------------------------
# cross_checkpoint_flags
# ---------------------------------------------------------------------------
class CrossCheckpointFlag(Base):
    """
    A persisted fraud signal detected by the cross-checkpoint engine.
    Each flag is one row — one scan can generate multiple flags.
    `resolved` allows an officer to mark a flag as reviewed without deletion.
    """
    __tablename__ = "cross_checkpoint_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    person_cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("person_clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggering_scan_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # name_mismatch|doc_number_mismatch|dob_mismatch|nationality_mismatch|
    # impossible_travel|repeat_offender
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)  # medium|high|critical
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # UUIDs of the other scan_events involved in this flag
    related_scan_event_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    person_cluster: Mapped["PersonCluster"] = relationship(
        back_populates="cross_checkpoint_flags",
        foreign_keys=[person_cluster_id],
    )
    triggering_scan_event: Mapped["ScanEvent | None"] = relationship(
        back_populates="cross_checkpoint_flags_triggered",
        foreign_keys=[triggering_scan_event_id],
    )

    __table_args__ = (
        Index("ix_cross_checkpoint_flags_cluster", "person_cluster_id"),
        Index("ix_cross_checkpoint_flags_type_severity", "flag_type", "severity"),
    )


# ---------------------------------------------------------------------------
# watchlist_entries  (source-agnostic blacklist/watchlist)
# ---------------------------------------------------------------------------
class WatchlistEntry(Base):
    """
    Source-agnostic watchlist/blacklist.
    Supports Interpol notices, national blacklists, and future sources without
    schema changes — `source` and `metadata` are free-form.

    NORMALISATION: document_number and full_name are stored UPPERCASE+STRIP.
    This is enforced by an SQLAlchemy event listener (after_attach) and in the
    application layer before every INSERT. The check_blacklist() function also
    normalises its query inputs so OCR output "  viktor korzhov  " matches
    the stored "VIKTOR KORZHOV".
    """
    __tablename__ = "watchlist_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # interpol|national|internal|...  — free text, new sources without migration
    source: Mapped[str] = mapped_column(Text, nullable=False, default="national")
    # External ID from the originating system (e.g. Interpol notice number)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Core match fields — stored UPPERCASE+STRIP (normalised on insert, see listener below)
    document_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(Text, nullable=True)
    nationality: Mapped[str | None] = mapped_column(Text, nullable=True)

    severity: Mapped[str] = mapped_column(Text, nullable=False, default="watch")  # watch|suspect|banned
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Soft-delete — never hard-delete watchlist entries
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional validity window (some Interpol notices expire)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Additional source-specific fields (biometric ref, case number, photo URL, etc.)
    extra_data: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    created_by_user: Mapped["User | None"] = relationship(
        back_populates="watchlist_entries_created",
        foreign_keys=[created_by],
    )

    __table_args__ = (
        # Exact-match lookups — the most common blacklist query pattern
        Index("ix_watchlist_document_number", "document_number"),
        Index("ix_watchlist_full_name", "full_name"),
        Index("ix_watchlist_is_active", "is_active"),
    )


# ── Normalisation event listener ─────────────────────────────────────────────
def _normalise_watchlist(target: WatchlistEntry, *_: Any) -> None:
    """
    Enforce UPPERCASE + STRIP on document_number and full_name before every
    INSERT and UPDATE. This ensures OCR noise ("  Viktor Korzhov  " / "viktor
    korzhov") matches stored entries regardless of casing or whitespace.
    """
    if target.document_number is not None:
        target.document_number = target.document_number.strip().upper()
    if target.full_name is not None:
        target.full_name = target.full_name.strip().upper()


event.listen(WatchlistEntry, "before_insert", _normalise_watchlist)
event.listen(WatchlistEntry, "before_update", _normalise_watchlist)


# ---------------------------------------------------------------------------
# audit_ledger  (append-only, SHA-256 hash-chained event log)
# ---------------------------------------------------------------------------
class AuditLedgerEntry(Base):
    """
    Tamper-evident append-only audit log.

    Hash chain:
      payload_hash  = SHA256(canonical_json(payload))
      prev_record_hash = record_hash of the immediately preceding entry
                        (or genesis '0'*64 for sequence_num=1)
      record_hash   = SHA256(payload_hash + prev_record_hash + created_at ISO)

    Any retroactive tampering, deletion, or modification invalidates all
    subsequent record_hashes and is detected by verify_chain().

    Row-Level Security in Supabase must deny UPDATE and DELETE on this table
    for all roles — enforced at the Postgres layer, not just application layer.

    Changes from the old model:
    - `document_id` renamed to `scan_event_id` (FK to scan_events)
    - `payload` JSONB column added — stores the full event payload (not just
      its hash) for forensic replay without joining other tables.
    """
    __tablename__ = "audit_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Monotonically increasing chain order. BigInteger won't overflow at
    # millions of events/day for decades.
    sequence_num: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    # scan|officer_decision|face_verification|blacklist_add|chain_verify|...

    scan_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Full event payload — stored for forensic replay (hash alone is insufficient)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Hash chain fields — these make the ledger tamper-evident
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prev_record_hash: Mapped[str] = mapped_column(Text, nullable=False)
    record_hash: Mapped[str] = mapped_column(Text, nullable=False)

    officer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # CRITICAL: created_at is used in the record_hash computation.
    # server_default=func.now() ensures the DB clock sets this — not Python.
    # Python clock drift across servers would silently corrupt the hash chain.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan_event: Mapped["ScanEvent | None"] = relationship(back_populates="audit_entries")
    officer: Mapped["User | None"] = relationship(back_populates="audit_entries")

    __table_args__ = (
        # Per-document audit trail fetch
        Index("ix_audit_ledger_scan_event_id", "scan_event_id"),
        Index("ix_audit_ledger_officer_id", "officer_id"),
    )
