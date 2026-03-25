import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, Package, ClipboardList, BarChart3, Clock, ChevronDown, Send } from 'lucide-react'
import { ask } from '@/lib/api'
import type { AskEvidenceRow, AskResponse } from '@/lib/api'

interface AskPageProps {
  readonly onError: (msg: string) => void
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

const SUGGESTED_PROMPTS = [
  { icon: Package, text: 'What orders were received this month?', color: 'text-blue-600' },
  { icon: BarChart3, text: 'Which vendors have the most orders?', color: 'text-violet-600' },
  { icon: ClipboardList, text: 'How many products do we have in inventory?', color: 'text-emerald-600' },
  { icon: Clock, text: 'Which items are expiring soon?', color: 'text-amber-600' },
] as const

const MAX_QUESTION_LENGTH = 2000

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

function formatEvidenceRow(row: AskEvidenceRow): string {
  return JSON.stringify(row, null, 2)
}

/** Render simple markdown: **bold**, *italic*, and `- list items` */
function SimpleMarkdown({ text }: Readonly<{ text: string }>) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!
    const trimmed = line.trim()

    // Render list items
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

function renderInline(text: string): React.ReactNode {
  // Replace **bold** and *italic*
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

export function AskPage({ onError }: Readonly<AskPageProps>) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<AskTurn[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const turnsRef = useRef(turns)
  turnsRef.current = turns

  const canSubmit = question.trim().length > 0 && question.length <= MAX_QUESTION_LENGTH && !submitting
  const remainingChars = MAX_QUESTION_LENGTH - question.length

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

    const turnId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setTurns((current) => [
      ...current,
      { id: turnId, question: trimmed, status: 'loading' },
    ])
    setQuestion('')

    try {
      const response = (await ask.query(buildContextualQuestion(turnsRef.current, trimmed))) as AskResponse
      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: 'done',
                answer: response.answer,
                source: response.source,
                sql: response.sql,
                evidence: response.raw_results ?? [],
                rowCount: response.row_count,
              }
            : turn,
        ),
      )
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
                status: 'error',
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
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-white">
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
  )
}
