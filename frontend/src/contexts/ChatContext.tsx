import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { streamChat, type StreamEvent } from '../api/chat'

// Lifted out of the Chat route on purpose: the route component unmounts on
// every navigation, which used to wipe message history when the user clicked
// Dashboard and came back. Hoisting the state into a provider mounted above
// the <Outlet/> means the conversation persists across route changes for the
// lifetime of the SPA. Refresh still resets -- that's a deliberate v3 line:
// session/local-storage rehydration adds serialization concerns we don't
// need to ship right now.

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  tools: string[]
  error?: string
}

interface ChatContextValue {
  messages: ChatMessage[]
  conversationId: string | null
  streaming: boolean
  send: (text: string) => Promise<void>
  reset: () => void
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const nextIdRef = useRef(1)

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || streaming) return

      const userMessage: ChatMessage = {
        id: nextIdRef.current++,
        role: 'user',
        text: trimmed,
        tools: [],
      }
      const assistantId = nextIdRef.current++
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        text: '',
        tools: [],
      }
      setMessages((prev) => [...prev, userMessage, assistantMessage])
      setStreaming(true)

      try {
        const newConvId = await streamChat({
          message: trimmed,
          conversationId: conversationId ?? undefined,
          onEvent: (event: StreamEvent) => {
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantId) return m
                if (event.type === 'token') return { ...m, text: m.text + event.text }
                if (event.type === 'tool') return { ...m, tools: [...m.tools, event.name] }
                if (event.type === 'error') return { ...m, error: event.message }
                return m
              }),
            )
          },
        })
        if (newConvId) setConversationId(newConvId)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Streaming failed.'
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, error: message } : m)),
        )
      } finally {
        setStreaming(false)
      }
    },
    [conversationId, streaming],
  )

  const reset = useCallback(() => {
    setMessages([])
    setConversationId(null)
    nextIdRef.current = 1
  }, [])

  const value = useMemo<ChatContextValue>(
    () => ({ messages, conversationId, streaming, send, reset }),
    [messages, conversationId, streaming, send, reset],
  )

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    throw new Error('useChat must be used inside <ChatProvider>')
  }
  return ctx
}
