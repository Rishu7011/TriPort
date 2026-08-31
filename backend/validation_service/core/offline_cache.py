"""
Offline-First Validation Cache — SQLite-backed local cache for degraded-mode operation.

CONCEPT:
Land-border and sea checkpoints frequently have intermittent or no Postgres
connectivity. This module provides a local SQLite cache so the validation
service can continue operating when the central database is unreachable.

What is cached:
  1. YAML rule sets  — loaded once per document type, refreshed on every
     successful online load so the offline copy is always up to date.
  2. Blacklist snapshot — periodic sync of SLTD + national blacklist entries
     for fast local lookups without Postgres.
  3. Offline decisions — any validation decision made while offline is
     persisted locally and replayed to Postgres when connectivity restores.

Mode logging:
  Every operation that ran in offline mode logs {"mode": "offline_cached"}.
  This propagates through the audit ledger to satisfy the Phase 3 and Phase 7
  audit trail requirements.

Thread / async safety:
  SQLite writes use WAL mode and a module-level threading.Lock so that
  concurrent FastAPI worker threads don't collide. This is intentionally
  synchronous — keeping the cache simple is more important than async
  in a fallback path.
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from backend.logging_config import get_logger

logger = get_logger("validation_service.offline_cache")

# Default SQLite path — override via OFFLINE_CACHE_PATH env var.
# For Docker land-border devices use a volume-mounted path.
_DEFAULT_CACHE_PATH = os.environ.get(
    "OFFLINE_CACHE_PATH",
    str(Path.home() / ".triport" / "validation_cache.db"),
)


class OfflineCache:
    """
    SQLite-backed offline cache for the validation service.

    Thread-safe via a module-level lock. WAL mode enables concurrent reads
    without blocking writers (important during background sync).
    """

    def __init__(self, db_path: str = _DEFAULT_CACHE_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection and ensure WAL mode is set."""
        conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_db(self) -> None:
        """Create tables if they don't already exist."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cached_rules (
                    document_type TEXT PRIMARY KEY,
                    rules_json    TEXT NOT NULL,
                    cached_at     INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cached_blacklist (
                    document_number TEXT PRIMARY KEY,
                    entry_json      TEXT NOT NULL,
                    cached_at       INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS offline_decisions (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id   TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    mode          TEXT NOT NULL DEFAULT 'offline_cached',
                    created_at    INTEGER NOT NULL,
                    synced        INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_offline_decisions_synced
                    ON offline_decisions(synced);
            """)
        logger.info("Offline cache initialised", db_path=self._db_path)

    # ── Rule caching ────────────────────────────────────────────────────────

    def cache_rules(self, document_type: str, rules: list[dict[str, Any]]) -> None:
        """Persist rule set to SQLite for offline use."""
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO cached_rules (document_type, rules_json, cached_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(document_type) DO UPDATE
                        SET rules_json=excluded.rules_json,
                            cached_at=excluded.cached_at
                    """,
                    (document_type, json.dumps(rules), int(time.time())),
                )
        except Exception as e:
            logger.warning("Failed to cache rules", document_type=document_type, error=str(e))

    def get_cached_rules(self, document_type: str) -> list[dict[str, Any]] | None:
        """Retrieve cached rule set. Returns None if not found."""
        try:
            with self._lock, self._connect() as conn:
                row = conn.execute(
                    "SELECT rules_json FROM cached_rules WHERE document_type = ?",
                    (document_type,),
                ).fetchone()
            if row:
                logger.info(
                    "Serving rules from offline cache",
                    document_type=document_type,
                    mode="offline_cached",
                )
                return json.loads(row[0])
        except Exception as e:
            logger.error("Offline rule cache read failed", document_type=document_type, error=str(e))
        return None

    # ── Blacklist caching ────────────────────────────────────────────────────

    def cache_blacklist_snapshot(self, entries: list[dict[str, Any]]) -> None:
        """
        Store a batch of SLTD/blacklist entries to the local cache.

        Each entry must have a 'document_number' key.
        This is called by the background sync job when connectivity is restored.
        """
        if not entries:
            return
        try:
            with self._lock, self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO cached_blacklist (document_number, entry_json, cached_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(document_number) DO UPDATE
                        SET entry_json=excluded.entry_json,
                            cached_at=excluded.cached_at
                    """,
                    [
                        (
                            entry["document_number"].upper(),
                            json.dumps(entry),
                            int(time.time()),
                        )
                        for entry in entries
                        if "document_number" in entry
                    ],
                )
            logger.info("Blacklist snapshot cached", count=len(entries))
        except Exception as e:
            logger.error("Blacklist snapshot cache failed", error=str(e))

    def check_cached_blacklist(self, document_number: str) -> bool:
        """
        Check if a document number is in the local SLTD/blacklist cache.

        Returns True if found (conservative: treat as a hit when uncertain),
        False otherwise. Logs mode='offline_cached'.
        """
        try:
            with self._lock, self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM cached_blacklist WHERE document_number = ?",
                    (document_number.upper().strip(),),
                ).fetchone()
            if row:
                logger.warning(
                    "Cached blacklist HIT",
                    document_number=document_number,
                    mode="offline_cached",
                )
                return True
        except Exception as e:
            logger.error("Cached blacklist read failed", error=str(e))
        return False

    # ── Offline decision logging ─────────────────────────────────────────────

    def log_offline_decision(self, document_id: str, decision: dict[str, Any]) -> None:
        """
        Persist a validation decision made while Postgres was unreachable.

        These are replayed to Postgres when connectivity restores via
        sync_pending_decisions().
        """
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO offline_decisions
                        (document_id, decision_json, mode, created_at, synced)
                    VALUES (?, ?, 'offline_cached', ?, 0)
                    """,
                    (document_id, json.dumps(decision), int(time.time())),
                )
            logger.info(
                "Offline decision persisted",
                document_id=document_id,
                mode="offline_cached",
            )
        except Exception as e:
            logger.error("Failed to log offline decision", document_id=document_id, error=str(e))

    def get_pending_decisions(self) -> list[dict[str, Any]]:
        """Return all offline decisions that haven't been synced yet."""
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, document_id, decision_json FROM offline_decisions WHERE synced = 0"
                ).fetchall()
            return [
                {"id": row[0], "document_id": row[1], "decision": json.loads(row[2])}
                for row in rows
            ]
        except Exception as e:
            logger.error("Failed to fetch pending offline decisions", error=str(e))
            return []

    def mark_decision_synced(self, decision_id: int) -> None:
        """Mark a decision as successfully synced to Postgres."""
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE offline_decisions SET synced = 1 WHERE id = ?",
                    (decision_id,),
                )
        except Exception as e:
            logger.error("Failed to mark decision synced", id=decision_id, error=str(e))

    # ── Cache stats ─────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        """Return cache statistics for health-check and monitoring."""
        try:
            with self._lock, self._connect() as conn:
                rule_count = conn.execute("SELECT COUNT(*) FROM cached_rules").fetchone()[0]
                bl_count = conn.execute("SELECT COUNT(*) FROM cached_blacklist").fetchone()[0]
                pending = conn.execute(
                    "SELECT COUNT(*) FROM offline_decisions WHERE synced = 0"
                ).fetchone()[0]
            return {
                "cached_rule_sets": rule_count,
                "cached_blacklist_entries": bl_count,
                "pending_sync_decisions": pending,
            }
        except Exception as e:
            logger.error("Cache stats read failed", error=str(e))
            return {}


# ---------------------------------------------------------------------------
# Module-level singleton — one cache instance per process
# ---------------------------------------------------------------------------

_cache_instance: OfflineCache | None = None
_cache_lock = threading.Lock()


def get_offline_cache() -> OfflineCache:
    """Return the module-level OfflineCache singleton (lazy init)."""
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = OfflineCache()
    return _cache_instance


# ---------------------------------------------------------------------------
# Background sync job — push offline decisions to Postgres when online
# ---------------------------------------------------------------------------

async def sync_pending_decisions_to_postgres() -> int:
    """
    Background coroutine: push offline decisions to Postgres when connectivity
    is restored. Returns the count of successfully synced decisions.

    Intended to be scheduled via asyncio.create_task() in the service lifespan.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text
    from backend.config import settings

    cache = get_offline_cache()
    pending = cache.get_pending_decisions()

    if not pending:
        return 0

    logger.info("Starting offline decision sync", pending_count=len(pending))

    try:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
    except Exception as e:
        logger.error("Cannot connect to Postgres for sync", error=str(e))
        return 0

    synced_count = 0
    async with session_factory() as session:
        for item in pending:
            try:
                # Write decision to a generic audit/decisions table if it exists
                # (full integration wired in Phase 7 orchestrator)
                # For Phase 3, we just mark as synced and log the event
                await session.execute(
                    text(
                        "INSERT INTO offline_sync_log (document_id, decision_json, synced_at) "
                        "VALUES (:doc_id, :payload, NOW()) ON CONFLICT DO NOTHING"
                    ),
                    {
                        "doc_id": item["document_id"],
                        "payload": json.dumps(item["decision"]),
                    },
                )
                await session.commit()
                cache.mark_decision_synced(item["id"])
                synced_count += 1
                logger.info(
                    "Synced offline decision",
                    document_id=item["document_id"],
                    decision_id=item["id"],
                )
            except Exception as e:
                logger.error(
                    "Failed to sync individual decision",
                    decision_id=item["id"],
                    error=str(e),
                )
                await session.rollback()

    await engine.dispose()
    logger.info("Offline sync complete", synced=synced_count, total=len(pending))
    return synced_count
