import { useState, useCallback, useRef, useEffect } from 'react'
import { search } from '@/lib/api'

interface HeaderProps {
  readonly title: string
  readonly onSearch?: (query: string) => void
  readonly darkMode: boolean
  readonly onToggleDarkMode: () => void
}

export function Header({ title: _title, onSearch, darkMode, onToggleDarkMode }: HeaderProps) {
  void _title
  const [searchQuery, setSearchQuery] = useState('')
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (value.length >= 2) {
      debounceRef.current = setTimeout(() => {
        search.suggest(value).then(res => {
          setSuggestions(res.suggestions ?? [])
          setShowSuggestions(true)
        }).catch(() => {})
      }, 300)
    } else {
      setSuggestions([])
      setShowSuggestions(false)
    }
  }, [])

  const handleSearchSubmit = useCallback((query: string) => {
    if (!query.trim()) return
    setShowSuggestions(false)
    if (onSearch) onSearch(query)
    search.query(query).catch(() => {})
  }, [onSearch])

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [])

  return (
    <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-primary/10 px-6 py-4 lg:px-10 bg-[var(--background)]/80 backdrop-blur-md sticky top-0 z-50">
      <div className="flex items-center gap-8 flex-1">
        <label className="hidden md:flex flex-col max-w-xl w-full h-10 relative">
          <div className="flex w-full flex-1 items-stretch rounded-lg h-full">
            <div className="text-[var(--muted-foreground)] flex border-none bg-[var(--card)] items-center justify-center pl-4 rounded-l-lg">
              <span className="material-symbols-outlined text-xl">search</span>
            </div>
            <input
              className="form-input flex w-full min-w-0 flex-1 border-none bg-[var(--card)] text-[var(--foreground)] focus:ring-1 focus:ring-primary/50 h-full placeholder:text-[var(--muted-foreground)] px-4 rounded-r-lg text-sm font-normal"
              placeholder="Search products, vendors, orders..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSearchSubmit(searchQuery)
                if (e.key === 'Escape') setShowSuggestions(false)
              }}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              role="combobox"
              aria-expanded={showSuggestions}
              aria-haspopup="listbox"
            />
          </div>
          {showSuggestions && suggestions.length > 0 && (
            <ul role="listbox" className="absolute top-full left-0 right-0 mt-1 bg-card-dark border border-primary/20 rounded-lg shadow-xl z-50 overflow-hidden">
              {suggestions.map((s) => (
                <li
                  key={s}
                  role="option"
                  className="px-4 py-2 text-sm text-slate-200 hover:bg-primary/20 cursor-pointer"
                  onMouseDown={() => {
                    setSearchQuery(s)
                    handleSearchSubmit(s)
                  }}
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </label>
      </div>
      <div className="flex items-center gap-4">
        <button className="flex items-center justify-center rounded-lg size-10 bg-[var(--card)] text-[var(--foreground)] hover:bg-primary/20 transition-colors">
          <span className="material-symbols-outlined text-xl">notifications</span>
        </button>
        <button
          onClick={onToggleDarkMode}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          className="flex items-center justify-center rounded-lg size-10 bg-[var(--card)] text-[var(--foreground)] hover:bg-primary/20 transition-colors"
        >
          <span className="material-symbols-outlined text-xl">
            {darkMode ? 'light_mode' : 'dark_mode'}
          </span>
        </button>
        <div className="flex items-center gap-3 pl-4 border-l border-primary/10">
          <span className="text-sm font-medium text-[var(--muted-foreground)]">Admin</span>
        </div>
      </div>
    </header>
  )
}
