"""
Phase 4 Unit & Integration Tests — Cryptographic Audit Ledger, Encryption, Auth & RBAC.

Verifies:
  1. Immutable hash chaining and SHA-256 Merkle-style linkage.
  2. Chain integrity verification and corruption detection.
  3. AES-256-GCM symmetric encryption / decryption and PII masking.
  4. Password hashing (bcrypt) and JWT Bearer token lifecycle.
  5. RBAC role access guards (Officer vs Supervisor vs Auditor vs Admin).
  6. Ledger and Auth FastAPI router endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from backend.audit_ledger.core.hash_chain import (
    append_event,
    verify_chain,
    compute_payload_hash,
    compute_record_hash,
    clear_in_memory_chain,
    get_in_memory_chain,
)
from backend.audit_ledger.core.encryption import (
    encrypt_bytes,
    decrypt_bytes,
    encrypt_text,
    decrypt_text,
    mask_pii,
)
from backend.orchestrator.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    DEMO_USERS,
)
from backend.orchestrator.main import app


@pytest.mark.asyncio
async def test_hash_chain_sequential_append():
    """Verify that multiple events form a valid continuous SHA-256 hash chain."""
    clear_in_memory_chain()

    # Append 3 events
    e1 = await append_event(
        event_type="scan",
        payload={"doc_number": "U5691319", "risk_score": 14.0},
        document_id="00000000-0000-0000-0000-000000000001",
    )
    assert e1.sequence_num == 1
    assert e1.prev_record_hash == "0" * 64

    e2 = await append_event(
        event_type="officer_decision",
        payload={"decision": "approve", "notes": "cleared"},
        document_id="00000000-0000-0000-0000-000000000001",
    )
    assert e2.sequence_num == 2
    assert e2.prev_record_hash == e1.record_hash

    e3 = await append_event(
        event_type="sync",
        payload={"checkpoint": "CP-DEL-T3"},
    )
    assert e3.sequence_num == 3
    assert e3.prev_record_hash == e2.record_hash

    # Run verification
    report = await verify_chain()
    assert report.valid is True
    assert report.total_events == 3
    assert report.first_invalid_sequence is None


@pytest.mark.asyncio
async def test_hash_chain_tamper_detection():
    """Verify that manually altering a past block breaks the chain and is detected."""
    clear_in_memory_chain()

    for i in range(1, 6):
        await append_event(
            event_type="scan" if i == 1 else "officer_decision",
            payload={"step": i, "score": 10 * i},
        )

    # Validate before attack
    pre_report = await verify_chain()
    assert pre_report.valid is True

    # Tamper with block #3 payload hash
    chain = get_in_memory_chain()
    assert len(chain) >= 3
    chain[2]["payload_hash"] = "deadbeef" * 8

    # Validate after attack
    post_report = await verify_chain()
    assert post_report.valid is False
    assert post_report.first_invalid_sequence == 3
    assert "tampering detected" in post_report.detail.lower()


def test_aes_256_encryption_and_pii_masking():
    """Verify AES-256-GCM symmetric encryption roundtrips and PII redaction."""
    secret_text = "PASSPORT_SECRET_U5691319"
    cipher_b64 = encrypt_text(secret_text)
    assert cipher_b64 != secret_text

    decrypted = decrypt_text(cipher_b64)
    assert decrypted == secret_text

    # Raw bytes test
    raw_payload = b"\x00\x01\x02\x03\xfe\xff"
    encrypted_bytes = encrypt_bytes(raw_payload)
    assert decrypt_bytes(encrypted_bytes) == raw_payload

    # PII masking
    masked_doc = mask_pii("U5691319", visible_prefix=4)
    assert masked_doc == "U569****"

    masked_name = mask_pii("GURPREET", visible_prefix=3)
    assert masked_name == "GUR*****"


def test_jwt_auth_and_password_hashing():
    """Verify bcrypt password hashing and JWT token claims parsing."""
    raw_pw = "officer123"
    pw_hash = get_password_hash(raw_pw)
    assert verify_password(raw_pw, pw_hash) is True
    assert verify_password("wrong_password", pw_hash) is False

    # Issue JWT token
    token = create_access_token({
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "officer@borderguard.gov",
        "role": "officer",
        "badge_number": "BG-7492",
        "checkpoint_id": "CP-DEL-T3",
    })
    assert isinstance(token, str)

    user_data = decode_access_token(token)
    assert user_data is not None
    assert user_data.email == "officer@borderguard.gov"
    assert user_data.role == "officer"
    assert user_data.badge_number == "BG-7492"


@pytest.mark.asyncio
async def test_auth_login_endpoint():
    """Verify FastAPI /api/v1/auth/login and /api/v1/auth/me endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Successful login
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "officer@borderguard.gov", "password": "officer123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["role"] == "officer"

        token = data["access_token"]

        # Profile /me call
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == "officer@borderguard.gov"
        assert "document:upload" in me_data["permissions"]

        # Failed login with bad password
        bad_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "officer@borderguard.gov", "password": "incorrect_password"},
        )
        assert bad_resp.status_code == 401


@pytest.mark.asyncio
async def test_audit_ledger_endpoints():
    """Verify /api/v1/audit/events/ and /api/v1/audit/events/verify."""
    clear_in_memory_chain()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create event
        evt_resp = await client.post(
            "/api/v1/audit/events/",
            json={
                "event_type": "scan",
                "payload": {"status": "test_pass"},
                "document_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert evt_resp.status_code == 201
        data = evt_resp.json()
        assert data["sequence_num"] == 1
        assert len(data["record_hash"]) == 64

        # Verify chain via HTTP
        verify_resp = await client.get("/api/v1/audit/events/verify")
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["valid"] is True
        assert verify_data["total_events"] >= 1


@pytest.mark.asyncio
async def test_rbac_document_and_audit_endpoints_enforcement():
    """
    Verify RBAC security:
      1. Unauthenticated requests to /api/v1/documents/* are rejected with 401.
      2. Unauthenticated requests to /api/v1/audit/{id} are rejected with 401.
      3. Officer role cannot access /api/v1/audit/{id} (rejected with 403).
      4. Supervisor role can access /api/v1/audit/{id} (passes RBAC).
      5. Authenticated officer request to /api/v1/documents/upload passes RBAC.
    """
    from unittest.mock import AsyncMock, MagicMock
    from backend.orchestrator.db.session import get_db

    async def mock_get_db():
        session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_res.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_res
        yield session

    app.dependency_overrides[get_db] = mock_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Unauthenticated /documents/upload -> 401
            unauth_upload = await client.post("/api/v1/documents/upload")
            assert unauth_upload.status_code == 401

            # 2. Unauthenticated /documents/{id}/risk-score -> 401
            dummy_id = "00000000-0000-0000-0000-000000000001"
            unauth_risk = await client.get(f"/api/v1/documents/{dummy_id}/risk-score")
            assert unauth_risk.status_code == 401

            # 3. Unauthenticated /audit/{id} -> 401
            unauth_audit = await client.get(f"/api/v1/audit/{dummy_id}")
            assert unauth_audit.status_code == 401

            # 4. Generate Officer token & Supervisor token
            officer_token = create_access_token({
                "sub": "00000000-0000-0000-0000-000000000001",
                "email": "officer@borderguard.gov",
                "role": "officer",
                "badge_number": "BG-7492",
                "checkpoint_id": "CP-DEL-T3",
            })
            supervisor_token = create_access_token({
                "sub": "00000000-0000-0000-0000-000000000002",
                "email": "supervisor@borderguard.gov",
                "role": "supervisor",
                "badge_number": "BG-1102",
                "checkpoint_id": "CP-DEL-T3",
            })

            # 5. Officer trying to access /audit/{id} -> 403 Forbidden (requires supervisor/admin)
            officer_audit_resp = await client.get(
                f"/api/v1/audit/{dummy_id}",
                headers={"Authorization": f"Bearer {officer_token}"},
            )
            assert officer_audit_resp.status_code == 403

            # 6. Supervisor accessing /audit/{id} -> passes auth (returns 404 since doc doesn't exist, but not 401/403)
            sup_audit_resp = await client.get(
                f"/api/v1/audit/{dummy_id}",
                headers={"Authorization": f"Bearer {supervisor_token}"},
            )
            assert sup_audit_resp.status_code in [200, 404]

            # 7. Authenticated officer accessing /documents/upload with empty payload -> gets 422 Unprocessable (NOT 401/403)
            officer_upload = await client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {officer_token}"},
            )
            assert officer_upload.status_code == 422  # Missing multipart file, but passed RBAC!
    finally:
        app.dependency_overrides.pop(get_db, None)

