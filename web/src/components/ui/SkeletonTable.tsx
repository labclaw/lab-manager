interface SkeletonTableProps {
  columns: number
  rows?: number
}

export function SkeletonTable({ columns, rows = 5 }: SkeletonTableProps) {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, i) => (
        <tr
          key={i}
          className="border-b border-[var(--border)] last:border-0"
        >
          {Array.from({ length: columns }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div
                className="h-4 rounded bg-[var(--muted)] animate-pulse"
                style={{ width: j === 0 ? '60%' : '40%', animationDelay: `${(i * columns + j) * 75}ms` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}
