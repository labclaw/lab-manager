import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Building2, User, Brain, Bell, Database, Info,
  Download, ChevronRight, Lock,
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
}

interface UserData {
  user: { id: number; name: string }
}

/* ---------- section card ---------- */

function SectionCard({
  icon: Icon,
  title,
  children,
}: {
  readonly icon: React.ElementType
  readonly title: string
  readonly children: React.ReactNode
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-6">
        <div className="size-9 flex items-center justify-center bg-primary/10 rounded-lg">
          <Icon className="size-5 text-primary" />
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
      Coming Soon
    </span>
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
  const version = config?.version ?? '0.1.9'
  const userName = userData?.user?.name ?? 'Admin'

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Lab Profile */}
      <SectionCard icon={Building2} title="Lab Profile">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Lab Name" value={labName} disabled />
          <Field label="Subtitle / Department" value={labSubtitle} disabled />
          <Field label="Institution" value="" disabled />
          <Field label="Address" value="" disabled />
          <Field label="PI Name" value="" disabled />
          <Field label="PI Email" value="" disabled type="email" />
        </div>
        <div className="mt-4 flex items-center gap-2">
          <ComingSoon />
          <span className="text-xs text-gray-400">Editing lab profile requires backend API support</span>
        </div>
      </SectionCard>

      {/* User Account */}
      <SectionCard icon={User} title="User Account">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Name" value={userName} disabled />
          <Field label="Role" value="Admin" disabled />
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
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label htmlFor="ocr-model" className="block text-sm font-medium text-gray-700 mb-1">OCR Model</label>
              <select
                id="ocr-model"
                disabled
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-500 bg-gray-50"
                defaultValue="llama-3.2-90b"
              >
                <option value="llama-3.2-90b">Llama 3.2 90B Vision</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="gemini-pro">Gemini Pro</option>
              </select>
            </div>
            <div>
              <label htmlFor="extraction-model" className="block text-sm font-medium text-gray-700 mb-1">Extraction Model</label>
              <select
                id="extraction-model"
                disabled
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-500 bg-gray-50"
                defaultValue="glm-5"
              >
                <option value="glm-5">GLM-5</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="claude-sonnet">Claude Sonnet</option>
              </select>
            </div>
            <div>
              <label htmlFor="rag-model" className="block text-sm font-medium text-gray-700 mb-1">RAG Model</label>
              <select
                id="rag-model"
                disabled
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-500 bg-gray-50"
                defaultValue="glm-5"
              >
                <option value="glm-5">GLM-5</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="claude-sonnet">Claude Sonnet</option>
              </select>
            </div>
          </div>

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
          <a
            href="/api/v1/export/inventory"
            className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <Download className="size-4 text-gray-400 group-hover:text-primary" />
              <div>
                <p className="text-sm font-medium text-gray-900">Export Inventory (CSV)</p>
                <p className="text-xs text-gray-500">Download all inventory items as CSV</p>
              </div>
            </div>
            <ChevronRight className="size-4 text-gray-300 group-hover:text-primary" />
          </a>

          <a
            href="/api/v1/export/orders"
            className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <Download className="size-4 text-gray-400 group-hover:text-primary" />
              <div>
                <p className="text-sm font-medium text-gray-900">Export Orders (CSV)</p>
                <p className="text-xs text-gray-500">Download all orders as CSV</p>
              </div>
            </div>
            <ChevronRight className="size-4 text-gray-300 group-hover:text-primary" />
          </a>

          <a
            href="/api/v1/export/products"
            className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <Download className="size-4 text-gray-400 group-hover:text-primary" />
              <div>
                <p className="text-sm font-medium text-gray-900">Export Products (CSV)</p>
                <p className="text-xs text-gray-500">Download all products as CSV</p>
              </div>
            </div>
            <ChevronRight className="size-4 text-gray-300 group-hover:text-primary" />
          </a>

          <a
            href="/api/v1/export/vendors"
            className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <Download className="size-4 text-gray-400 group-hover:text-primary" />
              <div>
                <p className="text-sm font-medium text-gray-900">Export Vendors (CSV)</p>
                <p className="text-xs text-gray-500">Download all vendors as CSV</p>
              </div>
            </div>
            <ChevronRight className="size-4 text-gray-300 group-hover:text-primary" />
          </a>
        </div>

        {/* Document processing stats */}
        {stats && (
          <div className="mt-6 pt-4 border-t border-gray-100">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Document Processing Stats</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.total_documents}</p>
                <p className="text-xs text-gray-500">Total Docs</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-primary">{stats.documents_approved}</p>
                <p className="text-xs text-gray-500">Approved</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-amber-600">{stats.documents_pending_review}</p>
                <p className="text-xs text-gray-500">Pending Review</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-900">{stats.total_vendors}</p>
                <p className="text-xs text-gray-500">Vendors</p>
              </div>
            </div>
          </div>
        )}
      </SectionCard>

      {/* About */}
      <SectionCard icon={Info} title="About">
        <div className="space-y-3">
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-sm text-gray-600">Version</span>
            <span className="text-sm font-mono font-semibold text-gray-900">v{version}</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-sm text-gray-600">API Endpoints</span>
            <span className="text-sm font-mono font-semibold text-gray-900">82</span>
          </div>
          {stats && (
            <>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Total Documents</span>
                <span className="text-sm font-mono font-semibold text-gray-900">{stats.total_documents}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Total Vendors</span>
                <span className="text-sm font-mono font-semibold text-gray-900">{stats.total_vendors}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-100">
                <span className="text-sm text-gray-600">Total Orders</span>
                <span className="text-sm font-mono font-semibold text-gray-900">{stats.total_orders}</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-gray-600">Total Inventory Items</span>
                <span className="text-sm font-mono font-semibold text-gray-900">{stats.total_inventory_items}</span>
              </div>
            </>
          )}
        </div>
      </SectionCard>
    </div>
  )
}
