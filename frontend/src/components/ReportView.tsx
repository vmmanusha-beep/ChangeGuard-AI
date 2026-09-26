import type { AnalyzeResponse } from '../api/client'
import RiskBadge from './RiskBadge'
import FindingCard from './FindingCard'

const RISK_BORDER: Record<string, string> = {
  high:   'border-red-400',
  medium: 'border-yellow-400',
  low:    'border-green-400',
}

const RISK_BG: Record<string, string> = {
  high:   'bg-red-50',
  medium: 'bg-yellow-50',
  low:    'bg-green-50',
}

/** Ensure affected_files is always a proper string[], never a bare string. */
function normaliseFiles(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    // Filter out empty strings and flatten any accidentally joined entries
    return raw
      .flatMap(item =>
        typeof item === 'string' && item.includes('\n')
          ? item.split('\n')
          : [item]
      )
      .map(s => String(s).trim())
      .filter(s => s.length > 0)
  }
  if (typeof raw === 'string' && raw.trim().length > 0) {
    // Model returned a comma-separated or newline-separated string — split it
    const sep = raw.includes('\n') ? '\n' : ','
    return raw.split(sep).map(s => s.trim()).filter(s => s.length > 0)
  }
  return []
}

export default function ReportView({ report }: { report: AnalyzeResponse }) {
  const affectedFiles = normaliseFiles(report.affected_files)
  // DIAGNOSTIC — remove after confirming fix is live in browser
  if (typeof window !== 'undefined') {
    console.log('[ChangeGuard diag] affected_files raw:', JSON.stringify(report.affected_files))
    console.log('[ChangeGuard diag] affectedFiles normalised:', JSON.stringify(affectedFiles))
    console.log('[ChangeGuard diag] array?', Array.isArray(report.affected_files), 'len:', affectedFiles.length)
  }
  const highCount   = report.findings.filter(f => f.severity === 'high').length
  const medCount    = report.findings.filter(f => f.severity === 'medium').length
  const lowCount    = report.findings.filter(f => f.severity === 'low').length

  return (
    <div className="space-y-6">
      {/* Summary card */}
      <div className={`rounded-xl border-2 ${RISK_BORDER[report.risk_level]} ${RISK_BG[report.risk_level]} p-6`}>
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <h2 className="text-xl font-bold text-gray-900">{report.title}</h2>
              <RiskBadge level={report.risk_level} large />
            </div>
            <p className="text-sm text-gray-700">{report.summary}</p>
          </div>

          {/* Risk score donut */}
          <div className="flex-shrink-0 text-center">
            <div className={`text-4xl font-extrabold ${
              report.risk_level === 'high' ? 'text-red-600' :
              report.risk_level === 'medium' ? 'text-yellow-600' : 'text-green-600'
            }`}>
              {report.risk_score}
            </div>
            <div className="text-xs text-gray-500 font-medium">Risk Score</div>
          </div>
        </div>

        {/* Stats row */}
        <div className="mt-4 flex flex-wrap gap-3">
          <Stat label="High" value={highCount} color="text-red-600" />
          <Stat label="Medium" value={medCount} color="text-yellow-600" />
          <Stat label="Low" value={lowCount} color="text-green-600" />
          <Stat label="Files affected" value={affectedFiles.length} color="text-blue-600" />
        </div>
      </div>

      {/* Affected files */}
<section>
  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
    Affected Files
  </h3>

  {affectedFiles.length > 0 ? (
    <div className="grid gap-2">
      {affectedFiles.map((file, index) => (
        <div
          key={`${file}-${index}`}
          className="w-fit max-w-full rounded-md border border-gray-200 bg-gray-100 px-3 py-2"
        >
          <code className="text-xs font-mono text-gray-700 break-all">
            {file}
          </code>
        </div>
      ))}
    </div>
  ) : (
    <p className="text-xs text-gray-400 italic">
      No affected files detected.
    </p>
  )}
</section>

      {/* Findings */}
      <section>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Findings ({report.findings.length})
        </h3>
        {report.findings.length === 0 ? (
          <div className="text-center py-10 text-gray-400">No findings — diff looks clean!</div>
        ) : (
          <div className="space-y-3">
            {/* Sort: high → medium → low */}
            {[...report.findings]
              .sort((a, b) => {
                const order = { high: 0, medium: 1, low: 2 }
                return order[a.severity] - order[b.severity]
              })
              .map((f, i) => (
                <FindingCard key={i} finding={f} />
              ))}
          </div>
        )}
      </section>
      {/* Safer alternatives */}
      {report.safer_alternatives?.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Safer Alternatives
          </h3>
          <div className="space-y-2">
            {report.safer_alternatives.map((alternative, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700"
              >
                {alternative}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recommended tests */}
      {report.recommended_tests?.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Recommended Tests
          </h3>
          <div className="space-y-2">
            {report.recommended_tests.map((test, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700"
              >
                {test}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-white rounded-lg px-4 py-2 border border-gray-200 text-center min-w-[80px]">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  )
}
