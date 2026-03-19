import { useState } from 'react'

interface HeaderProps {
  readonly title: string
  readonly onSearch?: (query: string) => void
  readonly darkMode: boolean
  readonly onToggleDarkMode: () => void
}

export function Header({ title, onSearch, darkMode, onToggleDarkMode }: HeaderProps) {
  const [searchOpen, setSearchOpen] = useState(false)

  return (
    <header className="h-16 border-b border-[var(--border)] bg-[var(--card)]/80 backdrop-blur-md flex items-center justify-between px-6 sticky top-0 z-10">
      <h2 className="text-xl font-bold text-[var(--foreground)]">
        {title}
      </h2>

      <div className="flex items-center gap-4 flex-1 max-w-xl px-8">
        {searchOpen && (
          <div className="relative w-full">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
              search
            </span>
            <input
              type="text"
              placeholder="Search products, vendors, orders..."
              className="w-full bg-[var(--muted)] border-none rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-[var(--primary)]/50 focus:outline-none transition-all"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && onSearch) onSearch(e.currentTarget.value)
                if (e.key === 'Escape') setSearchOpen(false)
              }}
              autoFocus
            />
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setSearchOpen(!searchOpen)}
          aria-label={searchOpen ? 'Close search' : 'Open search'}
          className="flex items-center justify-center rounded-lg w-10 h-10 bg-[var(--muted)] text-[var(--foreground)] hover:bg-[var(--primary)]/20 transition-colors"
        >
          <span className="material-symbols-outlined text-xl">search</span>
        </button>

        <button
          className="flex items-center justify-center rounded-lg w-10 h-10 bg-[var(--muted)] text-[var(--foreground)] hover:bg-[var(--primary)]/20 transition-colors relative"
          aria-label="Notifications"
        >
          <span className="material-symbols-outlined text-xl">notifications</span>
        </button>

        <button
          onClick={onToggleDarkMode}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          className="flex items-center justify-center rounded-lg w-10 h-10 bg-[var(--muted)] text-[var(--foreground)] hover:bg-[var(--primary)]/20 transition-colors"
        >
          <span className="material-symbols-outlined text-xl">
            {darkMode ? 'light_mode' : 'dark_mode'}
          </span>
        </button>
      </div>
    </header>
  )
}
