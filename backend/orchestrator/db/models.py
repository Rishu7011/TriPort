"""
DB Models — SQLAlchemy ORM definitions for all Phase 1–4 tables.

CONCEPT: Each class here maps 1:1 to a Postgres table.
SQLAlchemy handles the translation between Python ↔ SQL.

We use the "declarative" style:
  - `Base` is the registry all models register with
  - Each model inherits from `Base`
  - `__tablename__` tells SQLAlchemy the exact Postgres table name
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector  # VECTOR type for face embeddings
from sqlalchemy import (
    UUID,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    All models inherit from this.
    When Alembic runs migrations, it scans every subclass of Base
    to know what tables should exist.
    """
    pass


# ---------------------------------------------------------------------------
# documents — one row per uploaded document scan
# ---------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    # UUID primary key: globally unique, better than sequential integers
    # for distributed systems and security (can't enumerate IDs)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # passport | visa | national_id | driving_license | permit

    # MinIO object key — we don't store the image in Postgres, just a pointer
    # Binary blobs in a relational DB are slow and expensive; MinIO is for that
    image_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # server_default=func.now() means Postgres sets this, not Python
    # safer: avoids clock skew if multiple app servers exist
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    checkpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Relationships — SQLAlchemy will JOIN these automatically when accessed
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    validation_results: Mapped[list["ValidationResult"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tampering_results: Mapped[list["TamperingResult"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    face_embedding: Mapped["FaceEmbedding | None"] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    risk_score: Mapped["RiskScore | None"] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# extracted_fields — OCR output, one row per field per document
# ---------------------------------------------------------------------------
class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    # Composite primary key: a document can have many fields,
    # but each (document_id, field_name) pair is unique
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    field_name: Mapped[str] = mapped_column(Text, primary_key=True)
    # e.g. "name", "passport_number", "date_of_expiry"

    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # confidence: 0.0 → 1.0 — how sure the OCR model is
    # Used to decide: keep OCR result, or fall back to LLM
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="extracted_fields")


# ---------------------------------------------------------------------------
# validation_results — one row per rule per document
# ---------------------------------------------------------------------------
class ValidationResult(Base):
    __tablename__ = "validation_results"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rule_name: Mapped[str] = mapped_column(Text, primary_key=True)
    # e.g. "expiry_not_passed", "passport_number_format"

    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Human-readable explanation: "Date 2019-01-01 is before today 2025-08-29"
    # This is what the risk engine uses for the "reasons" output
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="validation_results")


# ---------------------------------------------------------------------------
# tampering_results — one row per check type per document (Phase 2)
# ---------------------------------------------------------------------------
class TamperingResult(Base):
    __tablename__ = "tampering_results"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    check_type: Mapped[str] = mapped_column(Text, primary_key=True)
    # ela | metadata | boundary | stamp_match | cnn

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # JSON column: flexible, stores check-specific detail (e.g. heatmap URL for ELA)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="tampering_results")


# ---------------------------------------------------------------------------
# face_embeddings — pgvector: semantic vector search (Phase 2)
# ---------------------------------------------------------------------------
class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
    )

    # VECTOR(512): 512-dimensional float array — the face's "fingerprint"
    # pgvector lets you do: SELECT ... ORDER BY embedding <=> query_vector LIMIT 5
    # This is an approximate nearest-neighbor search — finds faces that look similar
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=True)

    # Links faces that likely belong to the same person across different documents
    # Used to detect "same person, multiple identities" fraud
    person_cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    document: Mapped["Document"] = relationship(back_populates="face_embedding")


# ---------------------------------------------------------------------------
# risk_scores — Phase 3 output
# ---------------------------------------------------------------------------
class RiskScore(Base):
    __tablename__ = "risk_scores"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    band: Mapped[str | None] = mapped_column(Text, nullable=True)
    # low | medium | high | critical

    # JSON array of human-readable reasons: ["MRZ checksum failed on DOB", ...]
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="risk_score")


# ---------------------------------------------------------------------------
# audit_ledger — append-only, hash-chained (Phase 4)
# ---------------------------------------------------------------------------
class AuditLedgerEntry(Base):
    __tablename__ = "audit_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # sequence_num: monotonically increasing — the chain order
    # BigInteger: won't overflow even at millions of events/day for years
    sequence_num: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    # scan | officer_decision | sync | chain_verify

    # Hash chain fields — this is what makes it tamper-evident
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 of the event payload JSON

    prev_record_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # hash of the previous row — links the chain

    record_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256(payload_hash + prev_record_hash + timestamp)
    # Changing ANY prior row invalidates ALL subsequent record_hashes

    officer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
