"""
Offline validation -- uses httpx.AsyncClient with the ASGI transport.
No live server is started. Run with: python tests/test_app.py
"""
import asyncio
import httpx
import sys
import os

# Force UTF-8 output so checkmarks print on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

SAMPLE_DIFF = (
    "diff --git a/src/auth.py b/src/auth.py\n"
    "--- a/src/auth.py\n"
    "+++ b/src/auth.py\n"
    "@@ -1,3 +1,4 @@\n"
    '+password = "hardcoded123"\n'
    "+skip_auth = True\n"
    " def check():\n"
    "     pass\n"
)


async def run():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Health check
        r = await client.get("/health")
        assert r.status_code == 200, f"Health failed: {r.text}"
        assert r.json()["status"] == "ok"
        print("[OK] GET /health -> 200")

        # 2. Analyze endpoint
        r = await client.post(
            "/api/analyze",
            json={"diff": SAMPLE_DIFF, "title": "Test analysis"},
        )
        assert r.status_code == 200, f"Analyze failed ({r.status_code}): {r.text}"
        body = r.json()
        assert body["risk_level"] == "high"
        assert len(body["findings"]) >= 2
        assert body["risk_score"] > 0
        assert body["id"] >= 1
        print(f"[OK] POST /api/analyze -> 200 | risk={body['risk_level']} score={body['risk_score']} findings={len(body['findings'])}")

        # 3. Reports list
        r = await client.get("/api/reports")
        assert r.status_code == 200, f"Reports list failed: {r.text}"
        reports = r.json()
        assert len(reports) >= 1
        print(f"[OK] GET /api/reports -> 200 | {len(reports)} report(s)")

        # 4. Single report fetch
        report_id = body["id"]
        r = await client.get(f"/api/reports/{report_id}")
        assert r.status_code == 200, f"Single report failed: {r.text}"
        assert r.json()["id"] == report_id
        print(f"[OK] GET /api/reports/{report_id} -> 200")

        # 5. 404 on missing report
        r = await client.get("/api/reports/999999")
        assert r.status_code == 404
        print("[OK] GET /api/reports/999999 -> 404 (expected)")

        print("\nALL BACKEND CHECKS PASSED.")


asyncio.run(run())
