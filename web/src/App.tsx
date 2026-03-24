import { useEffect, useState, useCallback } from 'react'
import { Routes, Route, useLocation, Navigate } from 'react-router-dom'
import { auth, setup, alerts, documents } from '@/lib/api'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { ErrorBanner } from '@/components/ui/ErrorBanner'
import { LoginPage } from '@/pages/LoginPage'
import { SetupPage } from '@/pages/SetupPage'
import { AskPage } from '@/pages/AskPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { InventoryPage } from '@/pages/InventoryPage'
import { OrdersPage } from '@/pages/OrdersPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { ReviewPage } from '@/pages/ReviewPage'
import { UploadPage } from '@/pages/UploadPage'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/ask': 'Ask AI',
  '/inventory': 'Inventory',
  '/orders': 'Orders',
  '/documents': 'Documents',
  '/upload': 'Upload Documents',
  '/review': 'Review Queue',
  '/alerts': 'Alerts',
  '/settings': 'Settings',
}

function AlertsPage() {
  return (
    <div className="text-center py-16 space-y-3">
      <h3 className="text-lg font-display font-semibold text-[var(--foreground)]">
        Alerts
      </h3>
      <p className="text-sm text-[var(--muted-foreground)]">
        Alerts page
      </p>
    </div>
  )
}

function SettingsPage() {
  return (
    <div className="text-center py-16 space-y-3">
      <h3 className="text-lg font-display font-semibold text-[var(--foreground)]">
        Settings
      </h3>
      <p className="text-sm text-[var(--muted-foreground)]">
        Settings page coming soon
      </p>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState<{ id: number; name: string } | null>(null)
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  const [reviewCount, setReviewCount] = useState(0)
  const [darkMode, setDarkMode] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const location = useLocation()

  const checkAuth = useCallback(async () => {
    try {
      const setupRes = await setup.status()
      if (setupRes.needs_setup) {
        setNeedsSetup(true)
        setLoading(false)
        return
      }
      setNeedsSetup(false)
      const res = await auth.me()
      setUser(res.user)
    } catch {
      setUser(null)
      setNeedsSetup(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const stored = localStorage.getItem('darkMode')
    const isDark = stored === 'true'
    setDarkMode(isDark)
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [])

  const toggleDarkMode = () => {
    setDarkMode(prev => {
      const next = !prev
      localStorage.setItem('darkMode', String(next))
      if (next) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
      return next
    })
  }

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // Load badge counts
  useEffect(() => {
    if (!user) return
    alerts.list().then((res) => {
      const unack = (res.items ?? []).filter((a) => !a.acknowledged)
      setAlertCount(unack.length)
    }).catch(() => {})

    documents.reviewQueue().then((res) => {
      setReviewCount(res.items?.length ?? 0)
    }).catch(() => {})
  }, [user])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--background)]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          <p className="text-sm text-[var(--muted-foreground)]">Loading...</p>
        </div>
      </div>
    )
  }

  if (needsSetup) {
    return <SetupPage onComplete={() => { setNeedsSetup(false) }} />
  }

  if (!user) {
    return <LoginPage />
  }

  return (
    <>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <div className="flex h-screen bg-[var(--background)] overflow-hidden">
        <Sidebar
          current={location.pathname}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          alertCount={alertCount}
          reviewCount={reviewCount}
          mobileOpen={mobileMenuOpen}
          onMobileClose={() => setMobileMenuOpen(false)}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <Header
            title={PAGE_TITLES[location.pathname] ?? 'Lab Manager'}
            showSearch={location.pathname !== '/ask'}
            darkMode={darkMode}
            onToggleDarkMode={toggleDarkMode}
            onMobileMenuToggle={() => setMobileMenuOpen(prev => !prev)}
          />
          <main className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/">
                <Route index element={<DashboardPage onError={setError} />} />
                <Route path="ask" element={<AskPage onError={setError} />} />
                <Route path="inventory" element={<InventoryPage onError={setError} />} />
                <Route path="orders" element={<OrdersPage onError={setError} />} />
                <Route path="documents" element={<DocumentsPage onError={setError} />} />
                <Route path="upload" element={<UploadPage />} />
                <Route path="review" element={<ReviewPage onError={setError} />} />
                <Route path="alerts" element={<AlertsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </main>
        </div>
      </div>
    </>
  )
}
