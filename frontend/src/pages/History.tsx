import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ReportListItem } from '../api/client'
import RiskBadge from '../components/RiskBadge'

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function History() {
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listReports()
      .then(setReports)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load history'))
      .finally(() => setLoading(false))
  }, [])

  if (loading)
    return <div className="flex items-center justify-center py-24 text-gray-400">Loading…</div>

  if (error)
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Analysis History</h1>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          + New analysis
        </Link>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          No analyses yet.{' '}
          <Link to="/" className="text-blue-500 hover:underline">
            Run your first one.
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map(r => (
            <Link
              key={r.id}
              to={`/report/${r.id}`}
              className="flex items-center gap-4 bg-white border border-gray-200 rounded-lg px-5 py-4 hover:border-blue-300 hover:shadow-sm transition-all"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-medium text-gray-900 truncate">{r.title}</span>
                  <RiskBadge level={r.risk_level} />
                </div>
                <p className="text-xs text-gray-500 truncate">{r.summary}</p>
              </div>
              <div className="flex-shrink-0 text-right text-xs text-gray-400 space-y-0.5">
                <div>{r.findings_count} finding{r.findings_count !== 1 ? 's' : ''}</div>
                <div>{timeAgo(r.created_at)}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
