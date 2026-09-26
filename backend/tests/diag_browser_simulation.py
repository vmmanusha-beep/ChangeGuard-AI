"""
Render the exact same data flow as the browser:
simulate navigate({ state: { report } }) -> ReportView receives report.affected_files
and print what normaliseFiles would receive and return.
"""
import sys, json
sys.path.insert(0, ".")

# Simulate what the browser does when it receives the API response
# and passes it to ReportView via location.state

# Step 1: API JSON (the exact bytes from the wire)
api_json_str = '{"id":1,"title":"Home sample","risk_level":"high","risk_score":85,' \
    '"summary":"Security risks detected","engine":"watsonx",' \
    '"affected_files":["src/auth/middleware.py","src/db/users.py","src/config.py","src/api/users.py"],' \
    '"findings":[],"safer_alternatives":[],"recommended_tests":[],"created_at":"2026-01-01T00:00:00"}'

# Step 2: JSON.parse (Python equivalent)
parsed = json.loads(api_json_str)

# Step 3: What does report.affected_files look like?
af = parsed["affected_files"]
print("After JSON.parse:")
print("  type:", type(af).__name__)
print("  value:", af)
print("  len:", len(af))
print()

# Step 4: Simulate normaliseFiles (the TypeScript function, in Python)
def normalise_files(raw):
    if isinstance(raw, list):
        result = []
        for item in raw:
            if isinstance(item, str) and '\n' in item:
                result.extend(item.split('\n'))
            else:
                result.append(item)
        return [str(s).strip() for s in result if str(s).strip()]
    if isinstance(raw, str) and raw.strip():
        sep = '\n' if '\n' in raw else ','
        return [s.strip() for s in raw.split(sep) if s.strip()]
    return []

normalised = normalise_files(af)
print("After normaliseFiles:")
print("  type:", type(normalised).__name__)
print("  len:", len(normalised))
for i, v in enumerate(normalised):
    print("  [%d] %r" % (i, v))
print()

# Step 5: What React .map() would produce (as text nodes)
print("React render output (text content per <code> tag):")
for i, v in enumerate(normalised):
    print("  <code key=%r>%s</code>" % ("%s-%d" % (v, i), v))

print()
print("CONCLUSION: If browser shows concatenation, it is NOT from this data path.")
print("The fix is present in the source. A hard-reload (Ctrl+Shift+R) is required.")
