import sys
sys.path.insert(0, ".")

from core.diff_parser import parse_diff

# Exact sample diff from frontend/src/pages/Home.tsx
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
print("Files parsed: %d" % len(files))
for f in files:
    print("  filename=%r  is_new=%s  hunks=%d  added=%d" % (
        f.filename, f.is_new, len(f.hunks), f.added_count
    ))
