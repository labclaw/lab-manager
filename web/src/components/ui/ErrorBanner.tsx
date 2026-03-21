import { AlertTriangle, X } from 'lucide-react'

interface ErrorBannerProps {
  readonly error: string | null
  readonly onDismiss: () => void
}

export function ErrorBanner({ error, onDismiss }: ErrorBannerProps) {
  if (!error) return null

  return (
    <div className="fixed top-4 left-0 right-0 mx-auto max-w-md z-50 flex items-center gap-3 p-3 rounded-lg border border-red-500/30 bg-red-500/10">
      <AlertTriangle className="text-red-500 shrink-0" />
      <span className="text-sm text-red-500 flex-1">{error}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="text-red-500 hover:text-red-500/80 transition-colors"
      >
        <X className="size-5" />
      </button>
    </div>
  )
}
