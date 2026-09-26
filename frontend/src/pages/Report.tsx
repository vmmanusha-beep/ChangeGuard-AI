import { useEffect, useState } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import { api, type AnalyzeResponse } from '../api/client'
import ReportView from '../components/ReportView'

export default function Report() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const [report, setReport] = useState<AnalyzeResponse | null>(
    (location.state as { report?: AnalyzeResponse })?.report ?? null,
  )
  const [loading, setLoading] = useState(!report)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (report || !id) return
    api.getReport(Number(id))
      .then(setReport)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load report'))
      .finally(() => setLoading(false))
  }, [id, report])

  if (loading)
    return (
      <div className="flex items-center justify-center py-24 text-gray-400">
        Loading report…
      </div>
    )

  if (error)
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    )

  if (!report) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/" className="hover:text-blue-600 hover:underline">
          ← New analysis
        </Link>
        <span>/</span>
        <Link to="/history" className="hover:text-blue-600 hover:underline">
          History
        </Link>
      </div>
      <ReportView report={report} />
    </div>
  )
}
