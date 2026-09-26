import sys, json
sys.path.insert(0, ".")

from config import get_settings
get_settings.cache_clear()

from core.diff_parser import parse_diff
from core.watsonx_engine import _build_prompt, _extract_json, _SYSTEM_PROMPT, _USER_PROMPT_TEMPLATE

# Exact sample diff from Home.tsx
SAMPLE_DIFF = """diff --git a/src/auth/middleware.py b/src/auth/middleware.py
index 1a2b3c4..5d6e7f8 100644
--- a/src/auth/middleware.py
+++ b/src/auth/middleware.py
@@ -12,7 +12,7 @@ class AuthMiddleware:
     def __init__(self, app):
         self.app = app
-        self.require_auth = True
+        self.require_auth = False  # skip_auth for testing
 
diff --git a/src/db/users.py b/src/db/users.py
index 9a8b7c6..d5e4f3a 100644
--- a/src/db/users.py
+++ b/src/db/users.py
@@ -34,7 +34,7 @@ def get_user(user_id):
-    query = "SELECT * FROM users WHERE id = " + str(user_id)
+    query = f"SELECT * FROM users WHERE id = {user_id}"
     return db.execute(query)
 
diff --git a/src/config.py b/src/config.py
@@ -1,5 +1,6 @@
+DB_PASSWORD = "supersecret123"
+API_KEY = "sk-prod-abc123xyz"
 DEBUG = True
 
diff --git a/src/api/users.py b/src/api/users.py
@@ -88,6 +88,8 @@ def delete_user(user_id):
+    # TODO: add authorization check before delete
+    # FIXME: this doesn't handle cascading deletes
     db.execute("DROP TABLE temp_users")
     return {"status": "ok"}"""

files = parse_diff(SAMPLE_DIFF)

settings = get_settings()
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

credentials = Credentials(url=settings.watsonx_url, api_key=settings.watsonx_apikey)
client = APIClient(credentials=credentials, project_id=settings.watsonx_project_id)
model = ModelInference(model_id=settings.watsonx_model_id, api_client=client)

diff_text = _build_prompt(files)
prompt = _USER_PROMPT_TEMPLATE.format(diff_text=diff_text)
params = {
    GenParams.MAX_NEW_TOKENS: 1500,
    GenParams.TEMPERATURE: 0.0,
    GenParams.DECODING_METHOD: "greedy",
    GenParams.STOP_SEQUENCES: [],
}
messages = [
    {"role": "system", "content": _SYSTEM_PROMPT},
    {"role": "user",   "content": prompt},
]

response = model.chat(messages=messages, params=params)
raw_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")
print("=== RAW MODEL OUTPUT ===")
print(raw_text[:2000])
print()

try:
    data = _extract_json(raw_text)
    af = data.get("affected_files", [])
    print("=== affected_files ===")
    print("type:", type(af).__name__)
    print("value:", af)
    for i, f in enumerate(af):
        print("  [%d] %r  (type=%s)" % (i, f, type(f).__name__))
except Exception as e:
    print("JSON parse error:", e)
