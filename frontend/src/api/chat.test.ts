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
})
