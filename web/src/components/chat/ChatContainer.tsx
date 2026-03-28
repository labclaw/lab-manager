import { useState, useRef, useEffect, type FormEvent } from 'react'
import { Send } from 'lucide-react'
import {
  Search,
  Dna,
  Pill,
  FlaskConical,
  PenLine,
  Activity,
} from 'lucide-react'
import {
  type ChatMessage,
  MessageBubble,
} from './ChatMessage'

const QUICK_ACTIONS = [
  { label: 'Search PubMed', icon: Search, query: 'Search PubMed for recent papers on CRISPR base editing', color: 'text-cyan-600', bg: 'bg-cyan-50' },
  { label: 'Protein Lookup', icon: Dna, query: 'Look up protein P04637 in UniProt', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { label: 'Drug Info', icon: Pill, query: 'Find drug information for aspirin in ChEMBL', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { label: 'Experiment Design', icon: FlaskConical, query: 'Design a Western blot experiment to confirm CRISPR knockout', color: 'text-amber-600', bg: 'bg-amber-50' },
  { label: 'Write Methods', icon: PenLine, query: 'Write a Methods section for immunohistochemistry', color: 'text-rose-600', bg: 'bg-rose-50' },
  { label: 'Gene Analysis', icon: Activity, query: 'Analyze gene expression for BRCA1 in single-cell RNA-seq', color: 'text-violet-600', bg: 'bg-violet-50' },
] as const

interface ChatContainerProps {
  messages: ChatMessage[]
  onSend: (text: string) => void
  disabled?: boolean
  quickActions?: readonly typeof QUICK_ACTIONS[number][]
}

export function ChatContainer({ messages, onSend, disabled, quickActions }: ChatContainerProps) {
  const [query, setQuery] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setQuery('')
    inputRef.current?.focus()
  }

  const handleQuickAction = (actionQuery: string) => {
    if (disabled) return
    setQuery(actionQuery)
    inputRef.current?.focus()
  }

  const actions = quickActions ?? QUICK_ACTIONS

  return (
    <div
      className="bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col"
      style={{ maxHeight: '60vh' }}
    >
      {/* Messages */}
      {messages.length > 0 && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-live="polite">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Quick action chips */}
      {messages.length === 0 && (
        <div className="px-4 pt-4 pb-2">
          <div className="flex flex-wrap gap-2">
            {actions.map((action) => {
              const Icon = action.icon
              return (
                <button
                  key={action.label}
                  onClick={() => handleQuickAction(action.query)}
                  disabled={disabled}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${action.color} ${action.bg} hover:opacity-80 transition-opacity disabled:opacity-50`}
                >
                  <Icon className="size-3.5" />
                  {action.label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="border-t border-gray-100 p-4">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask Cloud Brain..."
            disabled={disabled}
            aria-label="Send scientific query"
            className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:bg-gray-50 disabled:text-gray-400"
          />
          <button
            type="submit"
            disabled={disabled || !query.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="size-4" />
            Ask
          </button>
        </form>
      </div>
    </div>
  )
}
