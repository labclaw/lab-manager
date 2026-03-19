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
        'hidden md:flex flex-col bg-sidebar-dark border-r border-primary/10 transition-all duration-300',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 text-primary px-6 py-8">
        <div className="size-8 flex items-center justify-center bg-primary/10 rounded-lg shrink-0">
          <span className="material-symbols-outlined text-primary text-2xl">psychology</span>
        </div>
        {!collapsed && (
          <div>
            <h2 className="text-slate-100 text-xl font-bold leading-none tracking-tight">Lab Manager</h2>
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">MGH Neuroscience</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-4 space-y-1">
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
                'flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary font-semibold'
                  : 'text-slate-400 hover:bg-primary/5 hover:text-slate-100',
              )}
              title={collapsed ? item.label : undefined}
            >
              <span className="material-symbols-outlined text-xl">
                {item.icon}
              </span>
              {!collapsed && <span className="text-sm">{item.label}</span>}
              {!collapsed && badge > 0 && (
                <span className="ml-auto bg-red-500/15 text-red-500 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {badge}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 mt-auto border-t border-primary/10">
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="h-9 w-9 rounded-full border border-primary/30 overflow-hidden shrink-0 bg-primary/10 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-lg">person</span>
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <p className="text-sm font-bold text-slate-100 truncate">Dr. Aris Thorne</p>
            </div>
          )}
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-4 py-2 text-slate-400 hover:text-red-400 transition-colors text-sm font-medium"
          title={collapsed ? 'Sign Out' : undefined}
        >
          <span className="material-symbols-outlined text-lg">logout</span>
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="hidden lg:flex absolute -right-3 top-20 items-center justify-center w-6 h-6 rounded-full bg-card-dark border border-primary/10 text-slate-400 hover:text-slate-100 transition-colors"
      >
        <span className="material-symbols-outlined text-sm">
          {collapsed ? 'chevron_right' : 'chevron_left'}
        </span>
      </button>
    </aside>
  )
}
