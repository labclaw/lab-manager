import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Brain, Loader2 } from 'lucide-react'
import 'highlight.js/styles/github.css'

export interface ChatMessage {
  readonly id: string
  readonly role: 'user' | 'assistant'
  readonly content: string
  readonly toolName?: string
  readonly toolArgs?: Record<string, unknown>
  readonly duration?: number
  readonly timestamp: number
  readonly status?: 'loading' | 'done' | 'error'
  readonly error?: string
}

export function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] bg-blue-100 text-gray-900 rounded-2xl rounded-br-sm px-4 py-2.5">
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        <p className="text-[10px] text-gray-400 mt-1 text-right">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  )
}

export function AssistantMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex gap-3">
      <div className="size-8 flex items-center justify-center rounded-lg bg-violet-50 shrink-0 mt-1">
        <Brain className="size-4 text-violet-600" />
      </div>
      <div className="max-w-[80%] min-w-0">
        {/* Tool activity indicator */}
        {message.status === 'loading' && message.toolName && (
          <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
            <Loader2 className="size-3 animate-spin" />
            Querying {message.toolName}...
          </div>
        )}
        {message.status === 'done' && message.toolName && (
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-2">
            <span className="text-emerald-500">&#10003;</span>
            {message.toolName} &middot; {((message.duration ?? 0) / 1000).toFixed(1)}s
          </div>
        )}

        {/* Loading shimmer */}
        {message.status === 'loading' && !message.content && (
          <div className="space-y-2 bg-gray-50 rounded-2xl rounded-bl-sm px-4 py-3">
            <div className="h-3 bg-gray-200 rounded animate-pulse w-3/4" />
            <div className="h-3 bg-gray-200 rounded animate-pulse w-1/2" />
            <div className="h-3 bg-gray-200 rounded animate-pulse w-5/6" />
          </div>
        )}

        {/* Markdown content */}
        {message.content && (
          <div className="prose prose-sm max-w-none bg-gray-50 rounded-2xl rounded-bl-sm px-4 py-3">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Error state */}
        {message.status === 'error' && (
          <div className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
            {message.error ?? 'An error occurred'}
          </div>
        )}

        <p className="text-[10px] text-gray-400 mt-1">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  )
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === 'user') return <UserMessage message={message} />
  return <AssistantMessage message={message} />
}
