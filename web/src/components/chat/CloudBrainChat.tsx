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

import { useState, useCallback } from 'react'
import { routeQuery } from '@/lib/cloud-brain-router'
import type { RouteResult } from '@/lib/cloud-brain-router'
import type { ChatMessage as ChatMessageType } from './ChatMessage'
import { ChatContainer } from './ChatContainer'

/* ---------- constants ---------- */

const CLOUD_BRAIN_URL = '/brain'

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
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isSubmitting) return

    // 1. Add user message
    const userMsgId = crypto.randomUUID()
    const userMsg: ChatMessageType = {
      id: userMsgId,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    }

    // 2. Route query via NLP router
    const route = routeQuery(trimmed)

    // 3. Add placeholder assistant message
    const assistantId = crypto.randomUUID()
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

  return (
    <ChatContainer
      messages={messages}
      onSend={handleSubmit}
      disabled={!connected || isSubmitting}
    />
  )
}
