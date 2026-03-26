import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Bell, Menu } from 'lucide-react'
import { search, alerts as alertsApi, type Alert } from '@/lib/api'

interface HeaderProps {
  readonly title: string
  readonly onSearch?: (query: string) => void
  readonly showSearch?: boolean
  readonly onMobileMenuToggle?: () => void
  readonly userName?: string
  readonly alertCount?: number
}

const SEARCH_TYPE_ROUTES: Record<string, string> = {
  inventory: '/inventory',
  document: '/documents',
  product: '/products',
  vendor: '/vendors',
  order: '/orders',
}

export function Header({ title, onSearch, showSearch = true, onMobileMenuToggle, userName = 'User', alertCount = 0 }: HeaderProps) {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [suggestions, setSuggestions] = useState<Array<{ type: string; text: string; id: number }>>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [bellOpen, setBellOpen] = useState(false)
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([])
  const [loadingAlerts, setLoadingAlerts] = useState(false)
  const bellRef = useRef<HTMLDivElement>(null)
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

  const handleSelectSuggestion = useCallback((suggestion: { type: string; text: string; id: number }) => {
    setSearchQuery(suggestion.text)
    setShowSuggestions(false)
    const route = SEARCH_TYPE_ROUTES[suggestion.type]
    if (route) {
      navigate(`${route}?search=${encodeURIComponent(suggestion.text)}`)
    }
  }, [navigate])

  const handleSearchSubmit = useCallback((query: string) => {
    if (!query.trim()) return
    setShowSuggestions(false)
    if (onSearch) onSearch(query)
  }, [onSearch])

  const handleBellToggle = useCallback(() => {
    setBellOpen(prev => {
      if (!prev) {
        setLoadingAlerts(true)
        alertsApi.list({ acknowledged: false }).then(res => {
          setRecentAlerts((res.items ?? []).slice(0, 5))
        }).catch(() => {
          setRecentAlerts([])
        }).finally(() => setLoadingAlerts(false))
      }
      return !prev
    })
  }, [])

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [])

  // Close bell dropdown on outside click
  useEffect(() => {
    if (!bellOpen) return
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setBellOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [bellOpen])

  return (
    <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-primary/10 px-3 py-3 md:px-6 md:py-4 lg:px-10 bg-[var(--background)]/80 backdrop-blur-md sticky top-0 z-50">
      <div className="flex items-center gap-4 md:gap-8 flex-1 min-w-0">
        {onMobileMenuToggle && (
          <button
            type="button"
            onClick={onMobileMenuToggle}
            aria-label="Open navigation menu"
            className="flex md:hidden items-center justify-center rounded-lg size-10 bg-[var(--card)] text-[var(--foreground)] hover:bg-primary/20 transition-colors"
          >
            <Menu className="size-5" />
          </button>
        )}
        <div className="flex flex-col min-w-0">
          <span className="hidden xl:block text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Current View</span>
          <h1 className="text-base md:text-lg font-bold text-[var(--foreground)] truncate">{title}</h1>
        </div>
        <label className={`${showSearch ? 'hidden md:flex' : 'hidden'} flex-col max-w-xl w-full h-10 relative`}>
          <div className="flex w-full flex-1 items-stretch rounded-lg h-full">
            <div className="text-[var(--muted-foreground)] flex border-none bg-[var(--card)] items-center justify-center pl-4 rounded-l-lg">
              <Search className="size-5 text-[var(--muted-foreground)]" />
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
            <ul role="listbox" className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-xl z-50 overflow-hidden">
              {suggestions.map((s) => (
                <li
                  key={`${s.type}-${s.id}`}
                  role="option"
                  className="px-4 py-2 text-sm text-[var(--foreground)] hover:bg-primary/10 cursor-pointer"
                  onMouseDown={() => handleSelectSuggestion(s)}
                >
                  <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-primary/70 bg-primary/10 px-1.5 py-0.5 rounded mr-2">{s.type}</span>
                  {s.text}
                </li>
              ))}
            </ul>
          )}
        </label>
      </div>
      <div className="flex items-center gap-2 md:gap-4">
        <div ref={bellRef} className="relative">
          <button
            onClick={handleBellToggle}
            aria-label="Notifications"
            className="flex items-center justify-center rounded-lg size-10 bg-[var(--card)] text-[var(--foreground)] hover:bg-primary/20 transition-colors relative"
          >
            <Bell className="size-5" />
            {alertCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold min-w-[18px] h-[18px] flex items-center justify-center rounded-full px-1">
                {alertCount > 99 ? '99+' : alertCount}
              </span>
            )}
          </button>
          {bellOpen && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-[var(--card)] border border-primary/10 rounded-lg shadow-xl z-50 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-primary/10">
                <span className="text-sm font-semibold text-[var(--foreground)]">Notifications</span>
                <button
                  onClick={() => { setBellOpen(false); navigate('/alerts') }}
                  className="text-xs text-primary hover:underline"
                >
                  View all
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {loadingAlerts && (
                  <p className="px-4 py-6 text-sm text-center text-[var(--muted-foreground)]">Loading...</p>
                )}
                {!loadingAlerts && recentAlerts.length === 0 && (
                  <p className="px-4 py-6 text-sm text-center text-[var(--muted-foreground)]">No new notifications</p>
                )}
                {!loadingAlerts && recentAlerts.map(a => (
                  <div
                    key={a.id}
                    className="px-4 py-3 hover:bg-primary/5 cursor-pointer border-b border-primary/5 last:border-b-0"
                    onClick={() => { setBellOpen(false); navigate('/alerts') }}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${a.severity === 'critical' ? 'bg-red-500' : a.severity === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'}`} />
                      <span className="text-xs font-medium text-[var(--muted-foreground)] uppercase">{a.type}</span>
                    </div>
                    <p className="text-sm text-[var(--foreground)] mt-1 line-clamp-2">{a.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="hidden md:flex items-center gap-3 pl-4 border-l border-primary/10">
          <span className="text-sm font-medium text-[var(--muted-foreground)]">{userName}</span>
        </div>
      </div>
    </header>
  )
}
