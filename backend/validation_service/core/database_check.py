"""
Database Cross-Check Module — In-memory mock government database queries.

No database persistence. Mock tables live in process memory only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.logging_config import get_logger
from backend.validation_service.schemas.validation import (
    BlacklistRecord,
    BlacklistResult,
    SLTDRecord,
    SLTDResult,
    VisaValidityResult,
)

logger = get_logger("validation_service.database_check")


@dataclass(frozen=True)
class _MockSLTD:
    document_number: str
    report_type: str
    reporting_country: str
    reported_at: str


@dataclass(frozen=True)
class _MockBlacklist:
    document_number: str | None
    name: str
    date_of_birth: str | None
    severity: str
    reason: str


@dataclass(frozen=True)
class _MockVisaRecord:
    visa_type: str
    nationality: str
    is_valid: bool
    max_stay_days: int | None


_MOCK_SLTD: list[_MockSLTD] = [
    _MockSLTD("X9999999", "STOLEN", "DEU", "2024-01-15"),
    _MockSLTD("Z8877665", "LOST", "FRA", "2023-11-02"),
]

_MOCK_BLACKLIST: list[_MockBlacklist] = [
    _MockBlacklist("X9999999", "VIKTOR KORZHOV", "1980-04-12", "banned", "Interpol Red Notice"),
    _MockBlacklist("B1234567", "JOHN DOE SUSPECT", "1975-09-30", "suspect", "Border alert"),
]

_MOCK_VISA: list[_MockVisaRecord] = [
    _MockVisaRecord("tourist", "IND", True, 90),
    _MockVisaRecord("business", "IND", True, 180),
    _MockVisaRecord("tourist", "USA", True, 30),
]


async def check_sltd(document_number: str) -> SLTDResult:
    logger.info("SLTD lookup", document_number=document_number)
    normalized = document_number.upper().strip()

    for row in _MOCK_SLTD:
        if row.document_number == normalized:
            logger.warning("SLTD HIT", document_number=document_number)
            return SLTDResult(
                sltd_hit=True,
                sltd_record=SLTDRecord(
                    document_number=row.document_number,
                    report_type=row.report_type,
                    reporting_country=row.reporting_country,
                    reported_at=row.reported_at,
                ),
                mode="online",
            )

    return SLTDResult(sltd_hit=False, sltd_record=None, mode="online")


async def check_national_blacklist(
    document_number: Optional[str] = None,
    name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
) -> BlacklistResult:
    logger.info(
        "National blacklist lookup",
        document_number=document_number,
        has_name=bool(name),
        has_dob=bool(date_of_birth),
    )

    normalized_doc = document_number.upper().strip() if document_number else None
    normalized_name = name.strip().upper() if name else None
    normalized_dob = date_of_birth.strip() if date_of_birth else None

    for row in _MOCK_BLACKLIST:
        match_basis: list[str] = []
        if normalized_doc and row.document_number and normalized_doc == row.document_number:
            match_basis.append("document_number")
        if (
            normalized_name
            and normalized_dob
            and row.name.upper() == normalized_name
            and row.date_of_birth == normalized_dob
        ):
            match_basis.append("name+dob")

        if match_basis:
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

    return BlacklistResult(
        blacklist_hit=False,
        matched_record=None,
        match_basis=[],
        mode="online",
    )


async def check_visa_validity(visa_type: str, nationality: str) -> VisaValidityResult:
    logger.info("Visa validity lookup", visa_type=visa_type, nationality=nationality)

    visa_key = visa_type.lower().strip()
    nationality_key = nationality.upper().strip()

    for row in _MOCK_VISA:
        if row.visa_type == visa_key and row.nationality == nationality_key:
            return VisaValidityResult(
                is_valid_combination=row.is_valid,
                max_stay_days=row.max_stay_days,
                mode="online",
            )

    return VisaValidityResult(
        is_valid_combination=True,
        max_stay_days=None,
        mode="online",
    )


async def run_all_database_checks(
    document_number: str,
    name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    visa_type: Optional[str] = None,
    nationality: Optional[str] = None,
) -> tuple[SLTDResult, BlacklistResult, Optional[VisaValidityResult]]:
    import asyncio

    sltd_coro = check_sltd(document_number)
    blacklist_coro = check_national_blacklist(
        document_number=document_number,
        name=name,
        date_of_birth=date_of_birth,
    )

    if visa_type and nationality:
        visa_coro = check_visa_validity(visa_type, nationality)
        sltd_result, blacklist_result, visa_result = await asyncio.gather(
            sltd_coro, blacklist_coro, visa_coro
        )
        return sltd_result, blacklist_result, visa_result

    sltd_result, blacklist_result = await asyncio.gather(sltd_coro, blacklist_coro)
    return sltd_result, blacklist_result, None
