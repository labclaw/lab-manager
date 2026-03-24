import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, Search } from 'lucide-react'
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
  'What orders were received this month?',
  'Which vendors have the most orders?',
  'How many products do we have in inventory?',
  'Which items are expiring soon?',
] as const

const MAX_QUESTION_LENGTH = 2000

function trimForPrompt(text: string, limit: number): string {
  if (limit <= 0) return ''
  return text.length <= limit ? text : text.slice(0, Math.max(0, limit - 1)).trimEnd() + '…'
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

function EmptyChatState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
      <div className="size-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
        <Bot className="size-7 text-primary" />
      </div>
      <div className="space-y-1 max-w-md">
        <h3 className="text-lg font-bold text-gray-900 dark:text-slate-100">Ask the lab manager anything</h3>
        <p className="text-sm text-gray-500 dark:text-slate-500 leading-6">
          Best for inventory, purchasing, and vendor operations questions grounded in live lab records.
        </p>
      </div>
    </div>
  )
}

function EvidenceList({ evidence, source }: Readonly<{ evidence: AskEvidenceRow[]; source?: string }>) {
  if (evidence.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 dark:border-outline bg-gray-50 dark:bg-surface-container-lowest/40 p-5 text-sm text-gray-500 dark:text-slate-500 leading-6">
        {source === 'sql'
          ? 'This answer came from the SQL path. The backend currently summarizes SQL-backed answers instead of exposing raw rows.'
          : 'No evidence rows were returned for this answer.'}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {evidence.slice(0, 3).map((row, idx) => (
        <div
          key={`${idx}-${Object.keys(row).join('-')}`}
          className="rounded-2xl border border-gray-200 dark:border-outline bg-gray-50 dark:bg-surface-container-lowest p-4"
        >
          <div className="flex items-center justify-between gap-3 mb-3">
            <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-slate-500">
              Evidence {idx + 1}
            </span>
            <span className="text-[10px] text-gray-400 dark:text-slate-600">Row preview</span>
          </div>
          <pre className="whitespace-pre-wrap break-words text-xs leading-6 text-gray-700 dark:text-slate-300 overflow-x-auto">
            {formatEvidenceRow(row)}
          </pre>
        </div>
      ))}
      {evidence.length > 3 && (
        <p className="text-xs text-gray-500 dark:text-slate-500">
          Showing 3 of {evidence.length} evidence rows.
        </p>
      )}
    </div>
  )
}

export function AskPage({ onError }: Readonly<AskPageProps>) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<AskTurn[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const transcriptRef = useRef<HTMLDivElement | null>(null)
  const turnsRef = useRef(turns)
  turnsRef.current = turns

  const canSubmit = question.trim().length > 0 && question.length <= MAX_QUESTION_LENGTH && !submitting
  const remainingChars = MAX_QUESTION_LENGTH - question.length

  useEffect(() => {
    const transcript = transcriptRef.current
    if (!transcript) return
    transcript.scrollTo({
      top: transcript.scrollHeight,
      behavior: 'smooth',
    })
  }, [turns])

  const latestHint = useMemo(() => {
    const last = turns[turns.length - 1]
    if (!last) return 'Ready for a question.'
    if (last.status === 'loading') return 'Searching the lab data...'
    if (last.status === 'error') return 'That question needs another pass.'
    return 'Answer grounded in lab data.'
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

  return (
    <div className="max-w-6xl mx-auto h-[calc(100vh-4rem)] flex flex-col gap-6">
      <div className="space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-primary">
          <span className="size-2 rounded-full bg-accent-green" />
          Ask AI
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-slate-100 tracking-tight">
            Ask the lab manager like a scientist
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-gray-500 dark:text-slate-500">
            Suggested prompts, in-page history, and grounded results for inventory, purchasing, and vendor workflows.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => setQuestion(prompt)}
            className="rounded-full border border-gray-200 dark:border-outline bg-white dark:bg-card-dark px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-slate-300 transition-colors hover:border-primary hover:text-primary"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 min-h-0 flex-1">
        <section className="rounded-[28px] border border-gray-200 dark:border-outline bg-white dark:bg-card-dark shadow-sm p-5 flex flex-col gap-4">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-slate-500 mb-2">
              New Question
            </div>
            <label className="block">
              <span className="sr-only">Ask a question</span>
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
                placeholder="What orders from Sigma-Aldrich arrived this month?"
                rows={8}
                maxLength={MAX_QUESTION_LENGTH}
                className="w-full rounded-2xl border border-gray-200 dark:border-outline bg-gray-50 dark:bg-surface-container-lowest px-4 py-3 text-sm text-gray-900 dark:text-slate-100 placeholder:text-gray-400 dark:placeholder:text-slate-500 focus:border-primary focus:ring-1 focus:ring-primary resize-none"
              />
            </label>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => submitQuestion(question)}
              disabled={!canSubmit}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary/85 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Search className="size-4" />
              )}
              Ask AI
            </button>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-gray-500 dark:text-slate-500">{latestHint}</span>
              <span className={`text-[11px] ${remainingChars < 200 ? 'text-amber-400' : 'text-gray-400 dark:text-slate-600'}`}>
                {remainingChars} characters remaining
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 dark:border-outline bg-gray-50 dark:bg-surface-container-lowest/50 p-4 space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-slate-500">
              Grounding
            </div>
            <p className="text-sm text-gray-500 dark:text-slate-400 leading-6">
              Answers are sourced from the lab database through `/api/v1/ask`. This surface is intentionally read-only, and follow-up questions carry recent conversation context forward. Fallback search is narrower than the main SQL path, so operational questions work best.
            </p>
          </div>

          {localError && (
            <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {localError}
            </div>
          )}
        </section>

        <section className="rounded-[28px] border border-gray-200 dark:border-outline bg-white dark:bg-card-dark shadow-sm flex flex-col min-h-0">
          <div className="border-b border-gray-200 dark:border-outline px-5 py-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-gray-900 dark:text-slate-100 uppercase tracking-widest">
                Conversation
              </h3>
              <p className="text-xs text-gray-500 dark:text-slate-500 mt-1">
                {turns.length} turn{turns.length === 1 ? '' : 's'} in this session
              </p>
            </div>
            <span className="text-xs text-gray-400 dark:text-slate-600">Read only</span>
          </div>

          <div ref={transcriptRef} className="flex-1 min-h-0 overflow-y-auto p-5 space-y-4">
            {turns.length === 0 ? (
              <EmptyChatState />
            ) : (
              turns.map((turn) => (
                <div key={turn.id} className="space-y-3">
                  <div className="ml-auto max-w-[85%] rounded-2xl bg-primary/10 border border-primary/20 px-4 py-3">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-primary mb-1">
                      You
                    </div>
                    <p className="text-sm leading-6 text-gray-900 dark:text-slate-100">{turn.question}</p>
                  </div>

                  <div className="max-w-[92%] rounded-2xl border border-gray-200 dark:border-outline bg-gray-50 dark:bg-surface-container-lowest p-4">
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-slate-500">
                        Lab manager
                      </div>
                      {turn.source && (
                        <span className="rounded-full border border-gray-200 dark:border-outline bg-white dark:bg-card-dark px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-slate-400">
                          {turn.source}
                        </span>
                      )}
                    </div>

                    {turn.status === 'loading' && (
                      <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-slate-500">
                        <span className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                        Searching the lab data...
                      </div>
                    )}

                    {turn.status === 'error' && (
                      <div className="space-y-3">
                        <p className="text-sm leading-6 text-red-300">
                          {turn.error ?? 'Ask AI failed.'}
                        </p>
                      </div>
                    )}

                    {turn.status === 'done' && (
                      <div className="space-y-4">
                        <p className="text-sm leading-7 text-gray-900 dark:text-slate-100">
                          {turn.answer}
                        </p>
                        <div className="grid gap-3 md:grid-cols-[160px_1fr]">
                          <div className="rounded-2xl border border-gray-200 dark:border-outline bg-white dark:bg-card-dark px-4 py-3">
                            <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-slate-500">
                              {turn.source === 'search' ? 'Fallback hits' : 'Rows matched'}
                            </div>
                            <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-slate-100">
                              {turn.rowCount ?? (turn.evidence ?? []).length}
                            </div>
                          </div>
                          <div className="space-y-3">
                            {turn.sql && (
                              <div className="rounded-2xl border border-gray-200 dark:border-outline bg-white dark:bg-card-dark p-4">
                                <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-slate-500 mb-2">
                                  SQL Query
                                </div>
                                <pre className="whitespace-pre-wrap break-words text-xs leading-6 text-gray-700 dark:text-slate-300 overflow-x-auto">
                                  {turn.sql}
                                </pre>
                              </div>
                            )}
                            <EvidenceList evidence={turn.evidence ?? []} source={turn.source} />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
