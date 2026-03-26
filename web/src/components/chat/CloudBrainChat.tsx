/**
 * CloudBrainChat — conversational chat section for the Cloud Brain page.
 *
 * ## Integration Guide
 *
 * Replace the "Query input" and "Recent Queries" sections in CloudBrainPage.tsx
 * with this single component:
 *
 * ```tsx
 * // In CloudBrainPage.tsx:
 * import { CloudBrainChat } from '@/components/chat/CloudBrainChat'
 *
 * // Remove: const [query, setQuery] = useState('')
 * // Remove: const [results, setResults] = useState<QueryResult[]>([])
 * // Remove: handleSubmit function
 * // Remove: handleTryExample function
 * // Remove: The "Query input" form block (~lines 507-533)
 * // Remove: The "Query Results" block (~lines 536-571)
 * // Remove: QueryResult interface
 *
 * // Add in their place (between Quick Actions and AI Skills Grid):
 * <CloudBrainChat connected={connected} />
 *
 * // Update Quick Actions onClick to use CloudBrainChat's onTryExample
 * // by either lifting state up or passing a ref.
 * ```
 *
 * The component is self-contained: it manages messages, input, routing,
 * and API calls. The parent only needs to provide the `connected` boolean.
 *
 * ## Dependencies (assumed to exist or be created by other agents)
 *
 * - `@/lib/cloud-brain-router`  — exports `routeQuery()`, `RouteResult`
 * - `@/components/chat/ChatMessage`  — exports `ChatMessage` type + `MessageBubble` component
 * - `@/components/chat/ChatContainer`  — exports `ChatContainer` layout component
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Brain, Dna, FlaskConical, Search, Pill, Activity, PenLine } from 'lucide-react'
import { cn } from '@/lib/utils'
import { routeQuery } from '@/lib/cloud-brain-router'
import type { RouteResult } from '@/lib/cloud-brain-router'
import { MessageBubble } from './ChatMessage'
import type { ChatMessage as ChatMessageType } from './ChatMessage'
import { ChatContainer } from './ChatContainer'

/* ---------- constants ---------- */

const CLOUD_BRAIN_URL = '/brain'

const QUICK_CHIPS = [
  { label: 'Search PubMed', icon: Search, query: 'Search PubMed for recent papers on CRISPR base editing', color: 'text-cyan-600', bg: 'bg-cyan-50' },
  { label: 'Protein Lookup', icon: Dna, query: 'Look up protein P04637 in UniProt', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { label: 'Drug Info', icon: Pill, query: 'Find drug information for aspirin in ChEMBL', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { label: 'Experiment Design', icon: FlaskConical, query: 'Design a Western blot experiment to confirm CRISPR knockout', color: 'text-amber-600', bg: 'bg-amber-50' },
  { label: 'Write Methods', icon: PenLine, query: 'Write a Methods section for immunohistochemistry', color: 'text-rose-600', bg: 'bg-rose-50' },
  { label: 'Gene Analysis', icon: Activity, query: 'Analyze gene expression for BRCA1 in single-cell RNA-seq', color: 'text-violet-600', bg: 'bg-violet-50' },
] as const

/* ---------- types ---------- */

interface CloudBrainChatProps {
  readonly connected: boolean
}

/* ---------- response formatting ---------- */

function formatBrainResponse(data: Record<string, unknown>, route: RouteResult): string {
  // Error handling: check for backend error responses first
  if (data.success === false && data.error) {
    return `**Error:** ${String(data.error)}`
  }
  if (data.success === false) {
    return '**Error:** Unknown error occurred'
  }

  const resultData = data.data as Record<string, unknown> | string | undefined

  // /brain/reason returns { success, data: { answer, ... } }
  if (route.endpoint === '/reason') {
    if (typeof resultData === 'object' && resultData !== null && 'answer' in resultData) {
      return String(resultData.answer)
    }
    if (typeof resultData === 'string') return resultData
    return '```json\n' + JSON.stringify(resultData, null, 2) + '\n```'
  }

  // /brain/write returns { success, data: { text, ... } }
  if (route.endpoint === '/write') {
    if (typeof resultData === 'object' && resultData !== null) {
      const text = (resultData as Record<string, unknown>).text ?? (resultData as Record<string, unknown>).answer
      if (text) return String(text)
    }
    if (typeof resultData === 'string') return resultData
    return '```json\n' + JSON.stringify(resultData, null, 2) + '\n```'
  }

  // /brain/execute returns { success, data: <tool-specific> }
  if (route.endpoint === '/execute') {
    if (typeof resultData === 'string') return resultData

    if (typeof resultData === 'object' && resultData !== null) {
      const obj = resultData as Record<string, unknown>

      // Check for output field
      if (obj.output !== undefined) {
        return typeof obj.output === 'string'
          ? obj.output
          : '```json\n' + JSON.stringify(obj.output, null, 2) + '\n```'
      }

      // Check for result/answer field
      if (obj.result !== undefined) {
        return typeof obj.result === 'string'
          ? obj.result
          : '```json\n' + JSON.stringify(obj.result, null, 2) + '\n```'
      }

      if (obj.answer !== undefined) {
        return String(obj.answer)
      }

      return '```json\n' + JSON.stringify(obj, null, 2) + '\n```'
    }

    return '```json\n' + JSON.stringify(resultData, null, 2) + '\n```'
  }

  return '```json\n' + JSON.stringify(data, null, 2) + '\n```'
}

/* ---------- main component ---------- */

export function CloudBrainChat({ connected }: CloudBrainChatProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [input, setInput] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isSubmitting) return

    // 1. Add user message
    const userMsgId = `msg-${Date.now()}`
    const userMsg: ChatMessageType = {
      id: userMsgId,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    }

    // 2. Route query via NLP router
    const route = routeQuery(trimmed)

    // 3. Add placeholder assistant message
    const assistantId = `msg-${Date.now() + 1}`
    const assistantMsg: ChatMessageType = {
      id: assistantId,
      role: 'assistant',
      content: '',
      toolName: route.toolName,
      toolArgs: route.toolArgs,
      timestamp: Date.now(),
      status: 'loading',
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    setIsSubmitting(true)

    const startTime = performance.now()

    try {
      const res = await fetch(`${CLOUD_BRAIN_URL}${route.endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(route.payload),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)

      const data = await res.json()

      // If execute returns success:false with "not found", retry with /reason
      if (route.endpoint === '/execute' && data.success === false && typeof data.error === 'string' && /not found|unknown tool/i.test(data.error)) {
        const fallbackStart = performance.now()
        const fallbackRes = await fetch(`${CLOUD_BRAIN_URL}/reason`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: trimmed, domain: 'general' }),
        })

        if (!fallbackRes.ok) throw new Error(`HTTP ${fallbackRes.status}: ${fallbackRes.statusText}`)

        const fallbackData = await fallbackRes.json()
        const fallbackDuration = performance.now() - fallbackStart
        const fallbackRoute: RouteResult = { endpoint: '/reason', payload: { question: trimmed, domain: 'general' }, toolName: 'Cloud Brain (fallback)' }

        const content = formatBrainResponse(fallbackData, fallbackRoute)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, status: 'done' as const, content, toolName: 'Cloud Brain (fallback)', duration: fallbackDuration }
              : m,
          ),
        )
        setIsSubmitting(false)
        return
      }

      const duration = performance.now() - startTime
      const content = formatBrainResponse(data, route)

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, status: 'done' as const, content, duration }
            : m,
        ),
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, status: 'error' as const, error: msg }
            : m,
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }, [isSubmitting])

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    handleSubmit(input)
  }

  const handleChipClick = (query: string) => {
    if (connected) {
      handleSubmit(query)
    } else {
      setInput(query)
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col"
         style={{ maxHeight: messages.length > 0 ? '60vh' : undefined }}>
      {/* Messages area */}
      {messages.length > 0 && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Empty state with quick chips */}
      {messages.length === 0 && (
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Brain className="size-4 text-violet-500" />
            <span>Ask a scientific question or try a quick action below</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {QUICK_CHIPS.map((chip) => {
              const Icon = chip.icon
              return (
                <button
                  key={chip.label}
                  onClick={() => handleChipClick(chip.query)}
                  disabled={!connected}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors',
                    connected
                      ? 'border-gray-200 bg-gray-50 text-gray-700 hover:border-primary/30 hover:bg-primary/5 hover:text-primary'
                      : 'border-gray-100 bg-gray-50 text-gray-300 cursor-not-allowed',
                  )}
                >
                  <Icon className={cn('size-3', connected ? chip.color : 'text-gray-300')} />
                  {chip.label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Input pinned at bottom */}
      <div className="border-t border-gray-100 p-4">
        <form onSubmit={handleFormSubmit} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Cloud Brain a scientific question..."
            disabled={!connected || isSubmitting}
            className="flex-1 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/30 disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!connected || !input.trim() || isSubmitting}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
            Ask
          </button>
        </form>
      </div>
    </div>
  )
}
