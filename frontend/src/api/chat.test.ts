import { describe, expect, it, vi } from 'vitest'
import { streamChat, type StreamEvent } from './chat'

function makeStreamResponse(frames: string[]): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame))
      }
      controller.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'X-Conversation-Id': 'conv-xyz',
    },
  })
}

describe('streamChat', () => {
  it('parses token + tool + done events and unescapes newlines', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeStreamResponse([
        'event: tool\ndata: search_vehicles\n\n',
        'event: token\ndata: Line one\\nLine two\n\n',
        'event: done\ndata: [DONE]\n\n',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const events: StreamEvent[] = []
    const conversationId = await streamChat({
      message: 'hi',
      onEvent: (e) => events.push(e),
    })

    expect(conversationId).toBe('conv-xyz')
    expect(events).toEqual([
      { type: 'tool', name: 'search_vehicles' },
      { type: 'token', text: 'Line one\nLine two' },
      { type: 'done' },
    ])
  })

  it('preserves leading spaces inside token frames (no word-glue)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeStreamResponse([
        'event: token\ndata: Public\n\n',
        'event: token\ndata:  Works\n\n',
        'event: token\ndata:  has\n\n',
        'event: done\ndata: [DONE]\n\n',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const events: StreamEvent[] = []
    await streamChat({ message: 'hi', onEvent: (e) => events.push(e) })

    const combined = events
      .filter((e): e is { type: 'token'; text: string } => e.type === 'token')
      .map((e) => e.text)
      .join('')
    expect(combined).toBe('Public Works has')
  })
})

describe('streamChat error handling', () => {
  it('throws on a non-OK response instead of parsing it as a stream', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('rate limited', { status: 429 })),
    )

    await expect(streamChat({ message: 'hi', onEvent: () => {} })).rejects.toThrow(
      'Chat stream failed: 429',
    )
  })

  it('throws when the response has no body', async () => {
    const bodyless = { ok: true, status: 200, body: null, headers: new Headers() }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(bodyless))

    await expect(streamChat({ message: 'hi', onEvent: () => {} })).rejects.toThrow(
      'Chat stream failed: 200',
    )
  })

  it('ignores frames with unknown event names', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeStreamResponse([
        'event: heartbeat\ndata: ignored\n\n',
        'event: token\ndata: hi\n\n',
        'event: done\ndata: [DONE]\n\n',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const events: StreamEvent[] = []
    await streamChat({ message: 'hi', onEvent: (e) => events.push(e) })

    expect(events).toEqual([{ type: 'token', text: 'hi' }, { type: 'done' }])
  })

  it('still resolves the conversation id when the stream ends without a done frame', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeStreamResponse(['event: token\ndata: partial\n\n']))
    vi.stubGlobal('fetch', fetchMock)

    const events: StreamEvent[] = []
    const conversationId = await streamChat({ message: 'hi', onEvent: (e) => events.push(e) })

    expect(conversationId).toBe('conv-xyz')
    expect(events).toEqual([{ type: 'token', text: 'partial' }])
  })
})
