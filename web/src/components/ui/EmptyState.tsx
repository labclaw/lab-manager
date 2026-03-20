import type { LucideIcon } from 'lucide-react'
import { HelpCircle } from 'lucide-react'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
}

export function EmptyState({
  icon: Icon = HelpCircle,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-4 space-y-4">
      <div className="w-12 h-12 rounded-2xl bg-slate-800 flex items-center justify-center">
        <Icon className="size-6 text-slate-500" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-slate-100">
          {title}
        </h3>
        {description && (
          <p className="text-sm text-slate-500 max-w-xs mx-auto">
            {description}
          </p>
        )}
      </div>
      {action && <div className="pt-2">{action}</div>}
    </div>
  )
}
