"""
Cross-Checkpoint Face Graph & Multi-Identity Analytics Engine.

CONCEPT:
A sophisticated traveler attempting identity fraud often exploits multiple border
checkpoints (e.g., crossing an airport with one passport, and a land border with a
second identity document or different name).

This engine:
  1. Queries all document records linked to a `person_cluster_id` across PostgreSQL.
  2. Analyzes pairwise identity attribute consistency:
     - Name discrepancies across documents (same face, different names).
     - Document number discrepancies (same face, different passport/ID numbers).
     - Date of birth & nationality conflicts.
  3. Evaluates physical transit feasibility (Impossible Travel / Velocity Check):
     - Flags rapid transit between distinct checkpoints within suspiciously short time windows.
  4. Integrates repeat-offender history to auto-escalate threat tiers.
  5. Computes a normalized cross-checkpoint fraud risk score (0.0–1.0).
  6. Persists detected fraud flags to the cross_checkpoint_flags table.

Changes from old version:
- _in_memory_cluster_store and register_cluster_document() removed.
- fetch_cluster_documents_from_db() updated to use new schema (ScanEvent, RiskResult).
- persist_flags_to_db() added — detected flags are now stored in DB.
"""

from datetime import datetime, timezone
import re
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.cross_checkpoint_service.core.repeat_offender import check_repeat_offender
from backend.cross_checkpoint_service.schemas.cross_checkpoint import (
    ClusterAnalysisResponse,
    ClusterDocument,
    ClusterHistoryResponse,
    CrossCheckpointFlag,
    CrossCheckpointFlagType,
)

logger = get_logger("cross_checkpoint_service.face_graph")

# In-memory registry fallback (used for tests and offline simulations)
_in_memory_cluster_store: dict[str, list[ClusterDocument]] = {}


def register_cluster_document(person_cluster_id: str, document: ClusterDocument) -> None:
    """Register document into in-memory store (for offline test simulations)."""
    if person_cluster_id not in _in_memory_cluster_store:
        _in_memory_cluster_store[person_cluster_id] = []
    # Replace existing if same document_id
    _in_memory_cluster_store[person_cluster_id] = [
        d for d in _in_memory_cluster_store[person_cluster_id] if d.document_id != document.document_id
    ]
    _in_memory_cluster_store[person_cluster_id].append(document)


def clear_cluster_registry() -> None:
    """Clear in-memory cluster registry."""
    _in_memory_cluster_store.clear()


def list_all_in_memory_clusters() -> dict[str, list[ClusterDocument]]:
    """Return all in-memory clusters."""
    return dict(_in_memory_cluster_store)


def get_in_memory_cluster_documents(person_cluster_id: str) -> list[ClusterDocument]:
    """Retrieve documents for cluster from in-memory store."""
    return list(_in_memory_cluster_store.get(person_cluster_id, []))




# ---------------------------------------------------------------------------
# Normalization Helpers
# ---------------------------------------------------------------------------

def _normalize_name(name_str: str | None) -> str:
    """Normalize a human name for comparison (remove titles, extra spaces, punctuation)."""
    if not name_str:
        return ""
    clean = name_str.upper().strip()
    clean = re.sub(r"\b(MR|MRS|MS|MISS|DR|PROF|SIR|MADAM)\b", "", clean)
    clean = re.sub(r"[^A-Z0-9\s]", " ", clean)
    words = sorted([w for w in clean.split() if len(w) > 0])
    return " ".join(words)


def _normalize_doc_number(doc_no: str | None) -> str:
    """Normalize passport/ID number."""
    if not doc_no:
        return ""
    return re.sub(r"[^A-Z0-9]", "", doc_no.upper().strip())


def _parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """Safely parse an ISO date/time string."""
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core Analysis Functions
# ---------------------------------------------------------------------------


async def fetch_cluster_documents_from_db(
    person_cluster_id: str,
    db: AsyncSession,
) -> list[ClusterDocument]:
    """
    Query PostgreSQL for all document records sharing this person_cluster_id.
    Uses the new schema: ScanEvent (not Document), RiskResult (not RiskScore),
    ExtractedField.scan_event_id (not document_id).
    """
    try:
        from backend.orchestrator.db.models import (
            ScanEvent,
            ExtractedField,
            FaceEmbedding,
            RiskResult,
        )

        cluster_uuid = uuid.UUID(person_cluster_id) if isinstance(person_cluster_id, str) else person_cluster_id

        stmt = (
            select(
                ScanEvent.id,
                ScanEvent.checkpoint_id,
                ScanEvent.uploaded_at,
                ScanEvent.document_type,
                RiskResult.score.label("risk_score"),
                RiskResult.band.label("risk_band"),
            )
            .join(FaceEmbedding, FaceEmbedding.scan_event_id == ScanEvent.id)
            .outerjoin(RiskResult, RiskResult.scan_event_id == ScanEvent.id)
            .where(FaceEmbedding.person_cluster_id == cluster_uuid)
            .order_by(ScanEvent.uploaded_at.asc())
        )

        result = await db.execute(stmt)
        rows = result.fetchall()

        cluster_docs: list[ClusterDocument] = []
        for r in rows:
            doc_id = str(r[0])
            # Fetch extracted fields for this scan
            field_stmt = select(ExtractedField.field_name, ExtractedField.field_value).where(
                ExtractedField.scan_event_id == r[0]
            )
            field_rows = (await db.execute(field_stmt)).fetchall()
            field_map = {name.lower(): val for name, val in field_rows if val}

            name_val = field_map.get("name") or field_map.get("full_name") or field_map.get("surname")
            doc_no = field_map.get("document_number") or field_map.get("doc_number") or field_map.get("passport_number")
            nat_val = field_map.get("nationality") or field_map.get("country")
            dob_val = field_map.get("date_of_birth") or field_map.get("dob")

            cluster_docs.append(
                ClusterDocument(
                    document_id=doc_id,
                    checkpoint_type=None,
                    checkpoint_id=str(r[1]) if r[1] else None,
                    checkpoint_name=None,
                    uploaded_at=r[2].isoformat() if r[2] else None,
                    document_type=r[3],
                    name=name_val,
                    document_number=doc_no,
                    nationality=nat_val,
                    date_of_birth=dob_val,
                    risk_score=float(r[4]) if r[4] is not None else None,
                    risk_band=str(r[5]) if r[5] else None,
                )
            )

        return cluster_docs

    except Exception as exc:
        logger.warning("Failed to query cluster documents from DB", error=str(exc))
        return []


async def persist_flags_to_db(
    flags: list[CrossCheckpointFlag],
    person_cluster_id: str,
    triggering_scan_event_id: str | None,
    db: AsyncSession,
) -> None:
    """
    Persist detected cross-checkpoint fraud flags to the cross_checkpoint_flags table.
    Previously, flags were computed per-request but never stored.
    """
    if not flags:
        return

    from backend.orchestrator.db.models import CrossCheckpointFlag as DBCrossCheckpointFlag

    try:
        cluster_uuid = uuid.UUID(person_cluster_id)
    except ValueError:
        return

    triggering_uuid = None
    if triggering_scan_event_id:
        try:
            triggering_uuid = uuid.UUID(triggering_scan_event_id)
        except ValueError:
            pass

    for flag in flags:
        db_flag = DBCrossCheckpointFlag(
            id=uuid.uuid4(),
            person_cluster_id=cluster_uuid,
            triggering_scan_event_id=triggering_uuid,
            flag_type=flag.flag_type.value if hasattr(flag.flag_type, "value") else str(flag.flag_type),
            severity=flag.severity,
            detail=flag.detail,
            related_scan_event_ids=flag.related_document_ids if hasattr(flag, "related_document_ids") else None,
        )
        db.add(db_flag)

    try:
        await db.commit()
        logger.info("cross_checkpoint_flags_persisted", count=len(flags), cluster_id=person_cluster_id)
    except Exception as exc:
        logger.warning("Failed to persist cross-checkpoint flags", error=str(exc))
        await db.rollback()



def evaluate_cluster_graph(
    person_cluster_id: str,
    documents: list[ClusterDocument],
    current_document_id: str | None = None,
    current_risk_band: str | None = "low",
) -> tuple[list[CrossCheckpointFlag], float, bool, bool, str | None, str]:
    """
    Perform full anomaly detection on a collection of cluster documents.

    Returns:
        flags: list of detected CrossCheckpointFlag
        cross_checkpoint_risk: float (0.0 to 1.0)
        repeat_offender_hit: bool
        escalate_risk_tier: bool
        escalated_risk_band: str | None
        summary: str
    """
    flags: list[CrossCheckpointFlag] = []
    risk_contributions: list[float] = []

    if len(documents) <= 1:
        # Single document in cluster — check if that single document was a repeat offense
        (
            rep_hit,
            hp_band,
            hp_score,
            esc_tier,
            esc_band,
            prior_reasons,
        ) = check_repeat_offender(documents, current_document_id, current_risk_band)

        if rep_hit:
            flags.append(
                CrossCheckpointFlag(
                    flag_type=CrossCheckpointFlagType.REPEAT_OFFENDER,
                    severity="critical" if hp_band == "critical" else "high",
                    detail=f"Prior severe offenses on record: {'; '.join(prior_reasons)}",
                    related_document_ids=[d.document_id for d in documents],
                )
            )
            risk_contributions.append(0.75)

        total_risk = max(risk_contributions, default=0.0)
        summary = (
            f"Cluster contains 1 document scan. Repeat offender: {rep_hit}."
            if rep_hit
            else "Clean single-document cluster with no cross-checkpoint anomalies."
        )
        return flags, total_risk, rep_hit, esc_tier, esc_band, summary

    # ── 1. Name Mismatch Check ────────────────────────────────────────────────
    distinct_names: dict[str, list[str]] = {}
    for d in documents:
        if d.name:
            norm = _normalize_name(d.name)
            if norm:
                if norm not in distinct_names:
                    distinct_names[norm] = []
                distinct_names[norm].append(d.document_id)

    if len(distinct_names) > 1:
        name_list_str = " vs ".join([f"'{d.name}'" for d in documents if d.name])
        flag = CrossCheckpointFlag(
            flag_type=CrossCheckpointFlagType.NAME_MISMATCH,
            severity="critical",
            detail=(
                f"MULTI-IDENTITY DETECTED: Biometric face cluster is associated with "
                f"{len(distinct_names)} conflicting holder names across scans: ({name_list_str}). "
                "Strong indicator of identity alteration or fraudulent document acquisition."
            ),
            related_document_ids=[d.document_id for d in documents],
        )
        flags.append(flag)
        risk_contributions.append(0.85)

    # ── 2. Document Number Mismatch Check ─────────────────────────────────────
    distinct_doc_numbers: dict[str, list[str]] = {}
    for d in documents:
        if d.document_number:
            norm_no = _normalize_doc_number(d.document_number)
            if norm_no:
                if norm_no not in distinct_doc_numbers:
                    distinct_doc_numbers[norm_no] = []
                distinct_doc_numbers[norm_no].append(d.document_id)

    if len(distinct_doc_numbers) > 1:
        doc_no_str = ", ".join([f"'{d.document_number}'" for d in documents if d.document_number])
        flag = CrossCheckpointFlag(
            flag_type=CrossCheckpointFlagType.DOCUMENT_NUMBER_MISMATCH,
            severity="high",
            detail=(
                f"MULTIPLE TRAVEL DOCUMENTS: Same individual observed holding "
                f"{len(distinct_doc_numbers)} distinct document numbers: ({doc_no_str})."
            ),
            related_document_ids=[d.document_id for d in documents],
        )
        flags.append(flag)
        risk_contributions.append(0.65)

    # ── 3. Date of Birth & Nationality Mismatch Check ─────────────────────────
    distinct_dobs = {d.date_of_birth.strip() for d in documents if d.date_of_birth}
    if len(distinct_dobs) > 1:
        flag = CrossCheckpointFlag(
            flag_type=CrossCheckpointFlagType.DOB_MISMATCH,
            severity="high",
            detail=f"Conflicting dates of birth registered in cluster: {', '.join(distinct_dobs)}.",
            related_document_ids=[d.document_id for d in documents],
        )
        flags.append(flag)
        risk_contributions.append(0.60)

    distinct_nats = {d.nationality.strip().upper() for d in documents if d.nationality}
    if len(distinct_nats) > 1:
        flag = CrossCheckpointFlag(
            flag_type=CrossCheckpointFlagType.NATIONALITY_MISMATCH,
            severity="medium",
            detail=f"Multiple declared nationalities registered in cluster: {', '.join(distinct_nats)}.",
            related_document_ids=[d.document_id for d in documents],
        )
        flags.append(flag)
        risk_contributions.append(0.40)

    # ── 4. Impossible Travel / Velocity Anomaly Check ────────────────────────
    # Sort docs by timestamp
    dated_docs = [
        (d, _parse_iso_datetime(d.uploaded_at))
        for d in documents
        if _parse_iso_datetime(d.uploaded_at) is not None
    ]
    dated_docs.sort(key=lambda item: item[1])

    impossible_travel_events = []
    for i in range(len(dated_docs) - 1):
        doc1, t1 = dated_docs[i]
        doc2, t2 = dated_docs[i + 1]

        # Sighting at different checkpoint types or different checkpoint IDs
        diff_type = doc1.checkpoint_type and doc2.checkpoint_type and (doc1.checkpoint_type != doc2.checkpoint_type)
        diff_id = doc1.checkpoint_id and doc2.checkpoint_id and (doc1.checkpoint_id != doc2.checkpoint_id)

        if diff_type or diff_id:
            delta_seconds = abs((t2 - t1).total_seconds())
            delta_minutes = delta_seconds / 60.0

            # Threshold: distinct checkpoints within < 2 hours (120 min) is physically impossible
            if delta_minutes < 120.0:
                loc1 = doc1.checkpoint_name or doc1.checkpoint_type or doc1.checkpoint_id or "Checkpoint A"
                loc2 = doc2.checkpoint_name or doc2.checkpoint_type or doc2.checkpoint_id or "Checkpoint B"
                impossible_travel_events.append(
                    f"Sightings at {loc1} and {loc2} within {delta_minutes:.0f} minutes (delta < 2h threshold)"
                )

    if impossible_travel_events:
        flag = CrossCheckpointFlag(
            flag_type=CrossCheckpointFlagType.IMPOSSIBLE_TRAVEL,
            severity="critical",
            detail=(
                f"IMPOSSIBLE TRAVEL VELOCITY DETECTED: {'; '.join(impossible_travel_events)}. "
                "Individual could not physically travel between these checkpoints in the recorded timeframe."
            ),
            related_document_ids=[d.document_id for d in documents],
        )
        flags.append(flag)
        risk_contributions.append(0.90)

    # ── 5. Repeat Offender Check ──────────────────────────────────────────────
    (
        rep_hit,
        hp_band,
        hp_score,
        esc_tier,
        esc_band,
        prior_reasons,
    ) = check_repeat_offender(documents, current_document_id, current_risk_band)

    if rep_hit:
        flags.append(
            CrossCheckpointFlag(
                flag_type=CrossCheckpointFlagType.REPEAT_OFFENDER,
                severity="critical" if hp_band == "critical" else "high",
                detail=f"Prior severe offenses on record: {'; '.join(prior_reasons)}",
                related_document_ids=[d.document_id for d in documents],
            )
        )
        risk_contributions.append(0.75)

    # ── 6. Aggregate Composite Risk Score ─────────────────────────────────────
    if risk_contributions:
        # Max signal + weighted average of secondary signals
        max_c = max(risk_contributions)
        mean_c = sum(risk_contributions) / len(risk_contributions)
        cross_checkpoint_risk = float(min(1.0, 0.7 * max_c + 0.3 * mean_c))
    else:
        cross_checkpoint_risk = 0.0

    # ── 7. Summary Narrative ──────────────────────────────────────────────────
    if flags:
        flag_types_str = ", ".join([f.flag_type.value for f in flags])
        summary = (
            f"Cross-checkpoint alert: {len(flags)} risk signal(s) detected across {len(documents)} "
            f"linked documents ({flag_types_str}). Risk contribution: {cross_checkpoint_risk:.2f}."
        )
    else:
        summary = f"Consistent identity history across {len(documents)} linked document scans."

    logger.info(
        "Cluster evaluation complete",
        cluster_id=person_cluster_id,
        documents_count=len(documents),
        flags_count=len(flags),
        risk=cross_checkpoint_risk,
        repeat_offender=rep_hit,
    )

    return (
        flags,
        round(cross_checkpoint_risk, 3),
        rep_hit,
        esc_tier,
        esc_band,
        summary,
    )


async def analyze_cluster(
    person_cluster_id: str,
    current_doc: ClusterDocument | None = None,
    current_risk_band: str | None = "low",
    db: AsyncSession | None = None,
    seed_documents: list[ClusterDocument] | None = None,
) -> ClusterAnalysisResponse:
    """
    Main entrypoint: evaluate all cross-checkpoint anomalies for a cluster.
    """
    # 1. Gather all documents
    if seed_documents:
        all_docs = list(seed_documents)
    elif db is not None:
        all_docs = await fetch_cluster_documents_from_db(person_cluster_id, db)
    else:
        all_docs = get_in_memory_cluster_documents(person_cluster_id)

    # Merge current document if provided and not present
    if current_doc:
        if not any(d.document_id == current_doc.document_id for d in all_docs):
            all_docs.append(current_doc)

    (
        flags,
        cc_risk,
        rep_hit,
        esc_tier,
        esc_band,
        summary,
    ) = evaluate_cluster_graph(
        person_cluster_id=person_cluster_id,
        documents=all_docs,
        current_document_id=current_doc.document_id if current_doc else None,
        current_risk_band=current_risk_band,
    )

    prior_high_or_critical = sum(
        1 for d in all_docs
        if (d.risk_band or "").lower() in ["high", "critical"]
        and (not current_doc or d.document_id != current_doc.document_id)
    )

    return ClusterAnalysisResponse(
        person_cluster_id=person_cluster_id,
        documents_in_cluster=all_docs,
        flags=flags,
        cross_checkpoint_risk=cc_risk,
        repeat_offender_hit=rep_hit,
        escalate_risk_tier=esc_tier,
        original_risk_band=current_risk_band,
        escalated_risk_band=esc_band,
        prior_critical_or_high_count=prior_high_or_critical,
        detail=summary,
    )


async def get_cluster_history(
    person_cluster_id: str,
    db: AsyncSession | None = None,
) -> ClusterHistoryResponse:
    """
    Retrieve full cross-checkpoint historical dossier for a person cluster.
    """
    if db is not None:
        docs = await fetch_cluster_documents_from_db(person_cluster_id, db)
    else:
        docs = get_in_memory_cluster_documents(person_cluster_id)

    (
        flags,
        cc_risk,
        rep_hit,
        esc_tier,
        esc_band,
        summary,
    ) = evaluate_cluster_graph(
        person_cluster_id=person_cluster_id,
        documents=docs,
    )

    highest_score = max([d.risk_score for d in docs if d.risk_score is not None], default=None)
    highest_band = next(
        (b for b in ["critical", "high", "medium", "low"] if any((d.risk_band or "").lower() == b for d in docs)),
        None,
    )

    return ClusterHistoryResponse(
        person_cluster_id=person_cluster_id,
        total_documents=len(docs),
        documents=docs,
        flags=flags,
        cross_checkpoint_risk=cc_risk,
        repeat_offender_hit=rep_hit,
        highest_prior_risk_band=highest_band,
        highest_prior_risk_score=highest_score,
        recommended_escalation=esc_tier,
        summary=summary,
    )
