import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alerts as alertsApi, type Alert } from '@/lib/api'
import { formatEnum } from '@/lib/utils'
import { SkeletonTable } from '@/components/ui/SkeletonTable'
import {
  Bell,
  AlertTriangle,
  ShieldAlert,
  Info,
  Filter,
  Eye,
  CheckCheck,
} from 'lucide-react'

interface AlertsPageProps {
  readonly onError: (msg: string) => void
}

type StatusFilter = 'active' | 'acknowledged' | 'resolved' | 'all'
type TypeFilter = string | 'all'

const SEVERITY_CONFIG: Record<string, { icon: typeof AlertTriangle; colorClass: string; bgClass: string; borderClass: string }> = {
  critical: { icon: ShieldAlert, colorClass: 'text-red-600', bgClass: 'bg-red-50', borderClass: 'border-red-200' },
  warning: { icon: AlertTriangle, colorClass: 'text-amber-600', bgClass: 'bg-amber-50', borderClass: 'border-amber-200' },
  info: { icon: Info, colorClass: 'text-blue-600', bgClass: 'bg-blue-50', borderClass: 'border-blue-200' },
}

function SeverityBadge({ severity }: { severity: string }) {
  const config = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.info
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold border ${config.bgClass} ${config.colorClass} ${config.borderClass}`}>
      <Icon className="size-3" />
      {formatEnum(severity)}
    </span>
  )
}

function TypeBadge({ alertType }: { alertType: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-[var(--card)] text-[var(--muted-foreground)] border border-[var(--border)]">
      {formatEnum(alertType)}
    </span>
  )
}

function formatTimestamp(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function AlertsPage({ onError }: AlertsPageProps) {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('active')
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')

  const apiFilters = useMemo(() => {
    const f: { acknowledged?: boolean; resolved?: boolean; alert_type?: string } = {}
    if (statusFilter === 'active') {
      f.acknowledged = false
      f.resolved = false
    } else if (statusFilter === 'acknowledged') {
      f.acknowledged = true
      f.resolved = false
    } else if (statusFilter === 'resolved') {
      f.resolved = true
    }
    // 'all' sends no status filters
    if (typeFilter !== 'all') {
      f.alert_type = typeFilter
    }
    return f
  }, [statusFilter, typeFilter])

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', apiFilters],
    queryFn: () => alertsApi.list(apiFilters),
  })

  const { data: summary } = useQuery({
    queryKey: ['alertsSummary'],
    queryFn: () => alertsApi.summary(),
  })

  const items: Alert[] = data?.items ?? []

  const alertTypes = useMemo(() => {
    const types = summary?.by_type ? Object.keys(summary.by_type) : []
    return types.sort()
  }, [summary])

  const acknowledgeMutation = useMutation({
    mutationFn: (id: number) => alertsApi.acknowledge(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      queryClient.invalidateQueries({ queryKey: ['alertsSummary'] })
    },
    onError: (err: Error) => onError(err.message),
  })

  const resolveMutation = useMutation({
    mutationFn: (id: number) => alertsApi.resolve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      queryClient.invalidateQueries({ queryKey: ['alertsSummary'] })
    },
    onError: (err: Error) => onError(err.message),
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-[var(--foreground)]">Alerts</h2>
        </div>
        <SkeletonTable rows={5} columns={5} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold text-[var(--foreground)]">Alerts</h2>
          {summary != null && (
            <span className="text-sm text-[var(--muted-foreground)]">
              {summary.unacknowledged} unacknowledged
            </span>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-[var(--muted-foreground)]">
          <Filter className="size-4" />
          <span className="text-xs font-medium uppercase tracking-wider">Filters</span>
        </div>

        {/* Status filter */}
        <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
          {(['active', 'acknowledged', 'resolved', 'all'] as StatusFilter[]).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === s
                  ? 'bg-primary text-white'
                  : 'bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              {formatEnum(s)}
            </button>
          ))}
        </div>

        {/* Type filter */}
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)]"
        >
          <option value="all">All Types</option>
          {alertTypes.map((t) => (
            <option key={t} value={t}>{formatEnum(t)}</option>
          ))}
        </select>
      </div>

      {/* Alert List */}
      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-[var(--card)] flex items-center justify-center">
            <Bell className="size-6 text-[var(--muted-foreground)]" />
          </div>
          <h3 className="text-base font-semibold text-[var(--foreground)]">
            No alerts
          </h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            {statusFilter === 'all'
              ? 'No alerts have been generated yet.'
              : `No ${statusFilter} alerts found.`}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((alert) => (
            <div
              key={alert.id}
              className="flex items-start gap-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]/50 hover:bg-[var(--card)] transition-colors"
            >
              {/* Severity icon */}
              <div className="pt-0.5">
                {(() => {
                  const config = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.info
                  const Icon = config.icon
                  return <Icon className={`size-5 ${config.colorClass}`} />
                })()}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <SeverityBadge severity={alert.severity} />
                  <TypeBadge alertType={alert.alert_type} />
                  {alert.is_acknowledged && !alert.is_resolved && (
                    <span className="text-xs text-[var(--muted-foreground)] italic">Acknowledged</span>
                  )}
                  {alert.is_resolved && (
                    <span className="text-xs text-emerald-600 font-medium">Resolved</span>
                  )}
                </div>
                <p className="text-sm text-[var(--foreground)]">{alert.message}</p>
                <p className="text-xs text-[var(--muted-foreground)] mt-1">
                  {formatTimestamp(alert.created_at)}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                {!alert.is_acknowledged && !alert.is_resolved && (
                  <button
                    onClick={() => acknowledgeMutation.mutate(alert.id)}
                    disabled={acknowledgeMutation.isPending}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] hover:bg-[var(--border)] transition-colors disabled:opacity-50"
                    title="Acknowledge"
                  >
                    <Eye className="size-3.5" />
                    Acknowledge
                  </button>
                )}
                {!alert.is_resolved && (
                  <button
                    onClick={() => resolveMutation.mutate(alert.id)}
                    disabled={resolveMutation.isPending}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors disabled:opacity-50"
                    title="Resolve"
                  >
                    <CheckCheck className="size-3.5" />
                    Resolve
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
