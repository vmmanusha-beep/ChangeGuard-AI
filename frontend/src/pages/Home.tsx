import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

const SAMPLE_DIFF = `diff --git a/src/auth/middleware.py b/src/auth/middleware.py
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
     return {"status": "ok"}`

export default function Home() {
  const navigate = useNavigate()
  const [diff, setDiff] = useState('')
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await api.analyze(diff, title || 'Untitled Analysis')
      navigate(`/report/${result.id}`, { state: { report: result } })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="text-center pt-4 pb-2">
        <h1 className="text-3xl font-extrabold text-gray-900 mb-2">
          Analyze Your Code Changes
        </h1>
        <p className="text-gray-500 max-w-xl mx-auto">
          Paste a git diff below. ChangeGuard AI will identify security issues, breaking changes,
          and code quality problems — with suggested fixes.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Analysis Title <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="e.g. PR #142 — refactor auth middleware"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Diff textarea */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-sm font-medium text-gray-700">
              Git Diff <span className="text-red-500">*</span>
            </label>
            <button
              type="button"
              onClick={() => setDiff(SAMPLE_DIFF)}
              className="text-xs text-blue-600 hover:underline"
            >
              Load sample diff
            </button>
          </div>
          <textarea
            value={diff}
            onChange={e => setDiff(e.target.value)}
            placeholder={"Paste the output of `git diff` or `git diff HEAD~1` here…"}
            rows={16}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
          />
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !diff.trim()}
          className="w-full py-3 rounded-lg bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Analyzing…
            </span>
          ) : (
            'Analyze Diff'
          )}
        </button>
      </form>
    </div>
  )
}
