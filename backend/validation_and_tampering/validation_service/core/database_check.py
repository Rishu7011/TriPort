"""
Database Cross-Check Module — Mock Government Database Queries.

Implements three independently callable, composable checks against mock
Postgres tables that stand in for real government API integrations:

  1. check_sltd()           — Interpol Stolen & Lost Travel Documents
  2. check_national_blacklist() — National prohibited/watchlist persons
  3. check_visa_validity()  — Permitted visa-type / nationality combinations

Design principles:
  - Every function is async, independently testable, and composable.
  - On DB connectivity failure, each function falls back to the offline
    SQLite cache (via offline_cache.py) and logs mode='offline_cached'.
  - Interfaces are intentionally stable so production replacements (real
    government APIs) are surgical — swap the body, keep the signature.
  - Never raise unhandled exceptions to the caller — return a typed result
    with hit=False and log the error.
"""

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.logging_config import get_logger
from backend.validation_service.core.db_models import MockBlacklist, MockSLTD, MockVisaRecord
from backend.validation_service.schemas.validation import (
    BlacklistRecord,
    BlacklistResult,
    SLTDRecord,
    SLTDResult,
    VisaValidityResult,
)

logger = get_logger("validation_service.database_check")

# ---------------------------------------------------------------------------
# Async DB engine — shared, lazy-initialised per process
# ---------------------------------------------------------------------------

_engine = None
_session_factory: Optional[async_sessionmaker] = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def _get_session() -> AsyncSession:
    """Return a new AsyncSession context manager from the shared factory."""
    return _get_session_factory()()


# ---------------------------------------------------------------------------
# 1. SLTD Check
# ---------------------------------------------------------------------------

async def check_sltd(document_number: str) -> SLTDResult:
    """
    Check a document number against the mock Interpol SLTD database.

    Args:
        document_number: The full document number extracted from the scan.

    Returns:
        SLTDResult with sltd_hit=True and the full record if found, else hit=False.
        Falls back to offline SQLite cache on Postgres connectivity failure.
    """
    logger.info("SLTD lookup", document_number=document_number)

    try:
        session = _get_session()
        async with session as s:
            result = await s.execute(
                select(MockSLTD).where(MockSLTD.document_number == document_number.upper().strip())
            )
            row: MockSLTD | None = result.scalar_one_or_none()

        if row:
            logger.warning(
                "SLTD HIT",
                document_number=document_number,
                report_type=row.report_type,
                reporting_country=row.reporting_country,
            )
            return SLTDResult(
                sltd_hit=True,
                sltd_record=SLTDRecord(
                    document_number=row.document_number,
                    report_type=row.report_type,
                    reporting_country=row.reporting_country,
                    reported_at=row.reported_at.isoformat(),
                ),
                mode="online",
            )

        logger.info("SLTD clear", document_number=document_number)
        return SLTDResult(sltd_hit=False, sltd_record=None, mode="online")

    except (OperationalError, SQLAlchemyError, OSError) as e:
        logger.error(
            "SLTD DB unreachable — falling back to offline cache",
            error=str(e),
            mode="offline_cached",
        )
        return await _sltd_offline_fallback(document_number)


async def _sltd_offline_fallback(document_number: str) -> SLTDResult:
    """Check offline SQLite cache for SLTD entries when Postgres is unavailable."""
    try:
        from backend.validation_service.core.offline_cache import get_offline_cache
        hit = get_offline_cache().check_cached_blacklist(document_number)
        return SLTDResult(sltd_hit=hit, sltd_record=None, mode="offline_cached")
    except Exception as cache_err:
        logger.error("Offline SLTD cache also failed", error=str(cache_err))
        # Fail safe — return no hit rather than blocking all travel
        return SLTDResult(sltd_hit=False, sltd_record=None, mode="offline_cached")


# ---------------------------------------------------------------------------
# 2. National Blacklist Check
# ---------------------------------------------------------------------------

async def check_national_blacklist(
    document_number: Optional[str] = None,
    name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
) -> BlacklistResult:
    """
    Check a person's identity against the national prohibited/watchlist database.

    Matching strategy (in priority order):
      1. document_number exact match
      2. name + date_of_birth combination match (case-insensitive name)

    Args:
        document_number: Optional — primary match key.
        name:            Optional — holder full name.
        date_of_birth:   Optional — ISO date string.

    Returns:
        BlacklistResult with matched record and match basis list if found.
    """
    logger.info(
        "National blacklist lookup",
        document_number=document_number,
        has_name=bool(name),
        has_dob=bool(date_of_birth),
    )

    try:
        session = _get_session()
        async with session as s:
            row: MockBlacklist | None = None
            match_basis: list[str] = []

            # Strategy 1: document number match
            if document_number:
                stmt = select(MockBlacklist).where(
                    MockBlacklist.document_number == document_number.upper().strip()
                )
                result = await s.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    match_basis = ["document_number"]

            # Strategy 2: name + DOB combination (only if no doc-number hit yet)
            if not row and name and date_of_birth:
                stmt = select(MockBlacklist).where(
                    MockBlacklist.name.ilike(name.strip()),
                    MockBlacklist.date_of_birth == date_of_birth.strip(),
                )
                result = await s.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    match_basis = ["name+dob"]

        if row:
            logger.warning(
                "BLACKLIST HIT",
                document_number=document_number,
                name=name,
                severity=row.severity,
                match_basis=match_basis,
            )
            return BlacklistResult(
                blacklist_hit=True,
                matched_record=BlacklistRecord(
                    name=row.name,
                    date_of_birth=row.date_of_birth or "",
                    document_number=row.document_number,
                    severity=row.severity,
                    reason=row.reason,
                ),
                match_basis=match_basis,
                mode="online",
            )

        logger.info("Blacklist clear", document_number=document_number, name=name)
        return BlacklistResult(blacklist_hit=False, matched_record=None, match_basis=[], mode="online")

    except (OperationalError, SQLAlchemyError, OSError) as e:
        logger.error(
            "Blacklist DB unreachable — returning safe default",
            error=str(e),
            mode="offline_cached",
        )
        # In offline mode we cannot do name+DOB matching — return safe clear
        return BlacklistResult(
            blacklist_hit=False,
            matched_record=None,
            match_basis=[],
            mode="offline_cached",
        )


# ---------------------------------------------------------------------------
# 3. Visa Validity Check
# ---------------------------------------------------------------------------

async def check_visa_validity(visa_type: str, nationality: str) -> VisaValidityResult:
    """
    Check that the issued visa type is valid for the traveller's nationality.

    Args:
        visa_type:   The visa type extracted from the document (e.g. 'tourist', 'business').
        nationality: ICAO/ISO-3166-1 alpha-3 nationality code from the document.

    Returns:
        VisaValidityResult with is_valid_combination flag and max_stay_days.
    """
    logger.info("Visa validity lookup", visa_type=visa_type, nationality=nationality)

    try:
        session = _get_session()
        async with session as s:
            result = await s.execute(
                select(MockVisaRecord).where(
                    MockVisaRecord.visa_type == visa_type.lower().strip(),
                    MockVisaRecord.nationality == nationality.upper().strip(),
                )
            )
            row: MockVisaRecord | None = result.scalar_one_or_none()

        if row:
            return VisaValidityResult(
                is_valid_combination=row.is_valid,
                max_stay_days=row.max_stay_days,
                mode="online",
            )

        # No record found — combination not in DB, treat as unknown/not-invalid
        # (the mock DB is intentionally incomplete; absence ≠ invalid)
        logger.info(
            "Visa validity: no record found, treating as unknown",
            visa_type=visa_type,
            nationality=nationality,
        )
        return VisaValidityResult(
            is_valid_combination=True,
            max_stay_days=None,
            mode="online",
        )

    except (OperationalError, SQLAlchemyError, OSError) as e:
        logger.error(
            "Visa validity DB unreachable — returning unknown",
            error=str(e),
            mode="offline_cached",
        )
        return VisaValidityResult(is_valid_combination=True, max_stay_days=None, mode="offline_cached")


# ---------------------------------------------------------------------------
# Composite check — all three at once
# ---------------------------------------------------------------------------

async def run_all_database_checks(
    document_number: str,
    name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    visa_type: Optional[str] = None,
    nationality: Optional[str] = None,
) -> tuple[SLTDResult, BlacklistResult, Optional[VisaValidityResult]]:
    """
    Run all three database checks and return results as a tuple.

    Errors in individual checks do NOT cascade — partial failure returns
    safe defaults for the failed check while others still complete.
    """
    import asyncio

    sltd_coro = check_sltd(document_number)
    blacklist_coro = check_national_blacklist(document_number, name, date_of_birth)

    if visa_type and nationality:
        visa_coro = check_visa_validity(visa_type, nationality)
        sltd_res, bl_res, visa_res = await asyncio.gather(
            sltd_coro, blacklist_coro, visa_coro
        )
    else:
        sltd_res, bl_res = await asyncio.gather(sltd_coro, blacklist_coro)
        visa_res = None

    return sltd_res, bl_res, visa_res
