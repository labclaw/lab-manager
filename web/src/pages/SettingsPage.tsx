import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Building2, User, Brain, Bell, Database, Info,
  Download, ChevronRight, Lock, AlertTriangle,
  Shield, Cpu, Server,
} from 'lucide-react'
import { analytics } from '@/lib/api'
import type { DashboardStats } from '@/lib/api'

interface SettingsPageProps {
  readonly onError: (msg: string) => void
}

interface ConfigData {
  lab_name: string
  lab_subtitle: string
  version: string
  ocr_model?: string
  extraction_model?: string
  rag_model?: string
  ocr_tier?: string
}

interface UserData {
  user: {
    id: number
    name: string
    email?: string | null
    role?: string
  }
}

/* ---------- model name helpers ---------- */

const MODEL_DISPLAY_NAMES: Record<string, string> = {
  'nvidia_nim/meta/llama-3.2-90b-vision-instruct': 'Llama 3.2 90B Vision',
  'nvidia_nim/z-ai/glm5': 'GLM-5',
  'nvidia_nim/z-ai/glm5-turbo': 'GLM-5 Turbo',
  'openai/gpt-4o': 'GPT-4o',
  'gemini/gemini-3-pro-preview': 'Gemini 3 Pro',
  'gemini/gemini-3-flash-preview': 'Gemini 3 Flash',
}

function friendlyModelName(modelId: string | undefined): string {
  if (!modelId) return 'Not configured'
  return MODEL_DISPLAY_NAMES[modelId] ?? modelId.split('/').pop() ?? modelId
}

function roleBadgeColor(role: string): string {
  switch (role) {
    case 'admin': return 'bg-purple-100 text-purple-700'
    case 'pi': return 'bg-blue-100 text-blue-700'
    case 'staff': return 'bg-green-100 text-green-700'
    default: return 'bg-gray-100 text-gray-600'
  }
}

/* ---------- section card ---------- */

function SectionCard({
  icon: Icon,
  title,
  children,
  variant = 'default',
}: {
  readonly icon: React.ElementType
  readonly title: string
  readonly children: React.ReactNode
  readonly variant?: 'default' | 'danger'
}) {
  const borderClass = variant === 'danger'
    ? 'border-red-200 bg-white'
    : 'border-gray-200 bg-white'
  const iconBgClass = variant === 'danger'
    ? 'bg-red-50'
    : 'bg-primary/10'
  const iconColorClass = variant === 'danger'
    ? 'text-red-500'
    : 'text-primary'

  return (
    <div className={`border rounded-xl p-6 shadow-sm ${borderClass}`}>
      <div className="flex items-center gap-3 mb-6">
        <div className={`size-9 flex items-center justify-center rounded-lg ${iconBgClass}`}>
          <Icon className={`size-5 ${iconColorClass}`} />
        </div>
        <h3 className="text-lg font-bold text-gray-900">{title}</h3>
      </div>
      {children}
    </div>
  )
}

/* ---------- reusable form field ---------- */

function Field({
  label,
  value,
  disabled = false,
  type = 'text',
}: {
  readonly label: string
  readonly value: string
  readonly disabled?: boolean
  readonly type?: string
}) {
  const id = label.toLowerCase().replace(/\s+/g, '-')
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        readOnly
        disabled={disabled}
        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 bg-white disabled:bg-gray-50 disabled:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
      />
    </div>
  )
}

/* ---------- toggle row ---------- */

function ToggleRow({
  label,
  description,
  defaultChecked = false,
  disabled = false,
}: {
  readonly label: string
  readonly description?: string
  readonly defaultChecked?: boolean
  readonly disabled?: boolean
}) {
  const [checked, setChecked] = useState(defaultChecked)
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setChecked(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
        } ${checked ? 'bg-primary' : 'bg-gray-200'}`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  )
}

/* ---------- coming soon badge ---------- */

function ComingSoon() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-gray-400 bg-gray-100 rounded-full">
      <Lock className="size-3" />
      Coming Soon
    </span>
  )
}

/* ---------- model card ---------- */

function ModelCard({
  label,
  modelId,
  icon: Icon,
}: {
  readonly label: string
  readonly modelId: string | undefined
  readonly icon: React.ElementType
}) {
  const displayName = friendlyModelName(modelId)
  return (
    <div className="p-4 border border-gray-200 rounded-lg bg-white">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="size-4 text-primary" />
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</span>
      </div>
      <p className="text-sm font-semibold text-gray-900">{displayName}</p>
      {modelId && (
        <p className="text-[11px] font-mono text-gray-400 mt-1 truncate" title={modelId}>{modelId}</p>
      )}
    </div>
  )
}

/* ---------- stat row ---------- */

function StatRow({
  label,
  value,
  last = false,
}: {
  readonly label: string
  readonly value: string | number
  readonly last?: boolean
}) {
  return (
    <div className={`flex items-center justify-between py-2.5 ${last ? '' : 'border-b border-gray-100'}`}>
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-mono font-semibold text-gray-900">{value}</span>
    </div>
  )
}

/* ---------- export link ---------- */

function ExportLink({
  href,
  title,
  description,
}: {
  readonly href: string
  readonly title: string
  readonly description: string
}) {
  return (
    <a
      href={href}
      className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-primary/30 transition-colors group"
    >
      <div className="flex items-center gap-3">
        <Download className="size-4 text-gray-400 group-hover:text-primary transition-colors" />
        <div>
          <p className="text-sm font-medium text-gray-900 group-hover:text-primary transition-colors">{title}</p>
          <p className="text-xs text-gray-500">{description}</p>
        </div>
      </div>
      <ChevronRight className="size-4 text-gray-300 group-hover:text-primary transition-colors" />
    </a>
  )
}

/* ---------- main component ---------- */

export function SettingsPage({ onError }: Readonly<SettingsPageProps>) {
  const { data: config } = useQuery({
    queryKey: ['lab-config'],
    queryFn: () =>
      fetch('/api/v1/config').then(async (res) => {
        if (!res.ok) throw new Error('Failed to load config')
        return res.json() as Promise<ConfigData>
      }),
  })

  const { data: userData } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () =>
      fetch('/api/v1/auth/me').then(async (res) => {
        if (!res.ok) throw new Error('Failed to load user')
        return res.json() as Promise<UserData>
      }),
  })

  const { data: stats, error: statsErr } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => analytics.dashboard() as Promise<DashboardStats>,
  })

  if (statsErr) {
    onError(statsErr instanceof Error ? statsErr.message : 'Failed to load stats')
  }

  const labName = config?.lab_name ?? 'My Lab'
  const labSubtitle = config?.lab_subtitle ?? ''
  const version = config?.version ?? '0.2.0'
  const userName = userData?.user?.name ?? 'Admin'
  const userEmail = userData?.user?.email ?? ''
  const userRole = userData?.user?.role ?? 'admin'

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Lab Profile */}
      <SectionCard icon={Building2} title="Lab Profile">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Lab Name" value={labName} disabled />
          <Field label="Subtitle / Department" value={labSubtitle} disabled />
          <Field label="Institution" value="" disabled />
          <Field label="PI Name" value="" disabled />
        </div>
        <div className="mt-4 flex items-center gap-2">
          <ComingSoon />
          <span className="text-xs text-gray-400">Editing lab profile requires backend API support</span>
        </div>
      </SectionCard>

      {/* User Account */}
      <SectionCard icon={User} title="User Account">
        <div className="flex items-start gap-6">
          {/* Avatar */}
          <div className="size-16 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
            <span className="text-2xl font-bold text-primary">
              {userName.charAt(0).toUpperCase()}
            </span>
          </div>
          {/* User info */}
          <div className="flex-1 space-y-3">
            <div>
              <h4 className="text-base font-semibold text-gray-900">{userName}</h4>
              {userEmail && (
                <p className="text-sm text-gray-500">{userEmail}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full capitalize ${roleBadgeColor(userRole)}`}>
                <Shield className="size-3" />
                {userRole}
              </span>
            </div>
          </div>
        </div>
        <div className="mt-6 pt-4 border-t border-gray-100">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="size-4 text-gray-400" />
            <h4 className="text-sm font-semibold text-gray-700">Change Password</h4>
            <ComingSoon />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 opacity-50">
            <Field label="Current Password" value="" type="password" disabled />
            <Field label="New Password" value="" type="password" disabled />
            <Field label="Confirm Password" value="" type="password" disabled />
          </div>
        </div>
      </SectionCard>

      {/* AI Configuration */}
      <SectionCard icon={Brain} title="AI Configuration">
        <div className="space-y-4">
          {/* Model cards - show real model IDs from config */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <ModelCard
              label="OCR Model"
              modelId={config?.ocr_model}
              icon={Cpu}
            />
            <ModelCard
              label="Extraction Model"
              modelId={config?.extraction_model}
              icon={Brain}
            />
            <ModelCard
              label="RAG Model"
              modelId={config?.rag_model}
              icon={Server}
            />
          </div>

          {/* OCR Tier */}
          {config?.ocr_tier && (
            <div className="flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-lg">
              <span className="text-sm text-gray-600">OCR Tier:</span>
              <span className={`inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-full ${
                config.ocr_tier === 'auto' ? 'bg-green-100 text-green-700' :
                config.ocr_tier === 'api' ? 'bg-blue-100 text-blue-700' :
                'bg-gray-100 text-gray-600'
              }`}>
                {config.ocr_tier.toUpperCase()}
              </span>
              <span className="text-xs text-gray-400">
                {config.ocr_tier === 'auto' && 'Local first, API fallback'}
                {config.ocr_tier === 'api' && 'Cloud APIs only'}
                {config.ocr_tier === 'local' && 'Local vLLM only'}
              </span>
            </div>
          )}

          <div className="pt-2">
            <ToggleRow
              label="Auto-process uploads"
              description="Automatically run OCR and extraction on new documents"
              defaultChecked
              disabled
            />
          </div>

          <div className="pt-2">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Confidence threshold for auto-approve
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="80"
                max="100"
                defaultValue="95"
                disabled
                className="flex-1 h-2 bg-gray-200 rounded-full appearance-none cursor-not-allowed"
              />
              <span className="text-sm font-mono text-gray-500 w-12 text-right">0.95</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <ComingSoon />
            <span className="text-xs text-gray-400">Model configuration changes require server restart</span>
          </div>
        </div>
      </SectionCard>

      {/* Notifications */}
      <SectionCard icon={Bell} title="Notifications">
        <div>
          <ToggleRow
            label="Email notifications"
            description="Receive email alerts for critical events"
            disabled
          />
          <ToggleRow
            label="Low stock alerts"
            description="Notify when inventory items fall below reorder level"
            defaultChecked
            disabled
          />
          <ToggleRow
            label="Expiring reagents alerts"
            description="Notify when reagents are nearing expiry date"
            defaultChecked
            disabled
          />
          <ToggleRow
            label="New document processed"
            description="Notify when a new document finishes AI processing"
            disabled
          />
        </div>
        <div className="mt-4 flex items-center gap-2">
          <ComingSoon />
          <span className="text-xs text-gray-400">Notification preferences will be stored per-user</span>
        </div>
      </SectionCard>

      {/* Data Management */}
      <SectionCard icon={Database} title="Data Management">
        <div className="space-y-3">
          <ExportLink
            href="/api/v1/export/inventory"
            title="Export Inventory (CSV)"
            description="Download all inventory items as CSV"
          />
          <ExportLink
            href="/api/v1/export/orders"
            title="Export Orders (CSV)"
            description="Download all orders as CSV"
          />
          <ExportLink
            href="/api/v1/export/products"
            title="Export Products (CSV)"
            description="Download all products as CSV"
          />
          <ExportLink
            href="/api/v1/export/vendors"
            title="Export Vendors (CSV)"
            description="Download all vendors as CSV"
          />
        </div>

        {/* Database stats */}
        {stats && (
          <div className="mt-6 pt-4 border-t border-gray-100">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Database Stats</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.total_documents}</p>
                <p className="text-xs text-gray-500">Documents</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.total_vendors}</p>
                <p className="text-xs text-gray-500">Vendors</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.total_orders}</p>
                <p className="text-xs text-gray-500">Orders</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.total_inventory_items}</p>
                <p className="text-xs text-gray-500">Inventory Items</p>
              </div>
            </div>
          </div>
        )}

        {/* Backup - coming soon */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-gray-50/50">
            <div className="flex items-center gap-3">
              <Database className="size-4 text-gray-300" />
              <div>
                <p className="text-sm font-medium text-gray-400">Backup Database</p>
                <p className="text-xs text-gray-400">Create a full database backup</p>
              </div>
            </div>
            <ComingSoon />
          </div>
        </div>
      </SectionCard>

      {/* System Info */}
      <SectionCard icon={Info} title="System Info">
        <div className="space-y-1">
          <StatRow label="Version" value={`v${version}`} />
          {stats && (
            <>
              <StatRow label="Total Documents" value={stats.total_documents} />
              <StatRow label="Approved" value={stats.documents_approved} />
              <StatRow label="Pending Review" value={stats.documents_pending_review} />
              <StatRow label="Total Vendors" value={stats.total_vendors} />
              <StatRow label="Total Orders" value={stats.total_orders} />
              <StatRow label="Total Inventory Items" value={stats.total_inventory_items} last />
            </>
          )}
          {!stats && (
            <StatRow label="Status" value="Loading..." last />
          )}
        </div>
      </SectionCard>

      {/* Danger Zone */}
      <SectionCard icon={AlertTriangle} title="Danger Zone" variant="danger">
        <div className="space-y-3">
          <ExportLink
            href="/api/v1/export/inventory"
            title="Export Full Database"
            description="Download all data tables as CSV files"
          />

          <div className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-gray-50/50">
            <div className="flex items-center gap-3">
              <AlertTriangle className="size-4 text-gray-300" />
              <div>
                <p className="text-sm font-medium text-gray-400">Reset to Default Settings</p>
                <p className="text-xs text-gray-400">Restore all settings to factory defaults</p>
              </div>
            </div>
            <ComingSoon />
          </div>

          <div className="flex items-center justify-between p-3 border border-red-200 rounded-lg bg-red-50/30">
            <div className="flex items-center gap-3">
              <AlertTriangle className="size-4 text-red-300" />
              <div>
                <p className="text-sm font-medium text-red-400">Delete All Data</p>
                <p className="text-xs text-red-300">Permanently remove all documents, orders, and inventory</p>
              </div>
            </div>
            <ComingSoon />
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
