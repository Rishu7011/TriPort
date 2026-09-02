"""
Blacklist Lookup Engine — database-backed via watchlist_entries table.

Replaces the in-memory _DEMO_BLACKLIST with queries to Supabase.
Field normalisation (UPPERCASE + STRIP) is applied to all query inputs
before the DB query — this is the key fix for Q1 (real OCR output).

Normalisation strategy:
  - OCR may produce "  Viktor Korzhov  " or "viktor korzhov"
  - watchlist_entries stores "VIKTOR KORZHOV" (enforced by ORM event listener)
  - This function normalises its query inputs to UPPERCASE+STRIP so both sides match
  - DB lookup uses exact TEXT equality on the normalised columns (fast B-tree index)

Fallback: if no db session is provided (test suites, offline demos), falls
back to an in-memory seed list so the demo remains functional without Supabase.
"""

from __future__ import annotations

from sqlalchemy import or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import ExtractedField
from backend.orchestrator.db.models import WatchlistEntry
from backend.risk_engine.schemas.risk import BlacklistSubScore

logger = get_logger("orchestrator.blacklist")


# ---------------------------------------------------------------------------
# Offline fallback (used when db is None — test suites / offline demos)
# ---------------------------------------------------------------------------
_OFFLINE_BLACKLIST = [
    {
        "document_number": "X9999999",
        "full_name": "VIKTOR KORZHOV",
        "severity": "banned",
        "reason": "Interpol Red Notice - Document Forgery & Identity Theft",
    },
    {
        "document_number": "B1234567",
        "full_name": "JOHN DOE SUSPECT",
        "severity": "suspect",
        "reason": "Active Border Alert - Cross-Border Smuggling",
    },
]


def _normalise(value: str | None) -> str | None:
    """UPPERCASE + STRIP normalisation for blacklist field comparison."""
    if value is None:
        return None
    result = value.strip().upper()
    return result if result else None


async def check_blacklist(
    fields: list[ExtractedField],
    db: AsyncSession | None = None,
) -> BlacklistSubScore:
    """
    Check extracted document fields against the watchlist_entries table.

    Normalisation applied to both query inputs and stored values ensures
    case/whitespace differences in OCR output never cause false negatives.

    Args:
        fields: Extracted OCR fields from the document.
        db: Async SQLAlchemy session. If None, falls back to offline demo list.

    Returns:
        BlacklistSubScore indicating hit status, matched fields, and severity.
    """
    # Build normalised field map from OCR output
    field_map: dict[str, str] = {
        f.field_name.lower(): _normalise(f.field_value) or ""
        for f in fields
        if f.field_value
    }

    # Normalise the document number (try all common field names)
    raw_doc_num = (
        field_map.get("passport_number")
        or field_map.get("doc_number")
        or field_map.get("id_number")
        or field_map.get("license_number")
        or field_map.get("permit_number")
    )
    doc_num = _normalise(raw_doc_num)  # already uppercase from field_map, but re-normalise for safety

    raw_name = field_map.get("name") or field_map.get("holder_name")
    name = _normalise(raw_name)

    matched_fields: list[str] = []
    severities: list[str] = []

    if db is not None:
        # ── Database lookup ─────────────────────────────────────────────────
        try:
            conditions = []
            if doc_num:
                conditions.append(WatchlistEntry.document_number == doc_num)
            if name:
                conditions.append(WatchlistEntry.full_name == name)

            if not conditions:
                return BlacklistSubScore(hit=False)

            stmt = (
                select(WatchlistEntry)
                .where(
                    and_(
                        WatchlistEntry.is_active.is_(True),
                        or_(*conditions),
                    )
                )
            )
            result = await db.execute(stmt)
            hits = result.scalars().all()

            for entry in hits:
                if doc_num and entry.document_number == doc_num:
                    matched_fields.append(f"document_number ({doc_num})")
                    severities.append(entry.severity)
                if name and entry.full_name == name:
                    matched_fields.append(f"name ({name})")
                    severities.append(entry.severity)

            if matched_fields:
                logger.warning(
                    "watchlist_hit_detected",
                    matched_fields=matched_fields,
                    hits_count=len(hits),
                )

        except Exception as exc:
            logger.warning("watchlist_db_query_failed_using_offline", error=str(exc))
            return _check_offline(doc_num=doc_num, name=name)

    else:
        # ── Offline fallback ─────────────────────────────────────────────────
        logger.debug("watchlist_check_offline_no_db_session")
        return _check_offline(doc_num=doc_num, name=name)

    if not matched_fields:
        return BlacklistSubScore(hit=False)

    # Deduplicate matched fields (same document might hit on both doc_num and name)
    unique_matched = list(dict.fromkeys(matched_fields))
    highest_severity = _highest_severity(severities)

    return BlacklistSubScore(
        hit=True,
        matched_fields=unique_matched,
        severity=highest_severity,
    )


def _check_offline(doc_num: str | None, name: str | None) -> BlacklistSubScore:
    """Check against the in-memory offline fallback list."""
    matched_fields: list[str] = []
    severities: list[str] = []

    for entry in _OFFLINE_BLACKLIST:
        entry_doc = _normalise(entry.get("document_number"))
        entry_name = _normalise(entry.get("full_name"))

        if doc_num and entry_doc and doc_num == entry_doc:
            matched_fields.append(f"document_number ({doc_num})")
            severities.append(entry.get("severity", "banned"))

        if name and entry_name and name == entry_name:
            matched_fields.append(f"name ({name})")
            severities.append(entry.get("severity", "banned"))

    if not matched_fields:
        return BlacklistSubScore(hit=False)

    return BlacklistSubScore(
        hit=True,
        matched_fields=list(dict.fromkeys(matched_fields)),
        severity=_highest_severity(severities),
    )


def _highest_severity(severities: list[str]) -> str:
    if any("banned" in s.lower() for s in severities):
        return "banned"
    if any("suspect" in s.lower() for s in severities):
        return "suspect"
    return "watch"
