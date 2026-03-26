import { Link } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  BarChart3,
  FileText,
  ClipboardCheck,
  Package,
  ScanBarcode,
  ShoppingCart,
  Upload,
  Brain,
  Sparkles,
  Settings,
  User,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Building2,
  FlaskConical,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { auth } from '@/lib/api'

interface SidebarProps {
  readonly current: string
  readonly collapsed: boolean
  readonly onToggle: () => void
  readonly alertCount?: number
  readonly reviewCount?: number
  readonly mobileOpen?: boolean
  readonly onMobileClose?: () => void
}

const navItems = [
  { path: '/', label: 'Dashboard', Icon: LayoutDashboard },
  { path: '/analytics', label: 'Analytics', Icon: BarChart3 },
  { path: '/ask', label: 'Ask AI', Icon: Bot },
  { path: '/documents', label: 'Documents', Icon: FileText },
  { path: '/review', label: 'Review Queue', Icon: ClipboardCheck },
  { path: '/vendors', label: 'Vendors', Icon: Building2 },
  { path: '/products', label: 'Products', Icon: FlaskConical },
  { path: '/scan', label: 'Scan', Icon: ScanBarcode },
  { path: '/inventory', label: 'Inventory', Icon: Package },
  { path: '/orders', label: 'Orders', Icon: ShoppingCart },
  { path: '/upload', label: 'Upload', Icon: Upload },
  { path: '/cloud-brain', label: 'Cloud Brain', Icon: Sparkles },
]

export function Sidebar({
  current,
  collapsed,
  onToggle,
  alertCount = 0,
  reviewCount = 0,
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  // On mobile overlay, always show expanded regardless of collapsed state
  const showLabels = mobileOpen || !collapsed

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
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onMobileClose}
        />
      )}
    <aside
      className={cn(
        'flex flex-col bg-[var(--sidebar)] border-r border-primary/10 transition-all duration-300 shrink-0',
        mobileOpen ? 'w-[240px]' : (collapsed ? 'w-16' : 'w-[240px]'),
        mobileOpen
          ? 'fixed inset-y-0 left-0 z-50 md:relative md:z-auto'
          : 'hidden md:flex relative',
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 text-primary px-6 py-8">
        <div className="size-8 flex items-center justify-center bg-primary/10 rounded-lg shrink-0">
          <Brain className="size-5" />
        </div>
        {showLabels && (
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
              onClick={onMobileClose}
              className={cn(
                'flex items-center gap-3 px-4 py-3 md:py-2.5 rounded-lg transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary font-semibold'
                  : 'text-[var(--muted-foreground)] hover:bg-primary/5 hover:text-[var(--foreground)]',
              )}
              title={collapsed ? item.label : undefined}
            >
              <item.Icon className="size-5 shrink-0" />
              {showLabels && <span className="text-sm">{item.label}</span>}
              {showLabels && badge > 0 && (
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
          {showLabels && (
            <div className="overflow-hidden">
              <p className="text-sm font-bold text-[var(--foreground)] truncate">Admin</p>
            </div>
          )}
        </div>
        <Link
          to="/settings"
          onClick={onMobileClose}
          className={cn(
            'flex items-center gap-3 w-full px-4 py-3 md:py-2 rounded-lg transition-colors text-sm font-medium',
            current === '/settings'
              ? 'bg-primary/10 text-primary font-semibold'
              : 'text-[var(--muted-foreground)] hover:bg-primary/5 hover:text-[var(--foreground)]',
          )}
          title={collapsed ? 'Settings' : undefined}
        >
          <Settings className="size-4 shrink-0" />
          {showLabels && <span>Settings</span>}
        </Link>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-4 py-3 md:py-2 text-[var(--muted-foreground)] hover:text-red-400 transition-colors text-sm font-medium"
          title={collapsed ? 'Sign Out' : undefined}
        >
          <LogOut className="size-4 shrink-0" />
          {showLabels && <span>Sign Out</span>}
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
    </>
  )
}
