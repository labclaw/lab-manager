import { useState, useRef, useEffect, type FormEvent } from 'react'
import { Send } from 'lucide-react'
import {
  Search,
  Dna,
  Pill,
  FlaskConical,
  PenLine,
} from 'lucide-react'
import {
  type ChatMessage,
  MessageBubble,
} from './ChatMessage'

const QUICK_ACTIONS = [
  { label: 'Search PubMed', icon: Search, query: 'Search PubMed for recent papers on...', color: 'text-cyan-600', bg: 'bg-cyan-50' },
  { label: 'Protein Lookup', icon: Dna, query: 'Look up protein in UniProt by accession...', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { label: 'Drug Info', icon: Pill, query: 'Find drug information and targets for...', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { label: 'Experiment Design', icon: FlaskConical, query: 'Design an experiment to test...', color: 'text-amber-600', bg: 'bg-amber-50' },
  { label: 'Write Section', icon: PenLine, query: 'Write a Methods section for...', color: 'text-rose-600', bg: 'bg-rose-50' },
]

interface ChatContainerProps {
  messages: ChatMessage[]
  onSend: (text: string) => void
  disabled?: boolean
}

export function ChatContainer({ messages, onSend, disabled }: ChatContainerProps) {
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

  return (
    <div
      className="bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col"
      style={{ maxHeight: messages.length > 0 ? '60vh' : undefined }}
    >
      {/* Messages */}
      {messages.length > 0 && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
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
            {QUICK_ACTIONS.map((action) => {
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
