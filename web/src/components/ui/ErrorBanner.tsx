interface ErrorBannerProps {
  readonly error: string | null
  readonly onDismiss: () => void
}

export function ErrorBanner({ error, onDismiss }: ErrorBannerProps) {
  if (!error) return null

  return (
    <div className="fixed top-4 left-4 right-4 max-w-md z-50 flex items-center gap-3 p-3 rounded-lg border border-[var(--destructive)]/30 bg-[var(--destructive)]/10">
      <span className="material-symbols-outlined text-[var(--destructive)] shrink-0">warning</span>
      <span className="text-sm text-[var(--destructive)] flex-1">{error}</span>
      <button
        onClick={onDismiss}
        className="text-[var(--destructive)] hover:text-[var(--destructive)]/80 transition-colors"
      >
        <span className="material-symbols-outlined text-lg">close</span>
      </button>
    </div>
  )
}
