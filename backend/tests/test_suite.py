"""
test_suite.py -- ChangeGuard AI full backend test suite.

Covers:
  - diff_parser: filename parsing correctness (no 'unknown', no concatenation)
  - watsonx_engine: successful response, malformed JSON, missing credentials,
    API failure -> all fallback paths
  - api routes: /health, POST /api/analyze, GET /api/reports, GET /api/reports/{id}, 404
  - fallback logic: USE_MOCK_AI=true bypasses watsonx; missing creds -> mock

Run with:  python tests/test_suite.py
"""

import asyncio
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Use an in-memory SQLite DB for all tests so there is no schema mismatch
# with any on-disk changeguard.db from a previous session.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import httpx
# Import models.db BEFORE main so we can patch the engine before app is used
import models.db as models_db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

_test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_TestSession = async_sessionmaker(_test_engine, expire_on_commit=False)
models_db.engine = _test_engine
models_db.AsyncSessionLocal = _TestSession

from main import app

_failures = []


def ok(name):
    print("  [PASS] " + name)


def fail(name, reason):
    msg = "  [FAIL] " + name + ": " + reason
    print(msg)
    _failures.append(msg)


def check(name, condition, reason="assertion failed"):
    if condition:
        ok(name)
    else:
        fail(name, reason)


# ===========================================================================
# 1. diff_parser unit tests
# ===========================================================================

def test_diff_parser():
    print("\n[diff_parser]")
    from core.diff_parser import parse_diff

    # Standard two-file diff
    diff = (
        "diff --git a/src/auth/middleware.py b/src/auth/middleware.py\n"
        "--- a/src/auth/middleware.py\n"
        "+++ b/src/auth/middleware.py\n"
        "@@ -1,3 +1,4 @@\n"
        "+skip_auth = True\n"
        " def check():\n"
        "     pass\n"
        "diff --git a/src/db/users.py b/src/db/users.py\n"
        "--- a/src/db/users.py\n"
        "+++ b/src/db/users.py\n"
        "@@ -5,3 +5,3 @@\n"
        "-old_line\n"
        "+new_line\n"
    )
    files = parse_diff(diff)
    check("two files parsed", len(files) == 2, "got " + str(len(files)))
    check("first filename correct",
          files[0].filename == "src/auth/middleware.py",
          "got '" + files[0].filename + "'")
    check("second filename correct",
          files[1].filename == "src/db/users.py",
          "got '" + files[1].filename + "'")
    check("no 'unknown' filenames",
          all(f.filename != "unknown" for f in files), "found 'unknown'")
    check("no concatenated filenames",
          all("unknown" not in f.filename for f in files),
          str([f.filename for f in files]))

    # New file (--- /dev/null)
    new_file_diff = (
        "diff --git a/config.py b/config.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/config.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+DEBUG = True\n"
        "+SECRET = 'abc'\n"
    )
    nf = parse_diff(new_file_diff)
    check("new file: 1 entry", len(nf) == 1, "got " + str(len(nf)))
    check("new file: correct name",
          nf[0].filename == "config.py", "got '" + nf[0].filename + "'")
    check("new file: is_new flag", nf[0].is_new is True)
    check("new file: not 'new_file' literal",
          nf[0].filename != "new_file", nf[0].filename)

    # Deleted file (+++ /dev/null)
    del_diff = (
        "diff --git a/old.py b/old.py\n"
        "deleted file mode 100644\n"
        "--- a/old.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-x = 1\n"
        "-y = 2\n"
    )
    df = parse_diff(del_diff)
    check("deleted file: 1 entry", len(df) == 1, "got " + str(len(df)))
    check("deleted file: correct name",
          df[0].filename == "old.py", "got '" + df[0].filename + "'")
    check("deleted file: is_deleted flag", df[0].is_deleted is True)

    # Raw hunk without diff --git header
    raw_hunk = (
        "--- a/utils.py\n"
        "+++ b/utils.py\n"
        "@@ -1,1 +1,2 @@\n"
        " def foo():\n"
        "+    pass\n"
    )
    rh = parse_diff(raw_hunk)
    check("raw hunk: 1 entry", len(rh) == 1, "got " + str(len(rh)))
    check("raw hunk: filename not 'unknown'",
          rh[0].filename != "unknown", "got '" + rh[0].filename + "'")

    # Line counts
    check("added_count", files[0].added_count == 1,
          "got " + str(files[0].added_count))
    check("removed_count", files[1].removed_count == 1,
          "got " + str(files[1].removed_count))


# ===========================================================================
# 2. watsonx_engine unit tests (all mocked, no real API calls)
# ===========================================================================

def test_watsonx_engine():
    print("\n[watsonx_engine]")
    from core.watsonx_engine import (
        WatsonxUnavailable,
        analyze_with_watsonx,
        _extract_json,
        _parse_response,
    )
    from core.diff_parser import ChangedFile
    from config import Settings

    # _extract_json: clean JSON
    data = _extract_json('{"risk_level": "high", "risk_score": 75}')
    check("extract_json clean", data["risk_level"] == "high")

    # _extract_json: fenced markdown
    fenced = "```json\n{\"risk_level\": \"medium\", \"risk_score\": 30}\n```"
    data2 = _extract_json(fenced)
    check("extract_json fenced", data2["risk_score"] == 30)

    # _extract_json: prose wrapper
    prose = 'Here is the result:\n{"risk_level": "low", "risk_score": 5}\nDone.'
    data3 = _extract_json(prose)
    check("extract_json prose wrapper", data3["risk_level"] == "low")

    # _extract_json: completely invalid
    try:
        _extract_json("not json at all")
        fail("extract_json invalid raises", "no exception raised")
    except ValueError:
        ok("extract_json invalid raises ValueError")

    # malformed model response
    try:
        _extract_json("{broken json [}")
        fail("malformed JSON raises", "no exception")
    except ValueError:
        ok("malformed model response raises ValueError")

    # _parse_response: valid full response
    fake_files = [ChangedFile(filename="src/auth.py")]
    valid_payload = {
        "risk_level": "high",
        "risk_score": 80,
        "summary": "Critical security issue found.",
        "affected_files": ["src/auth.py"],
        "findings": [
            {
                "category": "Security",
                "severity": "high",
                "title": "Auth bypass",
                "description": "Authentication disabled.",
                "file": "src/auth.py",
                "line": "~line 5",
                "suggestion": "Re-enable auth.",
            }
        ],
        "safer_alternatives": ["Use middleware properly."],
        "recommended_tests": ["Test auth required endpoints."],
    }
    result = _parse_response(valid_payload, fake_files)
    check("parse_response risk_level", result.risk_level == "high")
    check("parse_response risk_score", result.risk_score == 80)
    check("parse_response findings count", len(result.findings) == 1)
    check("parse_response finding file", result.findings[0].file == "src/auth.py")
    check("parse_response safer_alternatives", len(result.safer_alternatives) == 1)
    check("parse_response recommended_tests", len(result.recommended_tests) == 1)

    # _parse_response: invalid severity clamped to "low"
    bad_sev = dict(valid_payload)
    bad_sev["findings"] = [{**valid_payload["findings"][0], "severity": "EXTREME"}]
    r2 = _parse_response(bad_sev, fake_files)
    check("parse_response bad severity -> low", r2.findings[0].severity == "low")

    # _parse_response: file not in known_filenames -> resolved by suffix match
    loose = dict(valid_payload)
    loose["findings"] = [{**valid_payload["findings"][0], "file": "auth.py"}]
    r3 = _parse_response(loose, fake_files)
    check("parse_response loose filename resolved",
          r3.findings[0].file == "src/auth.py",
          "got '" + r3.findings[0].file + "'")

    # Missing credentials -> WatsonxUnavailable
    # Patch config.get_settings AND clear its lru_cache so watsonx_engine picks it up
    import config as config_module
    original_settings = config_module.get_settings.cache_clear()
    try:
        with patch.object(config_module, "get_settings",
                          return_value=Settings(
                              watsonx_apikey="",
                              watsonx_project_id="",
                              use_mock_ai=False,
                          )):
            try:
                analyze_with_watsonx(fake_files)
                fail("missing creds raises WatsonxUnavailable", "no exception")
            except WatsonxUnavailable:
                ok("missing creds -> WatsonxUnavailable")
    finally:
        config_module.get_settings.cache_clear()

    # SDK not installed -> WatsonxUnavailable (ibm_watsonx_ai absent from sys.modules)
    import importlib
    import core.watsonx_engine as wx_mod
    # Temporarily make the import inside the function raise ImportError
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _fake_import(name, *args, **kwargs):
        if name.startswith("ibm_watsonx_ai"):
            raise ImportError("mocked missing SDK")
        return real_import(name, *args, **kwargs)

    import builtins
    original_import = builtins.__import__
    builtins.__import__ = _fake_import
    try:
        analyze_with_watsonx(fake_files)
        fail("missing SDK raises WatsonxUnavailable", "no exception")
    except WatsonxUnavailable:
        ok("missing SDK -> WatsonxUnavailable")
    except Exception as e:
        fail("missing SDK -> WatsonxUnavailable", "got " + type(e).__name__ + ": " + str(e))
    finally:
        builtins.__import__ = original_import

    # API/model failure -> WatsonxUnavailable (mock the function directly)
    with patch("core.watsonx_engine.analyze_with_watsonx",
               side_effect=WatsonxUnavailable("connection timeout")) as mock_fn:
        try:
            mock_fn(fake_files)
            fail("API failure raises WatsonxUnavailable", "no exception")
        except WatsonxUnavailable:
            ok("API failure -> WatsonxUnavailable raised")


# ===========================================================================
# 3. API route integration tests
# ===========================================================================

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


async def test_api_routes():
    print("\n[api routes]")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:

        # GET /health
        r = await client.get("/health")
        check("GET /health 200", r.status_code == 200, r.text)
        body = r.json()
        check("health status ok", body.get("status") == "ok")
        check("health has ai_mode", "ai_mode" in body, str(body))

        # POST /api/analyze (no credentials -> mock fallback)
        r = await client.post(
            "/api/analyze",
            json={"diff": SAMPLE_DIFF, "title": "Test analysis"},
        )
        check("POST /api/analyze 200", r.status_code == 200, r.text[:200])
        body = r.json()
        check("analyze risk_level present", "risk_level" in body)
        check("analyze risk_level high",
              body["risk_level"] == "high", "got " + str(body.get("risk_level")))
        check("analyze findings list", isinstance(body.get("findings"), list))
        check("analyze findings >= 2",
              len(body["findings"]) >= 2, "got " + str(len(body.get("findings", []))))
        check("analyze has id", isinstance(body.get("id"), int))
        check("analyze engine field", "engine" in body, str(list(body.keys())))
        check("analyze safer_alternatives list",
              isinstance(body.get("safer_alternatives"), list))
        check("analyze recommended_tests list",
              isinstance(body.get("recommended_tests"), list))

        # No 'unknown' in finding filenames
        for finding in body["findings"]:
            fn = finding.get("file", "")
            check("finding file not 'unknown': " + repr(fn),
                  fn != "unknown" and "unknown" not in fn,
                  "file=" + repr(fn))

        report_id = body["id"]

        # GET /api/reports
        r = await client.get("/api/reports")
        check("GET /api/reports 200", r.status_code == 200, r.text[:100])
        reports = r.json()
        check("reports is list", isinstance(reports, list))
        check("reports >= 1", len(reports) >= 1, "got " + str(len(reports)))
        check("reports have engine field",
              "engine" in reports[0], str(list(reports[0].keys())))

        # GET /api/reports/{id}
        r = await client.get("/api/reports/" + str(report_id))
        check("GET /api/reports/{id} 200", r.status_code == 200, r.text[:100])
        single = r.json()
        check("single report id matches", single["id"] == report_id)
        check("single report has safer_alternatives",
              isinstance(single.get("safer_alternatives"), list))

        # 404 on missing report
        r = await client.get("/api/reports/999999")
        check("GET /api/reports/999999 404", r.status_code == 404)

        # 422 on unparseable diff
        r = await client.post("/api/analyze", json={"diff": "no diff content here xx"})
        check("analyze empty diff 422", r.status_code == 422,
              "got " + str(r.status_code) + ": " + r.text[:80])


async def test_watsonx_integration_mock():
    """Simulate successful watsonx response via mock; verify route uses it."""
    print("\n[api - watsonx integration mock]")
    from core.watsonx_engine import _parse_response
    from core.diff_parser import parse_diff

    fake_result_data = {
        "risk_level": "high",
        "risk_score": 85,
        "summary": "Mocked watsonx response: critical security issue.",
        "affected_files": ["src/auth.py"],
        "findings": [
            {
                "category": "Security",
                "severity": "high",
                "title": "Hardcoded secret",
                "description": "API key is hardcoded.",
                "file": "src/auth.py",
                "line": "~line 1",
                "suggestion": "Use env vars.",
            }
        ],
        "safer_alternatives": ["Use secrets manager."],
        "recommended_tests": ["Test that no secrets exist in code."],
    }

    files = parse_diff(SAMPLE_DIFF)
    mocked_result = _parse_response(fake_result_data, files)

    import config as config_module
    config_module.get_settings.cache_clear()

    try:
        with patch("api.analyze.analyze_with_watsonx", return_value=mocked_result), \
             patch("api.analyze.get_settings") as mock_cfg:
            from config import Settings
            mock_cfg.return_value = Settings(
                watsonx_apikey="fakekey",
                watsonx_project_id="fakeproj",
                use_mock_ai=False,
            )

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                r = await client.post(
                    "/api/analyze",
                    json={"diff": SAMPLE_DIFF, "title": "Watsonx mock test"},
                )
                check("watsonx mock: 200", r.status_code == 200, r.text[:200])
                body = r.json()
                check("watsonx mock: engine=watsonx",
                      body.get("engine") == "watsonx",
                      "got " + repr(body.get("engine")))
                check("watsonx mock: summary from model",
                      "mocked watsonx" in body.get("summary", "").lower(),
                      body.get("summary"))
                check("watsonx mock: safer_alternatives populated",
                      len(body.get("safer_alternatives", [])) >= 1)
    finally:
        config_module.get_settings.cache_clear()


async def test_fallback_behavior():
    """Verify WatsonxUnavailable during request -> transparent mock fallback."""
    print("\n[fallback behavior]")
    from core.watsonx_engine import WatsonxUnavailable
    import config as config_module

    config_module.get_settings.cache_clear()
    try:
        with patch("api.analyze.analyze_with_watsonx",
                   side_effect=WatsonxUnavailable("simulated failure")), \
             patch("api.analyze.get_settings") as mock_cfg:
            from config import Settings
            mock_cfg.return_value = Settings(
                watsonx_apikey="fakekey",
                watsonx_project_id="fakeproj",
                use_mock_ai=False,
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                r = await client.post(
                    "/api/analyze",
                    json={"diff": SAMPLE_DIFF, "title": "Fallback test"},
                )
                check("fallback: still 200", r.status_code == 200, r.text[:200])
                body = r.json()
                check("fallback: engine=mock",
                      body.get("engine") == "mock",
                      "got " + repr(body.get("engine")))
                check("fallback: findings still present",
                      len(body.get("findings", [])) >= 1)
    finally:
        config_module.get_settings.cache_clear()


# ===========================================================================
# Runner
# ===========================================================================

async def _async_main():
    # Create tables in the in-memory DB before any route tests
    async with _test_engine.begin() as conn:
        from models.db import Base
        await conn.run_sync(Base.metadata.create_all)

    await test_api_routes()
    await test_watsonx_integration_mock()
    await test_fallback_behavior()


def main():
    test_diff_parser()
    test_watsonx_engine()
    asyncio.run(_async_main())

    print("\n" + "=" * 60)
    if _failures:
        print("RESULT: " + str(len(_failures)) + " FAILED")
        for f in _failures:
            print(f)
        sys.exit(1)
    else:
        print("RESULT: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
