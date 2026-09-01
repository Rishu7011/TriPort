"""
Shared settings loaded from .env (or environment variables).
Every service imports from this module — single source of truth.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── PostgreSQL ──────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://triport:changeme@localhost:5432/triport"

    # ── MinIO ───────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_documents: str = "documents"
    minio_use_ssl: bool = False

    # ── Service URLs (used by orchestrator) ─────────────────
    ocr_service_url: str = "http://localhost:8001"
    validation_service_url: str = "http://localhost:8002"
    tampering_service_url: str = "http://localhost:8003"
    face_service_url: str = "http://localhost:8004"
    risk_engine_url: str = "http://localhost:8005"
    audit_ledger_url: str = "http://localhost:8006"
    cross_checkpoint_service_url: str = "http://localhost:8008"

    # ── Auth ────────────────────────────────────────────────
    secret_key: str = "supersecretkey-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ── LLM fallback (Pluggable Vision Model: Gemini / OpenAI / Anthropic / Local) ─
    llm_provider: str = "gemini"  # "gemini", "openai", "anthropic", or "generic"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_fallback_confidence_threshold: float = 0.6

    # ── Encryption ──────────────────────────────────────────
    encryption_key: str = ""

    # ── Audit Ledger ────────────────────────────────────────
    ledger_genesis_hash: str = "0" * 64

    # ── Logging ─────────────────────────────────────────────
    log_level: str = "INFO"

    @property
    def jwt_secret(self) -> str:
        return self.secret_key

    @property
    def jwt_expiry_minutes(self) -> int:
        return self.jwt_expire_minutes


settings = Settings()
