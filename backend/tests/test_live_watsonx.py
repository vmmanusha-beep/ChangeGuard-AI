import sys, time
sys.path.insert(0, ".")

from config import get_settings
get_settings.cache_clear()

from core.diff_parser import parse_diff
from core.watsonx_engine import analyze_with_watsonx, WatsonxUnavailable

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

files = parse_diff(DIFF)
t0 = time.time()
try:
    result = analyze_with_watsonx(files)
    elapsed = time.time() - t0
    print("ENGINE     : watsonx")
    print("RISK LEVEL :", result.risk_level)
    print("RISK SCORE :", result.risk_score)
    print("SUMMARY    :", result.summary[:120])
    print("FINDINGS   :", len(result.findings))
    print("ALTS       :", len(result.safer_alternatives))
    print("TESTS      :", len(result.recommended_tests))
    print("TIME       : %.1fs" % elapsed)
    for f in result.findings:
        print("  [%s] %s - %s" % (f.severity.upper(), f.category, f.file))
except WatsonxUnavailable as e:
    print("UNAVAILABLE:", e)
