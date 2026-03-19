import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { auth } from '@/lib/api'

interface SidebarProps {
  readonly current: string
  readonly collapsed: boolean
  readonly onToggle: () => void
  readonly alertCount?: number
  readonly reviewCount?: number
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: 'dashboard' },
  { path: '/documents', label: 'Documents', icon: 'description' },
  { path: '/review', label: 'Review Queue', icon: 'fact_check' },
  { path: '/inventory', label: 'Inventory', icon: 'inventory_2' },
  { path: '/orders', label: 'Orders', icon: 'shopping_cart' },
  { path: '/upload', label: 'Upload', icon: 'upload_file' },
]

export function Sidebar({
  current,
  collapsed,
  onToggle,
  alertCount = 0,
  reviewCount = 0,
}: SidebarProps) {
  const handleLogout = async () => {
    await auth.logout()
    window.location.reload()
  }

  return (
    <aside
      className={cn(
        'relative flex flex-col h-screen bg-[var(--sidebar)] border-r border-[var(--sidebar-border)]',
        'transition-all duration-300',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="w-8 h-8 bg-[var(--primary)] rounded-lg flex items-center justify-center text-white shrink-0">
          <span className="material-symbols-outlined text-xl">biotech</span>
        </div>
        {!collapsed && (
          <div>
            <h1 className="text-[var(--foreground)] text-lg font-bold leading-none tracking-tight">
              Lab Manager
            </h1>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = current === item.path
          const badge =
            item.path === '/alerts' && alertCount > 0
              ? alertCount
              : item.path === '/review' && reviewCount > 0
                ? reviewCount
                : 0
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-[var(--primary)]/10 text-[var(--primary)] border-l-[3px] border-[var(--primary)]'
                  : 'text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--sidebar-foreground)]',
              )}
              title={collapsed ? item.label : undefined}
            >
              <span className={cn(
                'material-symbols-outlined text-[22px]',
                isActive && 'fill-1',
              )} style={isActive ? { fontVariationSettings: "'FILL' 1" } : undefined}>
                {item.icon}
              </span>
              {!collapsed && <span>{item.label}</span>}
              {!collapsed && badge > 0 && (
                <span className="ml-auto bg-[var(--destructive)]/15 text-[var(--destructive)] text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {badge}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[var(--sidebar-border)] p-3 space-y-1">
        <Link
          to="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--sidebar-foreground)] transition-colors"
          title={collapsed ? 'Settings' : undefined}
        >
          <span className="material-symbols-outlined text-[22px]">settings</span>
          {!collapsed && <span>Settings</span>}
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--destructive)] hover:bg-[var(--destructive)]/10 transition-colors"
          title={collapsed ? 'Sign Out' : undefined}
        >
          <span className="material-symbols-outlined text-[22px]">logout</span>
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="hidden lg:flex absolute -right-3 top-20 items-center justify-center w-6 h-6 rounded-full bg-[var(--card)] border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
      >
        <span className="material-symbols-outlined text-sm">
          {collapsed ? 'chevron_right' : 'chevron_left'}
        </span>
      </button>
    </aside>
  )
}
