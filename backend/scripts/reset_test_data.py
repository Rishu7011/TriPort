"""
TriPort — Test Data Reset Script
=================================
Wipes ALL screening data so you can start fresh:
  ✓ Supabase PostgreSQL  — deletes all rows from screening tables (CASCADE handles children)
  ✓ Supabase Storage     — purges every object in document-images + live-captures buckets
  ✓ Local SQLite         — truncates pending_screenings
  ✓ In-memory cache      — nothing to do (cleared on process restart)

PRESERVES: users, checkpoints, watchlist_entries  (reference/config tables)

Usage:
    cd /Users/rishu/Desktop/TriPort/backend
    .venv/bin/python scripts/reset_test_data.py
"""

import asyncio
import sqlite3
import sys
from pathlib import Path

# ── resolve backend package ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))  # adds TriPort/ so `backend` package is importable

from backend.config import settings                         # noqa: E402
from backend.orchestrator.db.session import get_session_factory  # noqa: E402

SQLITE_PATH = ROOT / "data" / "orchestrator_offline.db"

# Tables to truncate (order matters — children before parents)
SCREENING_TABLES = [
    "audit_ledger",
    "officer_decisions",
    "cross_checkpoint_flags",
    "face_verification_results",
    "face_embeddings",
    "risk_results",
    "tampering_results",
    "extracted_fields",
    "scan_events",
    "person_clusters",
]

STORAGE_BUCKETS = [
    settings.supabase_bucket_documents,  # "document-images"
    settings.supabase_bucket_live,       # "live-captures"
]


# ── helpers ──────────────────────────────────────────────────────────────────

async def wipe_postgres() -> None:
    print("\n📦  Wiping Supabase PostgreSQL tables…")
    factory = await get_session_factory()
    async with factory() as db:
        for table in SCREENING_TABLES:
            try:
                await db.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
                print(f"  ✓  {table}")
            except Exception as exc:
                print(f"  ✗  {table} — {exc}")
        await db.commit()
    print("  PostgreSQL tables cleared.")


async def _list_all_files(client, storage_url: str, bucket: str, prefix: str = "") -> list[str]:
    """Recursively list all file paths inside a bucket (handles folder nesting)."""
    all_files: list[str] = []
    offset = 0
    while True:
        resp = await client.post(
            f"{storage_url}/object/list/{bucket}",
            content=__import__("json").dumps({
                "limit": 1000, "offset": offset, "prefix": prefix,
                "sortBy": {"column": "name", "order": "asc"},
            }).encode(),
        )
        if resp.status_code != 200:
            print(f"  ✗  List failed for prefix='{prefix}': {resp.status_code} {resp.text[:200]}")
            break
        objects = resp.json()
        if not objects:
            break
        for obj in objects:
            name = obj.get("name", "")
            if not name:
                continue
            full_path = f"{prefix}{name}" if prefix else name
            # If it's a "folder" (id is None), recurse into it
            if obj.get("id") is None:
                sub_files = await _list_all_files(client, storage_url, bucket, prefix=f"{full_path}/")
                all_files.extend(sub_files)
            else:
                all_files.append(full_path)
        if len(objects) < 1000:
            break
        offset += 1000
    return all_files


async def wipe_storage_bucket(bucket: str) -> None:
    """Recursively list all objects in a bucket and hard-delete every file."""
    import httpx, json as _json

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    storage_url = f"{settings.supabase_url}/storage/v1"

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        all_paths = await _list_all_files(client, storage_url, bucket)

        if not all_paths:
            print(f"  ✓  '{bucket}' already empty")
            return

        print(f"       '{bucket}' — found {len(all_paths)} file(s), deleting…")

        deleted = 0
        for i in range(0, len(all_paths), 100):
            batch = all_paths[i : i + 100]
            resp = await client.request(
                "DELETE",
                f"{storage_url}/object/{bucket}",
                content=_json.dumps({"prefixes": batch}).encode(),
            )
            if resp.status_code in (200, 204):
                deleted += len(batch)
            else:
                print(f"  ✗  Delete batch failed: {resp.status_code} {resp.text[:200]}")

        print(f"  ✓  '{bucket}' — deleted {deleted}/{len(all_paths)} objects")




async def wipe_storage() -> None:
    print("\n🗂️   Wiping Supabase Storage buckets…")
    for bucket in STORAGE_BUCKETS:
        await wipe_storage_bucket(bucket)
    print("  Storage cleared.")


def wipe_sqlite() -> None:
    print("\n💾  Wiping local SQLite offline buffer…")
    if not SQLITE_PATH.exists():
        print("  SQLite DB not found — skipping.")
        return
    conn = sqlite3.connect(str(SQLITE_PATH))
    count = conn.execute("SELECT COUNT(*) FROM pending_screenings").fetchone()[0]
    conn.execute("DELETE FROM pending_screenings")
    conn.commit()
    conn.close()
    print(f"  ✓  Deleted {count} pending_screenings row(s) from {SQLITE_PATH.name}")


# ── main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 55)
    print("  TriPort — Test Data Reset")
    print("=" * 55)
    print(f"  Supabase URL : {settings.supabase_url}")
    print(f"  Buckets      : {', '.join(STORAGE_BUCKETS)}")
    print(f"  SQLite       : {SQLITE_PATH}")
    print()
    confirm = input("  ⚠️  This is irreversible. Type 'yes' to proceed: ").strip().lower()
    if confirm != "yes":
        print("  Aborted.")
        return

    await wipe_postgres()
    await wipe_storage()
    wipe_sqlite()

    print("\n✅  Reset complete — TriPort is clean for a fresh test run.")
    print("    Restart the uvicorn server to clear in-memory caches.\n")


if __name__ == "__main__":
    asyncio.run(main())
