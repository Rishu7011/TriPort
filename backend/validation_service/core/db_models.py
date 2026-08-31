"""
Database ORM Models for Validation Service — Mock Government Databases.

Three mock tables stand in for real government API integrations:
  1. mock_sltd          — Interpol Stolen & Lost Travel Documents
  2. mock_blacklist     — National prohibited/watchlist persons
  3. mock_visa_records  — Permitted visa-type / nationality combinations

In production these stubs are replaced by outbound API calls to the relevant
government databases. The clean interface here (independent async functions
per check) is designed to make that substitution surgical.
"""

from datetime import date
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class MockSLTD(Base):
    """
    Mock Interpol SLTD (Stolen & Lost Travel Documents) database.

    Indexed on document_number for fast O(log n) lookups.
    Each row represents one reported document.
    """
    __tablename__ = "mock_sltd"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_number = Column(String(30), nullable=False, index=True, unique=True)
    report_type = Column(String(30), nullable=False)          # 'stolen', 'lost', 'fraudulent'
    reporting_country = Column(String(3), nullable=False)      # ISO-3166-1 alpha-3
    reported_at = Column(Date, nullable=False, default=date.today)

    def __repr__(self) -> str:
        return (
            f"<MockSLTD doc={self.document_number!r} "
            f"type={self.report_type!r} country={self.reporting_country!r}>"
        )


class MockBlacklist(Base):
    """
    National prohibited/watchlist persons database.

    Supports matching on:
      - document_number alone
      - name + date_of_birth combination

    severity values:
      'banned'    — deny entry, detain for further questioning
      'watchlist' — flag and escalate to supervisor
      'investigate' — flag for secondary inspection
    """
    __tablename__ = "mock_blacklist"
    __table_args__ = (
        UniqueConstraint("name", "date_of_birth", name="uq_blacklist_name_dob"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    date_of_birth = Column(String(10), nullable=True)          # ISO format YYYY-MM-DD
    document_number = Column(String(30), nullable=True, index=True)
    severity = Column(String(20), nullable=False, default="watchlist")
    reason = Column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<MockBlacklist name={self.name!r} severity={self.severity!r}>"


class MockVisaRecord(Base):
    """
    Permitted visa-type / nationality combinations and max stay durations.

    Validates that the issued visa type is actually valid for the traveller's
    nationality (catches forged visas with valid-looking numbers but wrong type).
    """
    __tablename__ = "mock_visa_records"
    __table_args__ = (
        UniqueConstraint("visa_type", "nationality", name="uq_visa_nationality"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    visa_type = Column(String(30), nullable=False, index=True)
    nationality = Column(String(3), nullable=False, index=True)   # ISO-3166-1 alpha-3
    is_valid = Column(Boolean, nullable=False, default=True)
    max_stay_days = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<MockVisaRecord visa={self.visa_type!r} "
            f"nat={self.nationality!r} valid={self.is_valid}>"
        )
