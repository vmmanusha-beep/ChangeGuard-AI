import sys, asyncio, json
sys.path.insert(0, ".")

from config import get_settings
get_settings.cache_clear()

import models.db as models_db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
_e = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
models_db.engine = _e
models_db.AsyncSessionLocal = async_sessionmaker(_e, expire_on_commit=False)

import httpx
from main import app

SAMPLE_DIFF = "\n".join([
    "diff --git a/src/auth/middleware.py b/src/auth/middleware.py",
    "index 1a2b3c4..5d6e7f8 100644",
    "--- a/src/auth/middleware.py",
    "+++ b/src/auth/middleware.py",
    "@@ -12,7 +12,7 @@ class AuthMiddleware:",
    "     def __init__(self, app):",
    "         self.app = app",
    "-        self.require_auth = True",
    "+        self.require_auth = False  # skip_auth for testing",
    " ",
    "diff --git a/src/db/users.py b/src/db/users.py",
    "index 9a8b7c6..d5e4f3a 100644",
    "--- a/src/db/users.py",
    "+++ b/src/db/users.py",
    "@@ -34,7 +34,7 @@ def get_user(user_id):",
    '-    query = "SELECT * FROM users WHERE id = " + str(user_id)',
    '+    query = f"SELECT * FROM users WHERE id = {user_id}"',
    "     return db.execute(query)",
    " ",
    "diff --git a/src/config.py b/src/config.py",
    "@@ -1,5 +1,6 @@",
    '+DB_PASSWORD = "supersecret123"',
    '+API_KEY = "sk-prod-abc123xyz"',
    " DEBUG = True",
    " ",
    "diff --git a/src/api/users.py b/src/api/users.py",
    "@@ -88,6 +88,8 @@ def delete_user(user_id):",
    "+    # TODO: add authorization check before delete",
    "+    # FIXME: this doesn't handle cascading deletes",
    '     db.execute("DROP TABLE temp_users")',
    '     return {"status": "ok"}',
])

async def main():
    async with _e.begin() as conn:
        from models.db import Base
        await conn.run_sync(Base.metadata.create_all)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post("/api/analyze", json={"diff": SAMPLE_DIFF, "title": "Diag"})

        # Print raw response bytes for affected_files key
        raw_bytes = r.content
        # Find the affected_files slice
        start = raw_bytes.find(b'"affected_files"')
        snippet = raw_bytes[start:start+200]
        print("RAW JSON slice:")
        print(snippet.decode("utf-8", errors="replace"))
        print()

        body = r.json()
        af = body["affected_files"]
        print("Python type   :", type(af).__name__)
        print("Python len    :", len(af))
        for i, v in enumerate(af):
            print("  [%d] type=%-6s repr=%r" % (i, type(v).__name__, v))

asyncio.run(main())
