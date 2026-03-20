import { Link } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  FileText,
  ClipboardCheck,
  Package,
  ShoppingCart,
  Upload,
  Brain,
  User,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
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
  { path: '/', label: 'Dashboard', Icon: LayoutDashboard },
  { path: '/ask', label: 'Ask AI', Icon: Bot },
  { path: '/documents', label: 'Documents', Icon: FileText },
  { path: '/review', label: 'Review Queue', Icon: ClipboardCheck },
  { path: '/inventory', label: 'Inventory', Icon: Package },
  { path: '/orders', label: 'Orders', Icon: ShoppingCart },
  { path: '/upload', label: 'Upload', Icon: Upload },
]

export function Sidebar({
  current,
  collapsed,
  onToggle,
  alertCount = 0,
  reviewCount = 0,
}: SidebarProps) {
  const handleLogout = async () => {
    try {
      await auth.logout()
    } catch {
      // Swallow logout errors — still reload to clear session
    } finally {
      window.location.reload()
    }
  }

  return (
    <aside
      className={cn(
        'relative hidden md:flex flex-col bg-[var(--sidebar)] border-r border-primary/10 transition-all duration-300 shrink-0',
        collapsed ? 'w-16' : 'w-[240px]',
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 text-primary px-6 py-8">
        <div className="size-8 flex items-center justify-center bg-primary/10 rounded-lg shrink-0">
          <Brain className="size-5" />
        </div>
        {!collapsed && (
          <div>
            <h2 className="text-[var(--foreground)] text-xl font-bold leading-none tracking-tight">Lab Manager</h2>
            <p className="text-[10px] text-[var(--muted-foreground)] font-bold uppercase tracking-widest mt-1">Laboratory</p>
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
                  : 'text-[var(--muted-foreground)] hover:bg-primary/5 hover:text-[var(--foreground)]',
              )}
              title={collapsed ? item.label : undefined}
            >
              <item.Icon className="size-5 shrink-0" />
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
            <User className="size-4 text-primary" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <p className="text-sm font-bold text-[var(--foreground)] truncate">Admin</p>
            </div>
          )}
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-4 py-2 text-[var(--muted-foreground)] hover:text-red-400 transition-colors text-sm font-medium"
          title={collapsed ? 'Sign Out' : undefined}
        >
          <LogOut className="size-4 shrink-0" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="hidden lg:flex absolute -right-3 top-20 items-center justify-center w-6 h-6 rounded-full bg-[var(--card)] border border-primary/10 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
      >
        {collapsed ? <ChevronRight className="size-3" /> : <ChevronLeft className="size-3" />}
      </button>
    </aside>
  )
}
