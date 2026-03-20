interface SkeletonTableProps {
  rows?: number
  columns?: number
}

export function SkeletonTable({ rows = 5, columns = 4 }: SkeletonTableProps) {
  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {Array.from({ length: columns }).map((_, i) => (
              <th
                key={i}
                className="text-left px-4 py-3 text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider"
              >
                <div
                  className="h-3 w-16 rounded bg-[var(--border)] animate-pulse"
                  style={{ animationDelay: `${i * 75}ms` }}
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, rowIdx) => (
            <tr key={rowIdx} className="border-b border-[var(--border)] last:border-0">
              {Array.from({ length: columns }).map((_, colIdx) => (
                <td key={colIdx} className="px-4 py-3">
                  <div
                    className="h-4 rounded bg-[var(--border)] animate-pulse"
                    style={{
                      width: `${50 + ((rowIdx * columns + colIdx) * 17) % 40}%`,
                      animationDelay: `${(rowIdx * columns + colIdx) * 75}ms`,
                    }}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
