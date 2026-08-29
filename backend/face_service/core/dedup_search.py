"""
1:N Biometric Deduplication & Person Clustering Engine.

CONCEPT:
A primary threat at border checkpoints is "same person, multiple identities"
(e.g., a person obtaining fraudulent passports under different names/nationalities).
1:N deduplication compares a new face embedding against all previously indexed
identities in PostgreSQL (via pgvector cosine distance).

This module:
  1. Searches nearest neighbors in the vector index for cosine similarity >= threshold (default: 0.65).
  2. If matching identity records exist, assigns the same `person_cluster_id` to link all fraudulent aliases.
  3. If no match exists, creates a new unique `person_cluster_id` (UUID).
  4. Provides in-memory vector scanning fallback for local tests.
"""

import uuid
from typing import Any
import numpy as np

from backend.logging_config import get_logger
from backend.face_service.core.one_to_one import compute_cosine_similarity
from backend.face_service.schemas.face import DedupHit

logger = get_logger("face_service.dedup_search")

DEDUP_SIMILARITY_THRESHOLD = 0.65

# In-memory mock store for testing / offline operation
_in_memory_embeddings: list[dict[str, Any]] = []


def register_in_memory_embedding(
    document_id: str,
    embedding: list[float],
    person_cluster_id: str | None = None,
) -> str:
    """Helper for testing: store an embedding in the temporary in-memory registry."""
    cluster_id = person_cluster_id or str(uuid.uuid4())
    _in_memory_embeddings.append({
        "document_id": document_id,
        "embedding": embedding,
        "person_cluster_id": cluster_id,
    })
    return cluster_id


def clear_in_memory_embeddings():
    """Clear in-memory embeddings store."""
    _in_memory_embeddings.clear()


async def search_duplicates(
    embedding: list[float],
    db_session: Any | None = None,
    threshold: float = DEDUP_SIMILARITY_THRESHOLD,
    current_doc_id: str | None = None,
) -> tuple[bool, list[DedupHit], str, str]:
    """
    Search 1:N stored face embeddings for duplicate identity matches.

    Args:
        embedding: 512-dim unit vector of the face being scanned.
        db_session: Optional async SQLAlchemy DB session connected to Postgres pgvector.
        threshold: Cosine similarity cutoff for identity duplication (default: 0.65).
        current_doc_id: Optional ID of the document currently being processed to exclude self.

    Returns:
        tuple: (
            has_duplicates: bool,
            hits: list[DedupHit],
            assigned_cluster_id: str,
            detail: str
        )
    """
    hits: list[DedupHit] = []
    assigned_cluster_id: str | None = None

    # 1. If DB session provided, query Postgres pgvector
    if db_session is not None:
        try:
            from sqlalchemy import text

            # Cosine distance in pgvector: <=> operator.
            # cosine_similarity = 1.0 - cosine_distance
            max_distance = 1.0 - threshold
            query = text(
                """
                SELECT document_id, person_cluster_id, (embedding <=> :vec) AS distance
                FROM face_embeddings
                WHERE (embedding <=> :vec) <= :max_dist
                ORDER BY distance ASC
                LIMIT 10
                """
            )
            # In pgvector string format: '[0.1, 0.2, ...]'
            vec_str = f"[{','.join(str(x) for x in embedding)}]"
            result = await db_session.execute(query, {"vec": vec_str, "max_dist": max_distance})
            rows = result.fetchall()

            for r in rows:
                doc_id = str(r[0])
                if current_doc_id and doc_id == current_doc_id:
                    continue
                cluster_id = str(r[1]) if r[1] else None
                sim = 1.0 - float(r[2])
                hits.append(DedupHit(document_id=doc_id, similarity=round(sim, 4), person_cluster_id=cluster_id))
                if assigned_cluster_id is None and cluster_id:
                    assigned_cluster_id = cluster_id
        except Exception as e:
            logger.debug("pgvector database query fallback to in-memory store", error=str(e))

    # 2. Check in-memory store (for testing or standalone service mode)
    if not hits and _in_memory_embeddings:
        for item in _in_memory_embeddings:
            doc_id = item["document_id"]
            if current_doc_id and doc_id == current_doc_id:
                continue
            sim = compute_cosine_similarity(embedding, item["embedding"])
            if sim >= threshold:
                cluster_id = item.get("person_cluster_id")
                hits.append(DedupHit(document_id=doc_id, similarity=round(sim, 4), person_cluster_id=cluster_id))
                if assigned_cluster_id is None and cluster_id:
                    assigned_cluster_id = cluster_id

    # 3. Resolve Person Cluster ID
    has_duplicates = len(hits) > 0
    if not assigned_cluster_id:
        assigned_cluster_id = str(uuid.uuid4())

    if has_duplicates:
        detail = (
            f"MULTI-IDENTITY ALERT: Face matches {len(hits)} previously registered document(s). "
            f"Top match similarity: {hits[0].similarity:.1%}. Cluster ID assigned: {assigned_cluster_id}."
        )
    else:
        detail = "No duplicate identities found across historical document registry."

    logger.info("1:N dedup search completed", has_duplicates=has_duplicates, hits_count=len(hits), cluster_id=assigned_cluster_id)
    return has_duplicates, hits, assigned_cluster_id, detail
