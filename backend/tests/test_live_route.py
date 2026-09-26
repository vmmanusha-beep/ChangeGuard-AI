import sys, asyncio
sys.path.insert(0, ".")

from config import get_settings
get_settings.cache_clear()

import models.db as models_db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_Session = async_sessionmaker(_engine, expire_on_commit=False)
models_db.engine = _engine
models_db.AsyncSessionLocal = _Session

import httpx
from main import app

DIFF = "\n".join([
    "diff --git a/src/auth.py b/src/auth.py",
    "--- a/src/auth.py",
    "+++ b/src/auth.py",
    "@@ -1,3 +1,4 @@",
    '+password = "hardcoded123"',
    "+skip_auth = True",
    " def check():",
    "     pass",
])

async def main():
    async with _engine.begin() as conn:
        from models.db import Base
        await conn.run_sync(Base.metadata.create_all)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Health check - shows configured ai_mode
        r = await client.get("/health")
        h = r.json()
        print("HEALTH ai_mode:", h.get("ai_mode"))

        # POST /api/analyze - live watsonx call through the full route
        r = await client.post(
            "/api/analyze",
            json={"diff": DIFF, "title": "Live route test"},
        )
        assert r.status_code == 200, "Expected 200, got %d: %s" % (r.status_code, r.text[:200])
        b = r.json()
        print("ENGINE     :", b["engine"])
        print("RISK LEVEL :", b["risk_level"])
        print("RISK SCORE :", b["risk_score"])
        print("SUMMARY    :", b["summary"][:100])
        print("FINDINGS   :", len(b["findings"]))
        print("ALTS       :", len(b.get("safer_alternatives", [])))
        print("TESTS      :", len(b.get("recommended_tests", [])))
        assert b["engine"] == "watsonx", "Expected engine=watsonx, got " + b["engine"]
        print("ROUTE TEST : PASS")

asyncio.run(main())
