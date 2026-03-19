import { Search } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

interface HeaderProps {
  title: string
  onSearch?: (query: string) => void
}

export function Header({ title, onSearch }: HeaderProps) {
  const [searchOpen, setSearchOpen] = useState(false)

  return (
    <header className="h-14 border-b border-[var(--border)] bg-[var(--card)] flex items-center justify-between px-6">
      <h1 className="text-lg font-display font-bold text-[var(--foreground)]">
        {title}
      </h1>

      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative">
          {searchOpen ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search inventory, orders, documents..."
                className={cn(
                  'w-64 bg-[var(--popover)] border border-[var(--border)] rounded-lg px-3 py-1.5 text-sm text-[var(--foreground)]',
                  'placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]',
                )}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && onSearch) onSearch(e.currentTarget.value)
                  if (e.key === 'Escape') setSearchOpen(false)
                }}
                autoFocus
              />
            </div>
          ) : null}
          <button
            onClick={() => setSearchOpen(!searchOpen)}
            className="p-2 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
          >
            <Search className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
