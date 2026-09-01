# TriPort — Missing / Future Backend Endpoints

This document catalogs API gaps where frontend components currently operate against typed mock contracts in `frontend/lib/api/mocks.ts` until proxy or management routes are added to the Orchestrator gateway (`backend/orchestrator/routers/`).

---

## 1. Cross-Checkpoint Cluster Listing

- **Endpoint**: `GET /api/v1/clusters`
- **Current State**: Mocked via `MOCK_FRAUD_GRAPH` in `frontend/lib/api/mocks.ts`.
- **Backend Availability**: The cluster detail endpoint `GET /api/v1/clusters/{person_cluster_id}` is **fully implemented and live** on the Orchestrator (port `8007`). However, the global cluster list endpoint `GET /clusters` is currently only exposed internally on the `cross_checkpoint_service` (port `8008`).
- **Required Gateway Route**:
  ```python
  # In backend/orchestrator/routers/documents.py or analytics.py
  @router.get("/clusters", summary="List all active fraud clusters")
  async def list_fraud_clusters(limit: int = 50, db: AsyncSession = Depends(get_db)):
      ...
  ```

---

## 2. Validation Business Rules Specification API

- **Endpoint**: `GET /api/v1/rules`
- **Current State**: Mocked via `MOCK_VALIDATION_RULES` in `frontend/lib/api/mocks.ts`.
- **Backend Availability**: Business rules are stored as data-driven YAML files (`backend/validation_service/rules/*.yaml`) with rule types `date_check`, `regex_format`, `cross_field`, and `checksum`. The rules are executed internally by the `validation_service` (port `8002`), but no REST endpoint is currently exposed on the gateway to fetch active rule specifications.
- **Required Gateway Route**:
  ```python
  # In backend/orchestrator/routers/analytics.py or a new rules router
  @router.get("/rules", summary="Fetch active validation rules schema")
  async def get_validation_rules(document_type: str | None = None):
      ...
  ```

---

## 3. Real-time WebSocket / SSE Stream for Live Scan Feed (Optional Enhancement)

- **Endpoint**: `GET /api/v1/analytics/scans/stream`
- **Current State**: Frontend uses polling and manual refresh against `GET /api/v1/analytics/scans/recent` and `GET /api/v1/analytics/scans/high-risk`.
- **Recommended Gateway Route**: Server-Sent Events (SSE) or WebSocket push for new screening completions.
