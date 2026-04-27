import { useEffect, useRef, useState } from 'react'
import { Plus, Send, Sparkles, Wrench } from 'lucide-react'
import clsx from 'clsx'
import Markdown from '../components/Markdown'
import { useChat, type ChatMessage } from '../contexts/ChatContext'

const SUGGESTIONS = [
  'What vehicles does Public Works have?',
  'What maintenance is overdue?',
  'What is the anti-idling rule?',
]

export default function Chat() {
  const { messages, streaming, send, reset } = useChat()
  const [input, setInput] = useState('')
  const scrollerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight
    }
  }, [messages])

  async function submit(text: string) {
    setInput('')
    await send(text)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] max-w-3xl mx-auto">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-[var(--color-accent)]" />
            Chat with the fleet
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Asks the LangGraph ReAct agent. Tool calls stream in as they fire.
            Conversation persists across page navigation.
          </p>
        </div>
        {messages.length > 0 ? (
          <button
            type="button"
            onClick={reset}
            disabled={streaming}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:border-[var(--color-accent)]/40 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Start a fresh conversation"
          >
            <Plus className="h-3 w-3" />
            New chat
          </button>
        ) : null}
      </header>

      <div
        ref={scrollerRef}
        className="flex-1 overflow-y-auto scroll-thin rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-4"
      >
        {messages.length === 0 ? (
          <EmptyState onPick={submit} />
        ) : (
          messages.map((m) => <Bubble key={m.id} message={m} />)
        )}
      </div>

      <form
        className="mt-4 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          void submit(input)
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void submit(input)
            }
          }}
          placeholder="Ask about vehicles, maintenance, or SOPs…"
          rows={1}
          className="flex-1 resize-none rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
          disabled={streaming}
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="inline-flex items-center gap-1 rounded-md bg-[var(--color-accent)] text-black px-4 py-2 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110"
        >
          <Send className="h-4 w-4" />
          {streaming ? 'Streaming…' : 'Send'}
        </button>
      </form>
    </div>
  )
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div className={clsx('max-w-[85%] space-y-2', isUser ? 'items-end' : 'items-start')}>
        {message.tools.length > 0 ? (
          <div className="flex flex-wrap gap-1 mb-1">
            {message.tools.map((name, i) => (
              <span
                key={`${name}-${i}`}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/10 text-[var(--color-accent)] px-2 py-0.5 text-xs"
              >
                <Wrench className="h-3 w-3" />
                {name}
              </span>
            ))}
          </div>
        ) : null}
        <div
          className={clsx(
            'rounded-lg px-4 py-2 text-sm',
            isUser
              ? 'bg-[var(--color-surface-raised)] text-[var(--color-text)] whitespace-pre-wrap'
              : 'bg-[var(--color-surface)] border border-[var(--color-accent)]/30 text-[var(--color-text)]',
          )}
        >
          {isUser ? (
            message.text
          ) : message.text ? (
            <Markdown source={message.text} />
          ) : !message.error ? (
            <span className="text-[var(--color-text-muted)] italic">Thinking…</span>
          ) : null}
          {message.error ? (
            <div className="text-[var(--color-danger)] text-xs mt-2">Error: {message.error}</div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 space-y-4">
      <Sparkles className="h-8 w-8 text-[var(--color-accent)]" />
      <div>
        <div className="font-medium">Ask about the fleet</div>
        <div className="text-sm text-[var(--color-text-muted)]">
          LangGraph ReAct agent · 13 tools · RAG over SOPs · SSE streaming
        </div>
      </div>
      <div className="flex flex-col gap-2 w-full max-w-md">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="text-left rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] hover:border-[var(--color-accent)]/40 hover:text-[var(--color-accent)] px-3 py-2 text-sm transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
