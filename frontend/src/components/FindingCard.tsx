import type { Finding } from '../api/client'
import RiskBadge from './RiskBadge'

const categoryIcon: Record<string, string> = {
  'Breaking Change': '⚠️',
  'Security': '🔒',
  'Reliability': '🔁',
  'Performance': '⚡',
  'Code Quality': '🔍',
  'Data Loss Risk': '💾',
  'Review Risk': '👀',
  'Dependency': '📦',
}

export default function FindingCard({ finding }: { finding: Finding }) {
  const icon = categoryIcon[finding.category] ?? '📋'

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base">{icon}</span>
          <span className="font-medium text-gray-900 text-sm truncate">{finding.category}</span>
        </div>
        <RiskBadge level={finding.severity} />
      </div>

      <p className="text-sm text-gray-700">{finding.description}</p>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
        <span>
          <span className="font-medium text-gray-600">File:</span>{' '}
          <code className="font-mono bg-gray-100 px-1 rounded">{finding.file}</code>
        </span>
        <span>
          <span className="font-medium text-gray-600">Location:</span> {finding.line_hint}
        </span>
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded p-3">
        <p className="text-xs font-semibold text-blue-700 mb-0.5">Suggested Fix</p>
        <p className="text-xs text-blue-900">{finding.suggestion}</p>
      </div>
    </div>
  )
}
