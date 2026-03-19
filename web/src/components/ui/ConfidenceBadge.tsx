interface ConfidenceBadgeProps {
  confidence: number | null | undefined
}

function getLevel(confidence: number | null | undefined) {
  if (confidence == null) return { label: 'N/A', color: '#6B7280' }
  const pct = confidence * 100
  if (pct >= 95) return { label: 'High', color: '#00D4AA' }
  if (pct >= 80) return { label: 'Medium', color: '#6C5CE7' }
  if (pct >= 50) return { label: 'Low', color: '#F39C12' }
  return { label: 'Needs Review', color: '#E74C3C' }
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const { label, color } = getLevel(confidence)
  const pct = confidence != null ? `${(confidence * 100).toFixed(0)}%` : '—'

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold"
      style={{
        backgroundColor: `${color}18`,
        color,
        border: `1px solid ${color}40`,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {pct} {label}
    </span>
  )
}
