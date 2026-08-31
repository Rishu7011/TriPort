"""
Phase 3 — FastAPI Integration Tests for the Validation Service.

Uses FastAPI's official async test pattern:
  - `httpx.AsyncClient` + `ASGITransport` — no real HTTP, no port binding,
    but exercises the full request/response pipeline including middleware,
    request parsing, response serialization, and all router logic.
  - Tests run entirely in-process; no Postgres required (DB calls are mocked).
  - Lifespan is NOT triggered in test mode (background sync task stays off),
    keeping tests fast and hermetic.

Endpoints covered:
  GET  /health                         ← service health
  POST /api/v1/validation/validate     ← YAML rules engine
  POST /api/v1/validation/database-check ← SLTD + blacklist + visa
  POST /api/v1/validation/regional-validate ← neighboring-country format rules
  GET  /api/v1/validation/regional-countries ← supported country list
  GET  /api/v1/validation/cache-stats  ← offline cache stats
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx

from backend.validation_service.main import app
from backend.validation_service.schemas.validation import (
    BlacklistResult,
    SLTDResult,
    VisaValidityResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def future_date(days: int = 400) -> str:
    return (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")


def past_date(days: int = 90) -> str:
    return (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")


def years_ago(years: int = 30) -> str:
    d = date.today()
    return d.replace(year=d.year - years).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Shared async test client fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """
    Yield an httpx.AsyncClient wired to the FastAPI app via ASGITransport.
    No real HTTP server is started — requests go in-process through ASGI.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "validation-service"
        assert "cache" in body


# ---------------------------------------------------------------------------
# 2. POST /api/v1/validation/validate
# ---------------------------------------------------------------------------

VALID_PASSPORT_PAYLOAD = {
    "document_type": "passport",
    "fields": [
        {"field_name": "doc_number",      "field_value": "A1234567",  "confidence": 0.99, "extraction_method": "mrz"},
        {"field_name": "passport_number", "field_value": "A1234567",  "confidence": 0.98, "extraction_method": "ocr"},
        {"field_name": "nationality",     "field_value": "IND",        "confidence": 0.99, "extraction_method": "mrz"},
        {"field_name": "date_of_birth",   "field_value": years_ago(35),"confidence": 0.97, "extraction_method": "mrz"},
        {"field_name": "expiry_date",     "field_value": future_date(600), "confidence": 0.99, "extraction_method": "mrz"},
        {"field_name": "date_of_expiry",  "field_value": future_date(600), "confidence": 0.99, "extraction_method": "ocr"},
    ],
    "mrz_checksum_valid": True,
    "mrz_checksum_failures": [],
}


class TestValidateEndpoint:
    @pytest.mark.asyncio
    async def test_valid_passport_returns_passed_true(self, client):
        """A genuinely valid passport payload must return passed=True, 200 OK."""
        resp = await client.post("/api/v1/validation/validate", json=VALID_PASSPORT_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is True
        assert body["failed_rules"] == []
        assert len(body["rule_results"]) > 0

    @pytest.mark.asyncio
    async def test_expired_passport_returns_passed_false(self, client):
        """An expired passport must return passed=False with expiry rules listed."""
        payload = {
            **VALID_PASSPORT_PAYLOAD,
            "fields": [
                {"field_name": "doc_number",      "field_value": "A1234567",  "confidence": 0.99, "extraction_method": "mrz"},
                {"field_name": "passport_number", "field_value": "A1234567",  "confidence": 0.98, "extraction_method": "ocr"},
                {"field_name": "nationality",     "field_value": "IND",        "confidence": 0.99, "extraction_method": "mrz"},
                {"field_name": "date_of_birth",   "field_value": years_ago(35),"confidence": 0.97, "extraction_method": "mrz"},
                {"field_name": "expiry_date",     "field_value": past_date(30), "confidence": 0.99, "extraction_method": "mrz"},
                {"field_name": "date_of_expiry",  "field_value": past_date(30), "confidence": 0.99, "extraction_method": "ocr"},
            ],
        }
        resp = await client.post("/api/v1/validation/validate", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is False
        assert "expiry_not_passed" in body["failed_rules"]

    @pytest.mark.asyncio
    async def test_invalid_document_type_returns_422(self, client):
        """An unrecognised document_type triggers a Pydantic validation error → 422."""
        payload = {**VALID_PASSPORT_PAYLOAD, "document_type": "intergalactic_id"}
        resp = await client.post("/api/v1/validation/validate", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_fields_array_returns_422(self, client):
        """fields is required — omitting it returns 422."""
        resp = await client.post(
            "/api/v1/validation/validate",
            json={"document_type": "passport"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_fields_still_returns_200(self, client):
        """Empty fields list is valid input — service runs zero rules, returns 200."""
        resp = await client.post(
            "/api/v1/validation/validate",
            json={"document_type": "passport", "fields": []},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_driving_license_validate(self, client):
        """Driving license document type is handled by the DL rules set."""
        resp = await client.post(
            "/api/v1/validation/validate",
            json={
                "document_type": "driving_license",
                "fields": [
                    {"field_name": "license_number",    "field_value": "KA-0120110012345", "confidence": 0.98, "extraction_method": "ocr"},
                    {"field_name": "date_of_expiry",    "field_value": future_date(400),   "confidence": 0.97, "extraction_method": "ocr"},
                    {"field_name": "date_of_birth",     "field_value": years_ago(30),      "confidence": 0.95, "extraction_method": "ocr"},
                    {"field_name": "vehicle_class",     "field_value": "LMV",              "confidence": 0.99, "extraction_method": "ocr"},
                    {"field_name": "issuing_authority", "field_value": "RTO Bangalore",    "confidence": 0.96, "extraction_method": "ocr"},
                    {"field_name": "name",              "field_value": "RAHUL SHARMA",     "confidence": 0.94, "extraction_method": "ocr"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["passed"] is True

    @pytest.mark.asyncio
    async def test_permit_validate(self, client):
        """Permit document type is handled by the permit rules set."""
        resp = await client.post(
            "/api/v1/validation/validate",
            json={
                "document_type": "permit",
                "fields": [
                    {"field_name": "permit_number",     "field_value": "ILP-2024-001",        "confidence": 0.98, "extraction_method": "ocr"},
                    {"field_name": "valid_until",       "field_value": future_date(60),        "confidence": 0.97, "extraction_method": "ocr"},
                    {"field_name": "name",              "field_value": "JANE TRAVELER",        "confidence": 0.95, "extraction_method": "ocr"},
                    {"field_name": "permit_type",       "field_value": "visitor",              "confidence": 0.99, "extraction_method": "ocr"},
                    {"field_name": "issuing_authority", "field_value": "District Collector",   "confidence": 0.96, "extraction_method": "ocr"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["passed"] is True

    @pytest.mark.asyncio
    async def test_response_shape(self, client):
        """Verify the response JSON matches the ValidationResponse schema."""
        resp = await client.post("/api/v1/validation/validate", json=VALID_PASSPORT_PAYLOAD)
        body = resp.json()
        assert "document_type" in body
        assert "passed" in body
        assert "failed_rules" in body
        assert "rule_results" in body
        # Each rule_result must have rule_name, passed, detail
        for r in body["rule_results"]:
            assert "rule_name" in r
            assert "passed" in r


# ---------------------------------------------------------------------------
# 3. POST /api/v1/validation/database-check
# (Postgres is mocked — no live DB required)
# ---------------------------------------------------------------------------

class TestDatabaseCheckEndpoint:
    def _make_sltd_result(self, hit: bool) -> SLTDResult:
        return SLTDResult(sltd_hit=hit, sltd_record=None, mode="online")

    def _make_blacklist_result(self, hit: bool) -> BlacklistResult:
        return BlacklistResult(blacklist_hit=hit, matched_record=None, match_basis=[], mode="online")

    def _make_visa_result(self, valid: bool) -> VisaValidityResult:
        return VisaValidityResult(is_valid_combination=valid, max_stay_days=90, mode="online")

    @pytest.mark.asyncio
    async def test_clean_document_no_hits(self, client):
        """A clean document returns all hits=False, any_hit=False."""
        with patch(
            "backend.validation_service.routers.validation.run_all_database_checks",
            new=AsyncMock(return_value=(
                self._make_sltd_result(False),
                self._make_blacklist_result(False),
                self._make_visa_result(True),
            )),
        ):
            resp = await client.post(
                "/api/v1/validation/database-check",
                json={
                    "document_number": "A1234567",
                    "name": "LEGITIMATE TRAVELER",
                    "date_of_birth": years_ago(35),
                    "visa_type": "tourist",
                    "nationality": "IND",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["any_hit"] is False
        assert body["sltd"]["sltd_hit"] is False
        assert body["blacklist"]["blacklist_hit"] is False
        assert body["visa_validity"]["is_valid_combination"] is True

    @pytest.mark.asyncio
    async def test_sltd_hit_flagged_in_response(self, client):
        """A document on the SLTD list returns any_hit=True."""
        with patch(
            "backend.validation_service.routers.validation.run_all_database_checks",
            new=AsyncMock(return_value=(
                self._make_sltd_result(True),          # ← SLTD hit
                self._make_blacklist_result(False),
                None,
            )),
        ):
            resp = await client.post(
                "/api/v1/validation/database-check",
                json={"document_number": "X9999999"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["any_hit"] is True
        assert body["sltd"]["sltd_hit"] is True

    @pytest.mark.asyncio
    async def test_blacklist_hit_flagged_in_response(self, client):
        """A person on the national blacklist returns any_hit=True."""
        with patch(
            "backend.validation_service.routers.validation.run_all_database_checks",
            new=AsyncMock(return_value=(
                self._make_sltd_result(False),
                self._make_blacklist_result(True),      # ← blacklist hit
                None,
            )),
        ):
            resp = await client.post(
                "/api/v1/validation/database-check",
                json={
                    "document_number": "A1234567",
                    "name": "JOHN DEMO BANNED",
                    "date_of_birth": "1985-01-01",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["any_hit"] is True
        assert body["blacklist"]["blacklist_hit"] is True

    @pytest.mark.asyncio
    async def test_missing_document_number_returns_422(self, client):
        """document_number is required — omitting it triggers 422."""
        resp = await client.post(
            "/api/v1/validation/database-check",
            json={"name": "SOMEONE"},   # no document_number
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_response_schema_shape(self, client):
        """Verify DatabaseCheckResponse schema: sltd, blacklist, visa_validity, any_hit."""
        with patch(
            "backend.validation_service.routers.validation.run_all_database_checks",
            new=AsyncMock(return_value=(
                self._make_sltd_result(False),
                self._make_blacklist_result(False),
                self._make_visa_result(True),
            )),
        ):
            resp = await client.post(
                "/api/v1/validation/database-check",
                json={"document_number": "A1234567"},
            )
        body = resp.json()
        assert "sltd" in body
        assert "blacklist" in body
        assert "visa_validity" in body
        assert "any_hit" in body
        assert "sltd_hit" in body["sltd"]
        assert "blacklist_hit" in body["blacklist"]


# ---------------------------------------------------------------------------
# 4. POST /api/v1/validation/regional-validate
# ---------------------------------------------------------------------------

class TestRegionalValidateEndpoint:
    @pytest.mark.asyncio
    async def test_nepal_valid_doc_passes(self, client):
        """Valid Nepali citizenship number → passed=True."""
        resp = await client.post(
            "/api/v1/validation/regional-validate",
            json={
                "nationality": "NP",
                "document_type": "national_id",
                "fields": [
                    {"field_name": "id_number",      "field_value": "05-02-80-12345", "confidence": 0.97, "extraction_method": "ocr"},
                    {"field_name": "passport_number","field_value": "NA1234567",      "confidence": 0.98, "extraction_method": "ocr"},
                    {"field_name": "date_of_birth",  "field_value": years_ago(32),    "confidence": 0.95, "extraction_method": "ocr"},
                    {"field_name": "date_of_expiry", "field_value": future_date(400), "confidence": 0.97, "extraction_method": "ocr"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["passed"] is True

    @pytest.mark.asyncio
    async def test_bangladesh_17digit_nid_passes(self, client):
        """Bangladesh 17-digit Smart NID passes BD regional rules."""
        resp = await client.post(
            "/api/v1/validation/regional-validate",
            json={
                "nationality": "BGD",
                "document_type": "national_id",
                "fields": [
                    {"field_name": "id_number",      "field_value": "19801234567890123", "confidence": 0.96, "extraction_method": "ocr"},
                    {"field_name": "passport_number","field_value": "AB9876543",         "confidence": 0.98, "extraction_method": "ocr"},
                    {"field_name": "date_of_birth",  "field_value": years_ago(44),       "confidence": 0.94, "extraction_method": "ocr"},
                    {"field_name": "date_of_expiry", "field_value": future_date(400),    "confidence": 0.97, "extraction_method": "ocr"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["passed"] is True

    @pytest.mark.asyncio
    async def test_invalid_nepal_id_fails(self, client):
        """Bad Nepali ID format → passed=False with np_citizenship_id_format in failed_rules."""
        resp = await client.post(
            "/api/v1/validation/regional-validate",
            json={
                "nationality": "NP",
                "document_type": "national_id",
                "fields": [
                    {"field_name": "id_number",     "field_value": "INVALID-FORMAT", "confidence": 0.90, "extraction_method": "ocr"},
                    {"field_name": "date_of_birth", "field_value": years_ago(30),    "confidence": 0.95, "extraction_method": "ocr"},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is False
        assert "np_citizenship_id_format" in body["failed_rules"]

    @pytest.mark.asyncio
    async def test_unknown_nationality_returns_pass(self, client):
        """Nationality with no regional rules → passed=True with informational note."""
        resp = await client.post(
            "/api/v1/validation/regional-validate",
            json={
                "nationality": "ZZ",
                "document_type": "passport",
                "fields": [
                    {"field_name": "passport_number", "field_value": "AB1234567", "confidence": 0.98, "extraction_method": "ocr"},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is True
        assert any("not configured" in r["detail"].lower() for r in body["rule_results"])

    @pytest.mark.asyncio
    async def test_alpha3_nationality_code_accepted(self, client):
        """ICAO alpha-3 code 'NPL' is normalised to 'NP' and rules are applied."""
        resp = await client.post(
            "/api/v1/validation/regional-validate",
            json={
                "nationality": "NPL",    # alpha-3 — should normalise to NP
                "document_type": "passport",
                "fields": [
                    {"field_name": "passport_number","field_value": "NA1234567",   "confidence": 0.99, "extraction_method": "mrz"},
                    {"field_name": "date_of_birth",  "field_value": years_ago(35), "confidence": 0.98, "extraction_method": "mrz"},
                    {"field_name": "date_of_expiry", "field_value": future_date(500), "confidence": 0.99, "extraction_method": "mrz"},
                ],
            },
        )
        assert resp.status_code == 200
        # The NP passport_number rule should have applied and passed
        rule_names = [r["rule_name"] for r in resp.json()["rule_results"]]
        assert "np_passport_number_format" in rule_names


# ---------------------------------------------------------------------------
# 5. GET /api/v1/validation/regional-countries
# ---------------------------------------------------------------------------

class TestRegionalCountriesEndpoint:
    @pytest.mark.asyncio
    async def test_returns_list_of_strings(self, client):
        resp = await client.get("/api/v1/validation/regional-countries")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert all(isinstance(c, str) for c in body)

    @pytest.mark.asyncio
    async def test_contains_all_phase3_countries(self, client):
        resp = await client.get("/api/v1/validation/regional-countries")
        countries = resp.json()
        for code in ["NP", "BT", "BD", "MM"]:
            assert code in countries, f"Country {code} missing from /regional-countries"


# ---------------------------------------------------------------------------
# 6. GET /api/v1/validation/cache-stats
# ---------------------------------------------------------------------------

class TestCacheStatsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_status_ok(self, client):
        resp = await client.get("/api/v1/validation/cache-stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "cache" in body

    @pytest.mark.asyncio
    async def test_cache_stats_contain_expected_keys(self, client):
        resp = await client.get("/api/v1/validation/cache-stats")
        cache = resp.json()["cache"]
        assert "cached_rule_sets" in cache
        assert "cached_blacklist_entries" in cache
        assert "pending_sync_decisions" in cache
