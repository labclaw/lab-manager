import {
  LayoutDashboard,
  Package,
  FileText,
  ClipboardCheck,
  Bell,
  Settings,
  FlaskConical,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Upload,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { auth } from '@/lib/api'

interface SidebarProps {
  current: string
  collapsed: boolean
  onToggle: () => void
  alertCount?: number
  reviewCount?: number
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/inventory', label: 'Inventory', icon: Package },
  { path: '/orders', label: 'Orders', icon: FlaskConical },
  { path: '/documents', label: 'Documents', icon: FileText },
  { path: '/upload', label: 'Upload', icon: Upload },
  { path: '/review', label: 'Review', icon: ClipboardCheck },
  { path: '/alerts', label: 'Alerts', icon: Bell },
]

export function Sidebar({
  current,
  collapsed,
  onToggle,
  alertCount = 0,
  reviewCount = 0,
}: SidebarProps) {
  const navigate = useNavigate()

  const handleLogout = async () => {
    await auth.logout()
    window.location.reload()
  }

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-[var(--sidebar)] border-r border-[var(--sidebar-border)]',
        'transition-all duration-300',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 h-14 border-b border-[var(--sidebar-border)]">
        <FlaskConical className="w-6 h-6 text-[var(--primary)] shrink-0" />
        {!collapsed && (
          <span className="font-display font-bold text-lg text-[var(--foreground)]">
            LabClaw
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon
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
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-[var(--primary)]/15 text-[var(--primary)]'
                  : 'text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--sidebar-foreground)]',
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
              {!collapsed && badge > 0 && (
                <span className="ml-auto badge badge-destructive text-[10px]">
                  {badge}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[var(--sidebar-border)] p-2 space-y-1">
        <Link
          to="/settings"
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--sidebar-foreground)] transition-colors',
          )}
          title={collapsed ? 'Settings' : undefined}
        >
          <Settings className="w-5 h-5 shrink-0" />
          {!collapsed && <span>Settings</span>}
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--destructive)]/10 hover:text-[var(--destructive)] transition-colors"
          title={collapsed ? 'Logout' : undefined}
        >
          <LogOut className="w-5 h-5 shrink-0" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="hidden lg:flex absolute -right-3 top-20 items-center justify-center w-6 h-6 rounded-full bg-[var(--card)] border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
      >
        {collapsed ? (
          <ChevronRight className="w-3 h-3" />
        ) : (
          <ChevronLeft className="w-3 h-3" />
        )}
      </button>
    </aside>
  )
}
