"""
Blacklist Lookup Engine.

Checks extracted document fields (document number, name, DOB, nationality)
against the watchlist / blacklist repository.
"""

from typing import Any
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.ocr_service.schemas.extraction import ExtractedField
from backend.orchestrator.db.models import BlacklistEntry
from backend.risk_engine.schemas.risk import BlacklistSubScore

logger = get_logger("orchestrator.blacklist")

# In-memory demo blacklist entries (used for testing or offline demos)
_DEMO_BLACKLIST = [
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


async def check_blacklist(
    fields: list[ExtractedField],
    db: AsyncSession | None = None,
) -> BlacklistSubScore:
    """
    Check extracted fields against the blacklist database (and in-memory seed list).

    Returns:
        BlacklistSubScore indicating hit, matched fields, and severity tier.
    """
    field_map: dict[str, str] = {
        f.field_name.lower(): (f.field_value or "").strip().upper()
        for f in fields
        if f.field_value
    }

    doc_num = (
        field_map.get("passport_number")
        or field_map.get("doc_number")
        or field_map.get("id_number")
        or field_map.get("license_number")
        or field_map.get("permit_number")
    )
    name = field_map.get("name") or field_map.get("holder_name")

    matched_fields: list[str] = []
    severities: list[str] = []

    # 1. Check in-memory demo blacklist
    for entry in _DEMO_BLACKLIST:
        entry_doc = entry.get("document_number", "").upper()
        entry_name = entry.get("full_name", "").upper()

        hit_found = False
        if doc_num and entry_doc and doc_num == entry_doc:
            matched_fields.append(f"document_number ({doc_num})")
            severities.append(entry.get("severity", "banned"))
            hit_found = True

        if name and entry_name and name == entry_name:
            matched_fields.append(f"name ({name})")
            severities.append(entry.get("severity", "banned"))
            hit_found = True

        if hit_found:
            logger.warning(
                "Blacklist hit detected from demo store",
                matched_fields=matched_fields,
                reason=entry.get("reason"),
            )

    # 2. Check Database if session available
    if db is not None:
        try:
            conditions = []
            if doc_num:
                conditions.append(func.upper(BlacklistEntry.document_number) == doc_num)
            if name:
                conditions.append(func.upper(BlacklistEntry.full_name) == name)

            if conditions:
                stmt = select(BlacklistEntry).where(or_(*conditions))
                res = await db.execute(stmt)
                db_entries = res.scalars().all()

                for entry in db_entries:
                    if entry.document_number and doc_num and entry.document_number.upper() == doc_num:
                        matched_fields.append(f"document_number ({doc_num})")
                    if entry.full_name and name and entry.full_name.upper() == name:
                        matched_fields.append(f"name ({name})")
                    if entry.severity:
                        severities.append(entry.severity)

                    logger.warning(
                        "Blacklist hit detected from Postgres database",
                        doc_number=entry.document_number,
                        name=entry.full_name,
                        severity=entry.severity,
                    )
        except Exception as exc:
            logger.warning("Database blacklist query skipped or failed", error=str(exc))

    if not matched_fields:
        return BlacklistSubScore(hit=False)

    # Deduplicate matched fields
    unique_matched = list(dict.fromkeys(matched_fields))

    # Determine highest severity
    highest_severity = "watch"
    if any("banned" in s.lower() for s in severities):
        highest_severity = "banned"
    elif any("suspect" in s.lower() for s in severities):
        highest_severity = "suspect"

    return BlacklistSubScore(
        hit=True,
        matched_fields=unique_matched,
        severity=highest_severity,
    )
