import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Monitor,
  Search,
  Wifi,
  WifiOff,
  Cpu,
  HardDrive,
  MemoryStick,
  Clock,
  Globe,
} from 'lucide-react'
import { devices } from '@/lib/api'
import type { Device } from '@/lib/api'

interface DevicesPageProps {
  readonly onError: (msg: string) => void
}

type StatusFilter = 'all' | 'online' | 'offline' | 'error'

function relativeTime(dateStr?: string | null): string {
  if (!dateStr) return 'Never'
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  if (diffMs < 0) return 'just now'
  const seconds = Math.floor(diffMs / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function platformIcon(platform?: string | null) {
  const p = (platform ?? '').toLowerCase()
  if (p.includes('linux')) return '🖥'
  if (p.includes('windows')) return '🖥'
  if (p.includes('darwin') || p.includes('mac')) return '🖥'
  return '🖥'
}

function statusBadge(status: string) {
  switch (status) {
    case 'online':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-green-100 text-green-700 border border-green-200">
          <span className="size-1.5 rounded-full bg-green-500" />
          Online
        </span>
      )
    case 'offline':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-gray-100 text-gray-500 border border-gray-200">
          <WifiOff className="size-3" />
          Offline
        </span>
      )
    case 'error':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-600 border border-red-200">
          <span className="size-1.5 rounded-full bg-red-500" />
          Error
        </span>
      )
    default:
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 text-xs font-semibold rounded-full bg-gray-100 text-gray-500 border border-gray-200">
          {status}
        </span>
      )
  }
}

function MetricBar({ label, value, icon }: { label: string; value: number | null | undefined; icon: React.ReactNode }) {
  const pct = value != null ? Math.min(100, Math.max(0, value)) : null
  const color = pct == null ? 'bg-gray-200' : pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-amber-500' : 'bg-green-500'
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted-foreground)]">
        {icon}
        <span className="truncate">{label}</span>
        <span className="ml-auto font-semibold text-on-surface tabular-nums">
          {pct != null ? `${pct.toFixed(0)}%` : '--'}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
        {pct != null && (
          <div
            className={`h-full rounded-full transition-all ${color}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  )
}

function DeviceCard({ device }: { readonly device: Device }) {
  return (
    <div className="bg-[var(--card)] rounded-xl border border-outline shadow-sm p-4 flex flex-col gap-3 hover:shadow-md transition-shadow">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="size-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 text-lg">
            {platformIcon(device.platform)}
          </div>
          <div className="min-w-0">
            <p className="font-bold text-on-surface text-sm truncate">{device.hostname}</p>
            <p className="text-[11px] text-[var(--muted-foreground)] font-mono truncate">
              {device.device_id}
            </p>
          </div>
        </div>
        {statusBadge(device.status)}
      </div>

      {/* Network info */}
      <div className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
        {device.ip_address && (
          <div className="flex items-center gap-1.5">
            <Globe className="size-3 shrink-0" />
            <span className="truncate">{device.ip_address}</span>
          </div>
        )}
        {device.tailscale_ip && (
          <div className="flex items-center gap-1.5">
            <Wifi className="size-3 shrink-0 text-primary" />
            <span className="truncate font-mono">{device.tailscale_ip}</span>
            {device.tailscale_exit_node && (
              <span className="ml-auto text-[10px] font-semibold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                Exit Node
              </span>
            )}
          </div>
        )}
        {device.os_version && (
          <p className="truncate text-[11px]">{device.os_version}</p>
        )}
      </div>

      {/* Metrics */}
      <div className="flex flex-col gap-2 pt-1 border-t border-outline">
        <MetricBar label="CPU" value={device.cpu_percent} icon={<Cpu className="size-3" />} />
        <MetricBar label="Memory" value={device.memory_percent} icon={<MemoryStick className="size-3" />} />
        <MetricBar label="Disk" value={device.disk_percent} icon={<HardDrive className="size-3" />} />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)] pt-1 border-t border-outline">
        <div className="flex items-center gap-1">
          <Clock className="size-3" />
          <span>{relativeTime(device.last_heartbeat_at)}</span>
        </div>
        {device.first_seen_at && (
          <span>
            Since {new Date(device.first_seen_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </span>
        )}
      </div>
    </div>
  )
}

export function DevicesPage({ onError }: DevicesPageProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [search, setSearch] = useState('')

  const { data: res, isLoading, error } = useQuery({
    queryKey: ['devices', statusFilter, search],
    queryFn: () =>
      devices.list(
        1,
        200,
        statusFilter === 'all' ? undefined : statusFilter,
        search || undefined,
      ),
    refetchInterval: 30_000, // Auto-refresh every 30s
  })

  useEffect(() => {
    if (error) {
      onError(error instanceof Error ? error.message : 'Failed to load devices')
    }
  }, [error, onError])

  const deviceList: Device[] = res?.items ?? []
  const total = res?.total ?? 0
  const onlineCount = deviceList.filter((d) => d.status === 'online').length
  const offlineCount = deviceList.filter((d) => d.status === 'offline').length

  const statusTabs: { value: StatusFilter; label: string; count?: number }[] = [
    { value: 'all', label: 'All', count: total },
    { value: 'online', label: 'Online', count: onlineCount },
    { value: 'offline', label: 'Offline', count: offlineCount },
  ]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Summary + Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {statusTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                statusFilter === tab.value
                  ? 'bg-primary text-white'
                  : 'bg-[var(--card)] text-[var(--muted-foreground)] border border-outline hover:bg-surface-container-high'
              }`}
            >
              {tab.label}
              {tab.count != null && (
                <span className={`ml-1.5 ${statusFilter === tab.value ? 'text-white/70' : 'text-[var(--muted-foreground)]'}`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--muted-foreground)]" />
          <input
            type="text"
            placeholder="Search hostname, IP..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-outline rounded-lg text-sm bg-[var(--card)] text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
          />
        </div>
      </div>

      {/* Summary bar */}
      <div className="text-xs text-[var(--muted-foreground)] font-medium">
        {total} device{total !== 1 ? 's' : ''} total
        {onlineCount > 0 && <span className="ml-2 text-green-600">{onlineCount} online</span>}
        {offlineCount > 0 && <span className="ml-2 text-gray-400">{offlineCount} offline</span>}
      </div>

      {/* Device Grid */}
      {deviceList.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-surface-container-high flex items-center justify-center">
            <Monitor className="size-5 text-[var(--muted-foreground)]" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-on-surface">No devices found</h3>
            <p className="text-sm text-[var(--muted-foreground)] max-w-xs mx-auto">
              Devices will appear here once they start sending heartbeats via the Tailscale mesh network.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {deviceList.map((device) => (
            <DeviceCard key={device.id} device={device} />
          ))}
        </div>
      )}
    </div>
  )
}
