import { API_BASE } from './client'

// Matches src/fleetwise/ai/sse.py: backslash-escaped data lines to keep SSE
// frame integrity. Reverse the same three escapes on read. Order matters —
// decode `\\` last so we don't double-unescape.
function unescapeSse(s: string): string {
  return s.replace(/\\n/g, '\n').replace(/\\r/g, '\r').replace(/\\\\/g, '\\')
}

export type StreamEvent =
  | { type: 'token'; text: string }
  | { type: 'tool'; name: string }
  | { type: 'error'; message: string }
  | { type: 'done' }

export interface StreamChatInput {
  message: string
  conversationId?: string
  signal?: AbortSignal
  onEvent: (event: StreamEvent) => void
}

// Parses the raw SSE byte stream into discrete events and invokes the
// caller's handler. Resolves with the conversation id returned via the
// X-Conversation-Id response header so chat can continue the thread.
export async function streamChat({
  message,
  conversationId,
  signal,
  onEvent,
}: StreamChatInput): Promise<string | null> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ Message: message, ConversationId: conversationId ?? null }),
    signal,
  })
  if (!res.ok || !res.body) {
    throw new Error(`Chat stream failed: ${res.status}`)
  }

  const newConversationId = res.headers.get('X-Conversation-Id')

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value

    // SSE frames are separated by blank lines (\n\n).
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const event = parseFrame(frame)
      if (event) onEvent(event)
      if (event?.type === 'done') {
        return newConversationId
      }
    }
  }

  return newConversationId
}

function parseFrame(frame: string): StreamEvent | null {
  let eventName = 'message'
  let data = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      // SSE spec: strip exactly one optional leading space after `data:`.
      // Using `.trimStart()` here (earlier bug) collapsed token whitespace
      // so words rendered glued together ("PublicWorkshasthe...").
      data += line.startsWith('data: ') ? line.slice(6) : line.slice(5)
    }
  }
  if (eventName === 'token') return { type: 'token', text: unescapeSse(data) }
  if (eventName === 'tool') return { type: 'tool', name: data.trim() }
  if (eventName === 'error') return { type: 'error', message: unescapeSse(data) }
  if (eventName === 'done') return { type: 'done' }
  return null
}
