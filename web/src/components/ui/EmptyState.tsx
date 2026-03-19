interface EmptyStateProps {
  icon?: string
  title: string
  description?: string
  action?: React.ReactNode
}

export function EmptyState({
  icon = 'help',
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-4 space-y-4">
      <div className="w-12 h-12 rounded-2xl bg-[var(--muted)] flex items-center justify-center">
        <span className="material-symbols-outlined text-2xl text-[var(--muted-foreground)]">
          {icon}
        </span>
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-[var(--foreground)]">
          {title}
        </h3>
        {description && (
          <p className="text-sm text-[var(--muted-foreground)] max-w-xs mx-auto">
            {description}
          </p>
        )}
      </div>
      {action && <div className="pt-2">{action}</div>}
    </div>
  )
}
