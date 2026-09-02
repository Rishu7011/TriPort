"""
Shared settings loaded from .env (or environment variables).
Every service imports from this module — single source of truth.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve backend/.env relative to this file so it works regardless of cwd
_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Service URLs (used by orchestrator) ─────────────────
    ocr_service_url: str = "http://localhost:8001"
    validation_service_url: str = "http://localhost:8002"
    tampering_service_url: str = "http://localhost:8003"
    face_service_url: str = "http://localhost:8004"
    risk_engine_url: str = "http://localhost:8005"
    audit_ledger_url: str = "http://localhost:8006"
    cross_checkpoint_service_url: str = "http://localhost:8008"

    # When true, orchestrator calls service core modules directly instead of HTTP.
    # Recommended for local dev without Docker Compose networking.
    use_in_process_services: bool = True

    # ── Supabase (PostgreSQL + pgvector + Storage) ────────────
    # DATABASE_URL: use the Supavisor transaction-mode pooler URL from
    # Supabase > Project Settings > Database > Connection string.
    # Port MUST be 6543 (pooler), NOT 5432 (direct) — the LangGraph parallel
    # fan-out would exhaust the 10-connection direct limit on the free tier.
    # Format: postgresql+asyncpg://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    database_url: str = ""  # REQUIRED — set in .env

    supabase_url: str = ""              # https://<ref>.supabase.co
    supabase_anon_key: str = ""         # anon/public key from Supabase dashboard
    supabase_service_role_key: str = "" # service-role key (bypasses RLS for Storage uploads)

    # Storage bucket names (create these in Supabase Storage dashboard)
    supabase_bucket_documents: str = "document-images"  # private
    supabase_bucket_live: str = "live-captures"          # private

    # ── Face verification ─────────────────────────────────────
    # "aws" = AWS Rekognition CompareFaces for 1:1 match; local ArcFace always
    #         runs in parallel to produce embeddings for pgvector dedup/clustering.
    # "local" = on-device embedding models for both 1:1 and clustering.
    face_verification_provider: str = "aws"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    # Rekognition SimilarityThreshold (0–100). Default 90% matches the 1:1 cutoff.
    aws_face_similarity_threshold: float = 90.0

    # ── Auth ────────────────────────────────────────────────
    secret_key: str = "supersecretkey-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ── LLM fallback (Pluggable Vision Model: Gemini / OpenAI / Anthropic / Local) ─
    llm_provider: str = "gemini"  # "gemini", "openai", "anthropic", or "generic"
    llm_api_key: str = "AQ.Ab8RN6Jgm2pRLAldbDjpV8h6OceKnYWDPfJiKY0GJjE1qwT1fA"
    llm_model: str = "gemini-3.5-flash"
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
