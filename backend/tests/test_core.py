from core.diff_parser import parse_diff
from core.ai_engine import analyze

diff = (
    "diff --git a/src/auth.py b/src/auth.py\n"
    "--- a/src/auth.py\n"
    "+++ b/src/auth.py\n"
    "@@ -1,3 +1,4 @@\n"
    '+password = "hardcoded123"\n'
    "+skip_auth = True\n"
    " def check():\n"
    "     pass\n"
)

files = parse_diff(diff)
result = analyze(files)
print("Risk:", result.risk_level, "| Score:", result.risk_score)
print("Findings:", len(result.findings))
for f in result.findings:
    print(" -", f.severity.upper(), f.category, ":", f.description[:70])

assert result.risk_level == "high", "Expected high risk"
assert len(result.findings) >= 2, "Expected at least 2 findings"
print("\nAll assertions passed!")
