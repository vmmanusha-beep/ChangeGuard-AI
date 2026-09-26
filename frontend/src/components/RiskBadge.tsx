type Severity = 'high' | 'medium' | 'low'

const CONFIG: Record<Severity, { label: string; classes: string }> = {
  high:   { label: 'HIGH',   classes: 'bg-red-100 text-red-700 border-red-300' },
  medium: { label: 'MEDIUM', classes: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  low:    { label: 'LOW',    classes: 'bg-green-100 text-green-700 border-green-300' },
}

export default function RiskBadge({ level, large = false }: { level: Severity; large?: boolean }) {
  const { label, classes } = CONFIG[level] ?? CONFIG.low
  return (
    <span
      className={`inline-flex items-center border font-semibold rounded-full ${classes} ${
        large ? 'px-4 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'
      }`}
    >
      {label}
    </span>
  )
}
