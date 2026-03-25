import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bot,
  Package,
  ClipboardList,
  BarChart3,
  Clock,
  ChevronDown,
  Send,
  Plus,
  Search,
  Trash2,
  Pencil,
  Download,
  Copy,
  X,
  Menu,
  MessageSquare,
  AlertTriangle,
  Check,
} from 'lucide-react'
import { ask } from '@/lib/api'
import type { AskEvidenceRow, AskResponse } from '@/lib/api'

/* ────────────────────────────────────────────────────────────────────────── */
/*  Types                                                                    */
/* ────────────────────────────────────────────────────────────────────────── */

interface AskPageProps {
  readonly onError: (msg: string) => void
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sql?: string | null
  evidence?: AskEvidenceRow[]
  source?: string
  rowCount?: number
  timestamp: string
}

interface ChatConversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}

type AskTurn = {
  readonly id: string
  readonly question: string
  readonly status: 'loading' | 'done' | 'error'
  readonly answer?: string
  readonly source?: string
  readonly sql?: string | null
  readonly evidence?: AskEvidenceRow[]
  readonly rowCount?: number
  readonly error?: string
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Constants                                                                */
/* ────────────────────────────────────────────────────────────────────────── */

const STORAGE_KEY = 'labclaw-chat-history'
const STORAGE_WARNING_BYTES = 5 * 1024 * 1024 // 5 MB

const SUGGESTED_PROMPTS = [
  { icon: Package, text: 'What orders were received this month?', color: 'text-blue-600' },
  { icon: BarChart3, text: 'Which vendors have the most orders?', color: 'text-violet-600' },
  { icon: ClipboardList, text: 'How many products do we have in inventory?', color: 'text-emerald-600' },
  { icon: Clock, text: 'Which items are expiring soon?', color: 'text-amber-600' },
] as const

const MAX_QUESTION_LENGTH = 2000

/* ────────────────────────────────────────────────────────────────────────── */
/*  Storage helpers                                                          */
/* ────────────────────────────────────────────────────────────────────────── */

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`
}

function loadConversations(): ChatConversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as ChatConversation[]
  } catch {
    return []
  }
}

function saveConversations(convos: ChatConversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(convos))
  } catch {
    // Storage full — handled by warning check
  }
}

function getStorageSize(): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? new Blob([raw]).size : 0
  } catch {
    return 0
  }
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Date grouping                                                            */
/* ────────────────────────────────────────────────────────────────────────── */

function getDateGroup(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)
  const monthAgo = new Date(today.getTime() - 30 * 86400000)

  if (date >= today) return 'Today'
  if (date >= yesterday) return 'Yesterday'
  if (date >= weekAgo) return 'This Week'
  if (date >= monthAgo) return 'This Month'
  return 'Older'
}

function groupConversations(convos: ChatConversation[]): Map<string, ChatConversation[]> {
  const groups = new Map<string, ChatConversation[]>()
  const order = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older']

  for (const label of order) {
    groups.set(label, [])
  }

  const sorted = [...convos].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  )

  for (const convo of sorted) {
    const group = getDateGroup(convo.updatedAt)
    const list = groups.get(group) ?? []
    list.push(convo)
    groups.set(group, list)
  }

  // Remove empty groups
  for (const [key, val] of groups) {
    if (val.length === 0) groups.delete(key)
  }

  return groups
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Export helpers                                                           */
/* ────────────────────────────────────────────────────────────────────────── */

function exportAsMarkdown(convo: ChatConversation): string {
  const dateStr = new Date(convo.createdAt).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
  const lines: string[] = [`# Lab Manager Chat - ${dateStr}`, '', `**${convo.title}**`, '']

  for (const msg of convo.messages) {
    if (msg.role === 'user') {
      lines.push(`**You:** ${msg.content}`, '')
    } else {
      lines.push(`**Lab Manager:** ${msg.content}`)
      if (msg.sql) {
        lines.push(`> SQL: ${msg.sql}`)
      }
      lines.push('')
    }
  }

  return lines.join('\n')
}

function exportAsJson(convo: ChatConversation): string {
  return JSON.stringify(convo, null, 2)
}

function downloadFile(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Contextual question builder (kept from original)                         */
/* ────────────────────────────────────────────────────────────────────────── */

function trimForPrompt(text: string, limit: number): string {
  if (limit <= 0) return ''
  return text.length <= limit ? text : text.slice(0, Math.max(0, limit - 1)).trimEnd() + '\u2026'
}

function buildContextualQuestion(turns: AskTurn[], currentQuestion: string): string {
  const trimmed = currentQuestion.trim()
  const priorTurns = turns.filter((turn) => turn.status === 'done' && turn.answer).slice(-3)
  if (priorTurns.length === 0) return trimmed

  const intro = [
    'Continue this lab operations conversation using the recent context when it is relevant.',
    'Keep the answer grounded in the lab manager data and do not invent facts.',
  ].join('\n')
  const currentBlock = `Current question:\n${trimmed}`
  const reserved = intro.length + currentBlock.length + 32
  const transcriptBudget = Math.max(0, MAX_QUESTION_LENGTH - reserved)
  const transcriptBlocks: string[] = []
  let used = 0

  for (const turn of priorTurns.reverse()) {
    const block = `User: ${turn.question}\nAssistant: ${turn.answer ?? ''}`
    const remaining = transcriptBudget - used
    if (remaining <= 0) break
    const fitted = trimForPrompt(block, remaining)
    transcriptBlocks.unshift(fitted)
    used += fitted.length + 2
  }

  return [
    intro,
    transcriptBlocks.length > 0 ? `Recent conversation:\n${transcriptBlocks.join('\n\n')}` : '',
    currentBlock,
  ].filter(Boolean).join('\n\n')
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Rendering helpers (kept from original)                                   */
/* ────────────────────────────────────────────────────────────────────────── */

function formatEvidenceRow(row: AskEvidenceRow): string {
  return JSON.stringify(row, null, 2)
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i}>{part.slice(1, -1)}</em>
    }
    return part
  })
}

function SimpleMarkdown({ text }: Readonly<{ text: string }>) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!
    const trimmed = line.trim()

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || /^\d+\.\s/.test(trimmed)) {
      const content = trimmed.replace(/^[-*]\s|^\d+\.\s/, '')
      elements.push(
        <li key={i} className="ml-4 list-disc text-sm leading-7 text-gray-800">
          {renderInline(content)}
        </li>
      )
    } else if (trimmed === '') {
      elements.push(<br key={i} />)
    } else {
      elements.push(
        <p key={i} className="text-sm leading-7 text-gray-800">
          {renderInline(trimmed)}
        </p>
      )
    }
  }

  return <div className="space-y-1">{elements}</div>
}

function SQLDetail({ sql, evidence, source, rowCount }: Readonly<{
  sql?: string | null
  evidence: AskEvidenceRow[]
  source?: string
  rowCount?: number
}>) {
  const [open, setOpen] = useState(false)
  const hasContent = sql || evidence.length > 0

  if (!hasContent) return null

  return (
    <div className="mt-3 border border-gray-100 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-gray-500 hover:bg-gray-50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-primary" />
          {source === 'sql' ? 'SQL evidence' : 'Search evidence'}
          {rowCount != null && <span className="text-gray-400">({rowCount} row{rowCount === 1 ? '' : 's'})</span>}
        </span>
        <ChevronDown className={`size-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100">
          {sql && (
            <div className="mt-3">
              <div className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1.5">SQL Query</div>
              <pre className="whitespace-pre-wrap break-words text-xs leading-6 text-gray-600 bg-gray-50 rounded-lg p-3 overflow-x-auto">
                {sql}
              </pre>
            </div>
          )}
          {evidence.length > 0 && (
            <div className="mt-2 space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1.5">Evidence rows</div>
              {evidence.slice(0, 3).map((row, idx) => (
                <pre
                  key={`${idx}-${Object.keys(row).join('-')}`}
                  className="whitespace-pre-wrap break-words text-xs leading-5 text-gray-600 bg-gray-50 rounded-lg p-3 overflow-x-auto"
                >
                  {formatEvidenceRow(row)}
                </pre>
              ))}
              {evidence.length > 3 && (
                <p className="text-xs text-gray-400">Showing 3 of {evidence.length} rows.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Sidebar components                                                       */
/* ────────────────────────────────────────────────────────────────────────── */

function ConversationItem({
  convo,
  isActive,
  onSelect,
  onDelete,
  onRename,
  onExport,
  onCopyText,
}: Readonly<{
  convo: ChatConversation
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
  onRename: (title: string) => void
  onExport: (format: 'md' | 'json') => void
  onCopyText: () => void
}>) {
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(convo.title)
  const [showActions, setShowActions] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const handleRename = () => {
    const trimmed = editValue.trim()
    if (trimmed && trimmed !== convo.title) {
      onRename(trimmed)
    }
    setEditing(false)
  }

  const handleCopy = () => {
    onCopyText()
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className={`group relative rounded-lg transition-colors ${
        isActive ? 'bg-gray-200' : 'hover:bg-gray-100'
      }`}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => {
        setShowActions(false)
        setExportOpen(false)
        if (!editing) setConfirmDelete(false)
      }}
    >
      <button
        type="button"
        onClick={onSelect}
        className="w-full text-left px-3 py-2.5 rounded-lg"
      >
        {editing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleRename}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleRename()
              if (e.key === 'Escape') setEditing(false)
            }}
            onClick={(e) => e.stopPropagation()}
            className="w-full text-sm bg-white border border-gray-300 rounded px-1.5 py-0.5 focus:outline-none focus:border-primary"
          />
        ) : (
          <>
            <div className="text-sm text-gray-800 truncate pr-16 font-medium">{convo.title}</div>
            <div className="text-[11px] text-gray-400 mt-0.5">
              {convo.messages.length} message{convo.messages.length === 1 ? '' : 's'}
            </div>
          </>
        )}
      </button>

      {/* Action buttons */}
      {showActions && !editing && (
        <div className="absolute right-1.5 top-1.5 flex items-center gap-0.5">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setEditing(true); setEditValue(convo.title) }}
            className="p-1 rounded hover:bg-gray-300 text-gray-400 hover:text-gray-600 transition-colors"
            title="Rename"
          >
            <Pencil className="size-3" />
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleCopy() }}
            className="p-1 rounded hover:bg-gray-300 text-gray-400 hover:text-gray-600 transition-colors"
            title="Copy as text"
          >
            {copied ? <Check className="size-3 text-green-500" /> : <Copy className="size-3" />}
          </button>
          <div className="relative">
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setExportOpen(!exportOpen) }}
              className="p-1 rounded hover:bg-gray-300 text-gray-400 hover:text-gray-600 transition-colors"
              title="Export"
            >
              <Download className="size-3" />
            </button>
            {exportOpen && (
              <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1 min-w-[120px]">
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onExport('md'); setExportOpen(false) }}
                  className="w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50"
                >
                  Markdown (.md)
                </button>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onExport('json'); setExportOpen(false) }}
                  className="w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50"
                >
                  JSON (.json)
                </button>
              </div>
            )}
          </div>
          {confirmDelete ? (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="p-1 rounded bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
              title="Confirm delete"
            >
              <Check className="size-3" />
            </button>
          ) : (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setConfirmDelete(true) }}
              className="p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500 transition-colors"
              title="Delete"
            >
              <Trash2 className="size-3" />
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function ChatSidebar({
  conversations,
  activeId,
  searchQuery,
  onSearchChange,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  onRenameConversation,
  onExportConversation,
  onCopyConversation,
  storageWarning,
  onClearOld,
  onExportAll,
  mobileOpen,
  onMobileClose,
}: Readonly<{
  conversations: ChatConversation[]
  activeId: string | null
  searchQuery: string
  onSearchChange: (q: string) => void
  onSelectConversation: (id: string) => void
  onNewChat: () => void
  onDeleteConversation: (id: string) => void
  onRenameConversation: (id: string, title: string) => void
  onExportConversation: (id: string, format: 'md' | 'json') => void
  onCopyConversation: (id: string) => void
  storageWarning: boolean
  onClearOld: () => void
  onExportAll: () => void
  mobileOpen: boolean
  onMobileClose: () => void
}>) {
  const filtered = searchQuery.trim()
    ? conversations.filter((c) => {
        const q = searchQuery.toLowerCase()
        return (
          c.title.toLowerCase().includes(q) ||
          c.messages.some((m) => m.content.toLowerCase().includes(q))
        )
      })
    : conversations

  const grouped = groupConversations(filtered)

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
        className={`flex flex-col bg-gray-50 border-r border-gray-200 w-[280px] shrink-0 h-full transition-transform duration-200 ${
          mobileOpen
            ? 'fixed inset-y-0 left-0 z-50 translate-x-0 md:relative md:z-auto'
            : 'hidden md:flex relative'
        }`}
      >
        {/* New Chat button */}
        <div className="p-3 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onNewChat}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <Plus className="size-4" />
              New Chat
            </button>
            <button
              type="button"
              onClick={onMobileClose}
              className="p-2 rounded-lg hover:bg-gray-200 text-gray-500 md:hidden"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="px-3 py-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search chats..."
              className="w-full pl-8 pr-3 py-2 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-primary placeholder:text-gray-400"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => onSearchChange('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="size-3" />
              </button>
            )}
          </div>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2">
          {filtered.length === 0 ? (
            <div className="px-3 py-8 text-center">
              <MessageSquare className="size-8 text-gray-300 mx-auto mb-2" />
              <p className="text-xs text-gray-400">
                {searchQuery ? 'No matching conversations' : 'No conversations yet'}
              </p>
            </div>
          ) : (
            Array.from(grouped.entries()).map(([group, convos]) => (
              <div key={group} className="mb-2">
                <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-gray-400">
                  {group}
                </div>
                <div className="space-y-0.5">
                  {convos.map((convo) => (
                    <ConversationItem
                      key={convo.id}
                      convo={convo}
                      isActive={convo.id === activeId}
                      onSelect={() => onSelectConversation(convo.id)}
                      onDelete={() => onDeleteConversation(convo.id)}
                      onRename={(title) => onRenameConversation(convo.id, title)}
                      onExport={(format) => onExportConversation(convo.id, format)}
                      onCopyText={() => onCopyConversation(convo.id)}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Storage warning */}
        {storageWarning && (
          <div className="mx-3 mb-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertTriangle className="size-3.5 text-amber-500 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-[11px] text-amber-700 font-medium">Storage almost full</p>
                <div className="flex gap-2 mt-1.5">
                  <button
                    type="button"
                    onClick={onExportAll}
                    className="text-[10px] text-amber-600 hover:text-amber-800 underline"
                  >
                    Export all
                  </button>
                  <button
                    type="button"
                    onClick={onClearOld}
                    className="text-[10px] text-amber-600 hover:text-amber-800 underline"
                  >
                    Clear old chats
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-3 border-t border-gray-200 text-center">
          <p className="text-[10px] text-gray-400">
            {conversations.length} conversation{conversations.length === 1 ? '' : 's'}
          </p>
        </div>
      </aside>
    </>
  )
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Main AskPage                                                             */
/* ────────────────────────────────────────────────────────────────────────── */

export function AskPage({ onError }: Readonly<AskPageProps>) {
  const [conversations, setConversations] = useState<ChatConversation[]>(() => loadConversations())
  const [activeConvoId, setActiveConvoId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<AskTurn[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const turnsRef = useRef(turns)
  turnsRef.current = turns

  // eslint-disable-next-line react-hooks/exhaustive-deps -- re-check when conversations list changes
  const storageWarning = useMemo(() => getStorageSize() >= STORAGE_WARNING_BYTES, [conversations.length])

  const canSubmit = question.trim().length > 0 && question.length <= MAX_QUESTION_LENGTH && !submitting
  const remainingChars = MAX_QUESTION_LENGTH - question.length

  // Persist conversations to localStorage
  const persistConversations = useCallback((updated: ChatConversation[]) => {
    setConversations(updated)
    saveConversations(updated)
  }, [])

  // Convert turns to ChatMessages for storage
  const turnsToMessages = useCallback((turnList: AskTurn[]): ChatMessage[] => {
    const messages: ChatMessage[] = []
    for (const turn of turnList) {
      messages.push({
        role: 'user',
        content: turn.question,
        timestamp: new Date().toISOString(),
      })
      if (turn.status === 'done' && turn.answer) {
        messages.push({
          role: 'assistant',
          content: turn.answer,
          sql: turn.sql,
          evidence: turn.evidence,
          source: turn.source,
          rowCount: turn.rowCount,
          timestamp: new Date().toISOString(),
        })
      }
    }
    return messages
  }, [])

  // Save current turns to active conversation
  const saveCurrentConversation = useCallback((currentTurns: AskTurn[], convoId: string | null) => {
    if (!convoId) return
    const completedTurns = currentTurns.filter((t) => t.status === 'done')
    if (completedTurns.length === 0) return

    const messages = turnsToMessages(completedTurns)
    const now = new Date().toISOString()
    const existing = loadConversations()
    const idx = existing.findIndex((c) => c.id === convoId)

    if (idx >= 0) {
      existing[idx] = { ...existing[idx]!, messages, updatedAt: now }
    } else {
      const title = completedTurns[0]?.question.slice(0, 50) ?? 'New conversation'
      existing.unshift({
        id: convoId,
        title,
        messages,
        createdAt: now,
        updatedAt: now,
      })
    }

    persistConversations(existing)
  }, [persistConversations, turnsToMessages])

  // Scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [turns])

  const latestHint = useMemo(() => {
    const last = turns[turns.length - 1]
    if (!last) return ''
    if (last.status === 'loading') return 'Searching the lab data...'
    if (last.status === 'error') return 'Something went wrong. Try again.'
    return ''
  }, [turns])

  // Load a conversation from history
  const loadConversation = useCallback((convoId: string) => {
    const convo = conversations.find((c) => c.id === convoId)
    if (!convo) return

    const loaded: AskTurn[] = []
    let userMsg: ChatMessage | null = null

    for (const msg of convo.messages) {
      if (msg.role === 'user') {
        userMsg = msg
      } else if (msg.role === 'assistant' && userMsg) {
        loaded.push({
          id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          question: userMsg.content,
          status: 'done',
          answer: msg.content,
          sql: msg.sql,
          evidence: msg.evidence ?? [],
          source: msg.source,
          rowCount: msg.rowCount,
        })
        userMsg = null
      }
    }

    setTurns(loaded)
    setActiveConvoId(convoId)
    setQuestion('')
    setLocalError(null)
    setSidebarMobileOpen(false)
  }, [conversations])

  // New chat
  const handleNewChat = useCallback(() => {
    setTurns([])
    setActiveConvoId(null)
    setQuestion('')
    setLocalError(null)
    setSidebarMobileOpen(false)
  }, [])

  // Delete conversation
  const handleDeleteConversation = useCallback((id: string) => {
    const updated = loadConversations().filter((c) => c.id !== id)
    persistConversations(updated)
    if (activeConvoId === id) {
      setTurns([])
      setActiveConvoId(null)
    }
  }, [activeConvoId, persistConversations])

  // Rename conversation
  const handleRenameConversation = useCallback((id: string, title: string) => {
    const existing = loadConversations()
    const idx = existing.findIndex((c) => c.id === id)
    if (idx >= 0) {
      existing[idx] = { ...existing[idx]!, title }
      persistConversations(existing)
    }
  }, [persistConversations])

  // Export conversation
  const handleExportConversation = useCallback((id: string, format: 'md' | 'json') => {
    const convo = conversations.find((c) => c.id === id)
    if (!convo) return

    const safeTitle = convo.title.replace(/[^a-zA-Z0-9-_ ]/g, '').slice(0, 40).trim()
    if (format === 'md') {
      downloadFile(exportAsMarkdown(convo), `chat-${safeTitle}.md`, 'text/markdown')
    } else {
      downloadFile(exportAsJson(convo), `chat-${safeTitle}.json`, 'application/json')
    }
  }, [conversations])

  // Copy conversation as text
  const handleCopyConversation = useCallback((id: string) => {
    const convo = conversations.find((c) => c.id === id)
    if (!convo) return
    const text = exportAsMarkdown(convo)
    navigator.clipboard.writeText(text).catch(() => {})
  }, [conversations])

  // Export all conversations
  const handleExportAll = useCallback(() => {
    const all = JSON.stringify(conversations, null, 2)
    downloadFile(all, `labclaw-chats-${new Date().toISOString().slice(0, 10)}.json`, 'application/json')
  }, [conversations])

  // Clear old conversations (keep last 10)
  const handleClearOld = useCallback(() => {
    const sorted = [...conversations].sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    )
    const kept = sorted.slice(0, 10)
    persistConversations(kept)
    if (activeConvoId && !kept.find((c) => c.id === activeConvoId)) {
      setTurns([])
      setActiveConvoId(null)
    }
  }, [conversations, activeConvoId, persistConversations])

  // Submit question
  const submitQuestion = async (nextQuestion: string) => {
    const trimmed = nextQuestion.trim()
    if (!trimmed || submitting) return
    if (trimmed.length > MAX_QUESTION_LENGTH) {
      const message = `Question too long. Keep it under ${MAX_QUESTION_LENGTH} characters.`
      setLocalError(message)
      onError(message)
      return
    }

    setSubmitting(true)
    setLocalError(null)

    // Create conversation if none active
    let convoId = activeConvoId
    if (!convoId) {
      convoId = generateId()
      setActiveConvoId(convoId)
    }

    const turnId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setTurns((current) => [
      ...current,
      { id: turnId, question: trimmed, status: 'loading' },
    ])
    setQuestion('')

    try {
      const response = (await ask.query(buildContextualQuestion(turnsRef.current, trimmed))) as AskResponse
      setTurns((current) => {
        const updated = current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: 'done' as const,
                answer: response.answer,
                source: response.source,
                sql: response.sql,
                evidence: response.raw_results ?? [],
                rowCount: response.row_count,
              }
            : turn,
        )
        // Save to storage after state update
        setTimeout(() => saveCurrentConversation(updated, convoId), 0)
        return updated
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ask AI failed'
      const friendly =
        message === 'Unauthorized'
          ? 'Session expired. Please sign in again.'
          : message
      setLocalError(friendly)
      onError(friendly)
      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: 'error' as const,
                error: friendly,
              }
            : turn,
        ),
      )
    } finally {
      setSubmitting(false)
    }
  }

  const hasConversation = turns.length > 0

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-white">
      {/* Chat History Sidebar */}
      <ChatSidebar
        conversations={conversations}
        activeId={activeConvoId}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSelectConversation={loadConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRenameConversation}
        onExportConversation={handleExportConversation}
        onCopyConversation={handleCopyConversation}
        storageWarning={storageWarning}
        onClearOld={handleClearOld}
        onExportAll={handleExportAll}
        mobileOpen={sidebarMobileOpen}
        onMobileClose={() => setSidebarMobileOpen(false)}
      />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile sidebar toggle */}
        <div className="md:hidden flex items-center px-4 py-2 border-b border-gray-100">
          <button
            type="button"
            onClick={() => setSidebarMobileOpen(true)}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <Menu className="size-5" />
          </button>
          <span className="ml-2 text-sm font-medium text-gray-700">Chat History</span>
        </div>

        {/* Scrollable conversation area */}
        <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto">
          <div className="max-w-3xl mx-auto w-full px-6">
            {!hasConversation ? (
              /* Empty state - centered welcome */
              <div className="flex flex-col items-center justify-center min-h-[60vh] pt-16">
                <div className="size-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-6">
                  <Bot className="size-8 text-primary" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 tracking-tight mb-2">
                  Ask the lab manager like a scientist
                </h2>
                <p className="text-sm text-gray-500 mb-10 max-w-md text-center leading-6">
                  Ask about inventory, orders, vendors, and lab operations. Answers are grounded in your live lab data.
                </p>

                {/* 2x2 prompt cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
                  {SUGGESTED_PROMPTS.map(({ icon: Icon, text, color }) => (
                    <button
                      key={text}
                      type="button"
                      onClick={() => {
                        setQuestion(text)
                        void submitQuestion(text)
                      }}
                      className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-4 text-left transition-all hover:border-primary/40 hover:shadow-md hover:bg-primary/[0.02] group"
                    >
                      <Icon className={`size-5 mt-0.5 shrink-0 ${color} opacity-70 group-hover:opacity-100 transition-opacity`} />
                      <span className="text-sm text-gray-700 leading-snug">{text}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* Conversation turns */
              <div className="py-6 space-y-6">
                {turns.map((turn) => (
                  <div key={turn.id} className="space-y-4">
                    {/* User message - right aligned */}
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl bg-primary px-4 py-3">
                        <p className="text-sm leading-6 text-white">{turn.question}</p>
                      </div>
                    </div>

                    {/* AI response - left aligned */}
                    <div className="flex justify-start gap-3">
                      <div className="size-8 rounded-full bg-gray-100 flex items-center justify-center shrink-0 mt-1">
                        <Bot className="size-4 text-gray-500" />
                      </div>
                      <div className="max-w-[85%]">
                        {turn.status === 'loading' && (
                          <div className="flex items-center gap-3 text-sm text-gray-500 py-2">
                            <span className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                            Searching the lab data...
                          </div>
                        )}

                        {turn.status === 'error' && (
                          <div className="rounded-xl bg-red-50 border border-red-100 px-4 py-3">
                            <p className="text-sm leading-6 text-red-600">
                              {turn.error ?? 'Ask AI failed.'}
                            </p>
                          </div>
                        )}

                        {turn.status === 'done' && (
                          <div>
                            <SimpleMarkdown text={turn.answer ?? ''} />
                            <SQLDetail
                              sql={turn.sql}
                              evidence={turn.evidence ?? []}
                              source={turn.source}
                              rowCount={turn.rowCount}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Fixed bottom input area */}
        <div className="shrink-0 border-t border-gray-100 bg-white">
          <div className="max-w-3xl mx-auto w-full px-6 py-4">
            {localError && (
              <div className="mb-3 rounded-xl bg-red-50 border border-red-100 px-4 py-2.5 text-sm text-red-600">
                {localError}
              </div>
            )}

            {latestHint && (
              <div className="mb-2 text-xs text-gray-400 text-center">{latestHint}</div>
            )}

            <div className="relative">
              <textarea
                value={question}
                onChange={(e) => {
                  setQuestion(e.target.value)
                  setLocalError(null)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void submitQuestion(question)
                  }
                }}
                placeholder="Ask anything about your lab..."
                rows={1}
                maxLength={MAX_QUESTION_LENGTH}
                className="w-full rounded-2xl border border-gray-200 bg-white px-5 py-3.5 pr-14 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary focus:ring-2 focus:ring-primary/20 resize-none shadow-sm transition-shadow focus:shadow-md"
                style={{ minHeight: '52px', maxHeight: '160px' }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = Math.min(target.scrollHeight, 160) + 'px'
                }}
              />
              <button
                type="button"
                onClick={() => submitQuestion(question)}
                disabled={!canSubmit}
                className="absolute right-3 bottom-3 inline-flex items-center justify-center size-9 rounded-xl bg-primary text-white transition-all hover:bg-primary/90 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}
              </button>
            </div>

            <div className="flex items-center justify-between mt-2">
              <p className="text-[11px] text-gray-400">
                Powered by AI &middot; Grounded in your lab data
              </p>
              {remainingChars < 200 && (
                <span className="text-[11px] text-amber-500">
                  {remainingChars} characters remaining
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
