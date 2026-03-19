import { useState } from 'react'

interface HeaderProps {
  readonly title: string
  readonly onSearch?: (query: string) => void
  readonly darkMode: boolean
  readonly onToggleDarkMode: () => void
}

export function Header({ title: _title, onSearch, darkMode, onToggleDarkMode }: HeaderProps) {
  const [searchQuery, setSearchQuery] = useState('')

  return (
    <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-primary/10 px-6 py-4 lg:px-10 bg-background-dark/80 backdrop-blur-md sticky top-0 z-50">
      <div className="flex items-center gap-8 flex-1">
        <label className="hidden md:flex flex-col max-w-xl w-full h-10">
          <div className="flex w-full flex-1 items-stretch rounded-lg h-full">
            <div className="text-slate-400 flex border-none bg-card-dark items-center justify-center pl-4 rounded-l-lg">
              <span className="material-symbols-outlined text-xl">search</span>
            </div>
            <input
              className="form-input flex w-full min-w-0 flex-1 border-none bg-card-dark text-slate-100 focus:ring-1 focus:ring-primary/50 h-full placeholder:text-slate-500 px-4 rounded-r-lg text-sm font-normal"
              placeholder="Search products, vendors, orders..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && onSearch) onSearch(searchQuery)
              }}
            />
          </div>
        </label>
      </div>
      <div className="flex items-center gap-4">
        <button className="flex items-center justify-center rounded-lg size-10 bg-card-dark text-slate-100 hover:bg-primary/20 transition-colors">
          <span className="material-symbols-outlined text-xl">notifications</span>
        </button>
        <button
          onClick={onToggleDarkMode}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          className="flex items-center justify-center rounded-lg size-10 bg-card-dark text-slate-100 hover:bg-primary/20 transition-colors"
        >
          <span className="material-symbols-outlined text-xl">
            {darkMode ? 'light_mode' : 'dark_mode'}
          </span>
        </button>
        <div className="flex items-center gap-3 pl-4 border-l border-primary/10">
          <span className="text-sm font-medium text-slate-400">Dr. Aris Thorne</span>
        </div>
      </div>
    </header>
  )
}
