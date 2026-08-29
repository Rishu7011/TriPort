# BorderGuard-AI — API Contracts & Specification

This document details all external REST API endpoints exposed by the Orchestrator Gateway (`backend/orchestrator/routers/`) and Authentication subsystem.

---

## 1. Authentication & Security Model

All API endpoints (except `/api/v1/auth/login`) require a JWT Bearer token passed in the HTTP `Authorization` header:

```http
Authorization: Bearer <JWT_ACCESS_TOKEN>
```

### RBAC Permission Matrix

| Endpoint | Method | Required Roles | Description |
|---|---|---|---|
| `/api/v1/auth/login` | `POST` | Public | Authenticate user & receive JWT token |
| `/api/v1/auth/me` | `GET` | All authenticated | Get current user identity & permissions |
| `/api/v1/documents/upload` | `POST` | `officer`, `supervisor`, `admin` | Upload document scan and run screening pipeline |
| `/api/v1/documents/{id}/extraction` | `GET` | `officer`, `supervisor`, `admin` | Retrieve OCR extracted fields & MRZ status |
| `/api/v1/documents/{id}/validation` | `GET` | `officer`, `supervisor`, `admin` | Retrieve business rules validation result |
| `/api/v1/documents/{id}/tampering` | `GET` | `officer`, `supervisor`, `admin` | Retrieve forensic tampering & ELA results |
| `/api/v1/documents/{id}/face-verification` | `GET` | `officer`, `supervisor`, `admin` | Retrieve biometric match & deduplication cluster |
| `/api/v1/documents/{id}/risk-score` | `GET` | `officer`, `supervisor`, `admin` | Retrieve computed risk score & reasons |
| `/api/v1/documents/{id}/decision` | `POST` | `officer`, `supervisor`, `admin` | Record officer verdict into audit ledger |
| `/api/v1/audit/{document_id}` | `GET` | `supervisor`, `admin` | Retrieve full hash-chained event trail |
| `/api/v1/audit/events/` | `POST` | Internal / Admin | Append raw event to audit ledger |
| `/api/v1/audit/events/verify` | `GET` | All authenticated | Verify SHA-256 hash-chain integrity |

---

## 2. Authentication Endpoints

### `POST /api/v1/auth/login`
Authenticates an officer or administrator and issues a signed JWT token.

- **Request Body (`application/json`):**
```json
{
  "email": "officer@borderguard.gov",
  "password": "officer123"
}
```

- **Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "officer@borderguard.gov",
    "role": "officer",
    "name": "Officer J. Miller",
    "badge_number": "BG-7492",
    "checkpoint_id": "CP-DEL-T3",
    "permissions": ["document:upload", "document:view", "decision:record"]
  }
}
```

- **Errors:**
  - `401 Unauthorized`: Invalid email or password.

---

### `GET /api/v1/auth/me`
Fetches the active user profile from the provided Bearer token.

- **Response (`200 OK`):**
```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "email": "officer@borderguard.gov",
  "role": "officer",
  "badge_number": "BG-7492",
  "checkpoint_id": "CP-DEL-T3",
  "permissions": ["document:upload", "document:view", "decision:record"]
}
```

---

## 3. Document Screening Endpoints

### `POST /api/v1/documents/upload`
Uploads a document scan image, executes all 5 screening modules sequentially (with fallback handling), persists records to PostgreSQL, and returns the complete screening report.

*(Implementation Note: Differs from early plan.md sketch by returning synchronous complete pipeline results rather than a polling job status, optimizing for the <5s requirement).*

- **Request Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: multipart/form-data`

- **Form Fields:**
  - `file` (UploadFile, required): Raw document image (JPEG/PNG).
  - `document_type` (string, optional, default: `"passport"`): `"passport" | "visa" | "national_id" | "driving_license" | "permit"`.
  - `live_photo` (UploadFile, optional): Traveler webcam portrait for 1:1 biometric match & liveness check.
  - `checkpoint_id` (string, optional): Border checkpoint UUID.

- **Response (`200 OK`):**
```json
{
  "document_id": "3e365d37-623b-40fa-8a02-1e0cdfa58799",
  "status": "complete",
  "pipeline": {
    "document_id": "3e365d37-623b-40fa-8a02-1e0cdfa58799",
    "degraded": false,
    "service_statuses": {
      "ocr": { "available": true },
      "validation": { "available": true },
      "tampering": { "available": true },
      "face": { "available": true },
      "risk_engine": { "available": true }
    },
    "extraction": {
      "document_type": "passport",
      "fields": [
        { "field_name": "passport_number", "field_value": "A1234567", "confidence": 0.98 },
        { "field_name": "surname", "field_value": "SINGH", "confidence": 0.99 },
        { "field_name": "given_names", "field_value": "GURPREET", "confidence": 0.99 }
      ],
      "mrz": {
        "mrz_present": true,
        "checksum_valid": true,
        "checksum_failures": [],
        "mrz_fields": { "doc_number": "A1234567", "dob": "900515", "expiry": "301231" }
      }
    },
    "validation": {
      "document_type": "passport",
      "passed": true,
      "failed_rules": [],
      "rule_results": [
        { "rule_name": "MRZ-01", "passed": true, "detail": "All ICAO 9303 check digits valid" }
      ]
    },
    "tampering": {
      "flagged": false,
      "tampering_score": 0.08,
      "checks": [
        { "check_type": "ela", "score": 0.05, "flagged": false, "detail": "Uniform error level distribution" }
      ],
      "ela_heatmap_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
    },
    "face": {
      "one_to_one": {
        "matched": true,
        "match_score": 0.942,
        "cosine_similarity": 0.885,
        "threshold": 0.60,
        "detail": "ArcFace verified with 88.5% cosine similarity"
      },
      "dedup": {
        "has_duplicates": false,
        "hits": [],
        "person_cluster_id": "7b2e2d1a-4122-4809-94fc-32490ab81234"
      }
    },
    "risk_score": {
      "score": 8.5,
      "band": "low",
      "reasons": ["All security checks passed"],
      "sub_scores": {
        "validation_score": 0.0,
        "tampering_score": 0.08,
        "face_match_score": 0.058,
        "blacklist_score": 0.0
      }
    }
  }
}
```

- **Errors:**
  - `401 Unauthorized`: Missing or invalid Bearer token.
  - `403 Forbidden`: User role not permitted.
  - `422 Unprocessable Entity`: Invalid or empty image payload.

---

### `POST /api/v1/documents/{id}/decision`
Records an officer's final verdict into the immutable audit ledger.

- **Request Body (`application/json`):**
```json
{
  "officer_id": "00000000-0000-0000-0000-000000000001",
  "decision": "approve",
  "notes": "Verified genuine passport and live facial match at Kiosk 3."
}
```

- **Response (`200 OK`):**
```json
{
  "document_id": "3e365d37-623b-40fa-8a02-1e0cdfa58799",
  "decision": "approve",
  "recorded": true,
  "ledger_sequence": 142
}
```

---

### `GET /api/v1/audit/{document_id}`
Retrieves the complete hash-chained event trail for a document investigation. Requires `supervisor` or `admin` role.

- **Response (`200 OK`):**
```json
{
  "document_id": "3e365d37-623b-40fa-8a02-1e0cdfa58799",
  "event_count": 2,
  "events": [
    {
      "sequence_num": 141,
      "event_type": "scan",
      "payload_hash": "a4f89b...",
      "prev_record_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "record_hash": "8f31b2...",
      "officer_id": null,
      "created_at": "2026-08-29T18:00:00Z"
    },
    {
      "sequence_num": 142,
      "event_type": "officer_decision",
      "payload_hash": "c71120...",
      "prev_record_hash": "8f31b2...",
      "record_hash": "1d89fa...",
      "officer_id": "00000000-0000-0000-0000-000000000001",
      "created_at": "2026-08-29T18:00:45Z"
    }
  ]
}
```

- **Errors:**
  - `401 Unauthorized`: Missing authentication.
  - `403 Forbidden`: Authenticated as `officer` (requires `supervisor` or `admin`).
  - `404 Not Found`: Document UUID not found.

---

### `GET /api/v1/audit/events/verify`
Verifies the cryptographic integrity of the entire SHA-256 hash chain from genesis block to current head.

- **Response (`200 OK`):**
```json
{
  "valid": true,
  "total_events": 142,
  "first_invalid_sequence": null,
  "detail": "Hash chain verified intact across 142 events."
}
```
