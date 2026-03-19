interface ConfidenceBadgeProps {
  confidence: number | null | undefined
}

const LEVELS = [
  { min: 0.95, label: 'High', color: '#00D4AA' },
  { min: 0.80, label: 'Medium', color: '#6C5CE7' },
  { min: 0.50, label: 'Low', color: '#F39C12' },
  { min: 0, label: 'Needs Review', color: '#E74C3C' },
] as const

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  if (confidence == null) {
    return (
      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border border-border-dark text-slate-500">
        —
      </span>
    )
  }

  const level = LEVELS.find((l) => confidence >= l.min) ?? LEVELS[LEVELS.length - 1]
  const pct = Math.round(confidence * 100)

  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border"
      style={{
        color: level.color,
        borderColor: `${level.color}30`,
        backgroundColor: `${level.color}15`,
      }}
    >
      {level.label} ({pct}%)
    </span>
  )
}
