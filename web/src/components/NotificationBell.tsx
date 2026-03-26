import { useState, useEffect, useCallback, useRef } from 'react'
import { Bell } from 'lucide-react'
import { notifications as api } from '@/lib/api'

interface NotificationItem {
  id: number
  type: string
  title: string
  message: string
  link?: string | null
  is_read: boolean
  created_at?: string | null
}

export function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const fetchCount = useCallback(() => {
    api.unreadCount().then(r => setUnreadCount(r.unread_count)).catch(() => {})
  }, [])

  const fetchItems = useCallback(() => {
    api.list(true).then(r => setItems(r.items ?? [])).catch(() => {})
  }, [])

  // Poll unread count every 30s
  useEffect(() => {
    fetchCount()
    const interval = setInterval(fetchCount, 30_000)
    return () => clearInterval(interval)
  }, [fetchCount])

  // Fetch items when dropdown opens
  useEffect(() => {
    if (open) fetchItems()
  }, [open, fetchItems])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleMarkRead = useCallback((id: number, link?: string | null) => {
    api.markRead(id).then(() => {
      setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
      if (link) window.location.href = link
    }).catch(() => {})
  }, [])

  const handleMarkAllRead = useCallback(() => {
    api.markAllRead().then(() => {
      setItems(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadCount(0)
    }).catch(() => {})
  }, [])

  const formatTime = (ts?: string | null) => {
    if (!ts) return ''
    const d = new Date(ts)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60_000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    return `${diffDay}d ago`
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label="Notifications"
        className="flex items-center justify-center rounded-lg size-10 bg-[var(--card)] text-[var(--foreground)] hover:bg-primary/20 transition-colors relative"
      >
        <Bell className="size-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-[var(--card)] border border-primary/10 rounded-lg shadow-xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-primary/10">
            <span className="text-sm font-semibold text-[var(--foreground)]">Notifications</span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="text-xs text-primary hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">
                No notifications
              </div>
            ) : (
              items.map(n => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleMarkRead(n.id, n.link)}
                  className={`w-full text-left px-4 py-3 border-b border-primary/5 hover:bg-primary/5 transition-colors ${
                    n.is_read ? 'opacity-60' : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && (
                      <span className="mt-1.5 w-2 h-2 rounded-full bg-primary flex-shrink-0" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--foreground)] truncate">{n.title}</p>
                      <p className="text-xs text-[var(--muted-foreground)] line-clamp-2">{n.message}</p>
                      <span className="text-[10px] text-[var(--muted-foreground)]">{formatTime(n.created_at)}</span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
