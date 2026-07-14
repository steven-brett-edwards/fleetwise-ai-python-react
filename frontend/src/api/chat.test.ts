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

  it('decodes an escaped literal backslash-n as two characters, not a newline', async () => {
    // Regression for the sequential-replace decode bug (same as the .NET
    // edition's Angular client). A model emitting the two characters
    // `\` + `n` (common in code blocks) is escaped on the wire as `\\n`;
    // decoding `\n` before `\\` corrupted it into backslash + real newline.
    const fetchMock = vi.fn().mockResolvedValue(
      makeStreamResponse([
        'event: token\ndata: use \\\\n for newlines\n\n',
        'event: done\ndata: [DONE]\n\n',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const events: StreamEvent[] = []
    await streamChat({ message: 'hi', onEvent: (e) => events.push(e) })

    expect(events[0]).toEqual({ type: 'token', text: 'use \\n for newlines' })
  })

  it('decodes escaped carriage returns', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeStreamResponse(['event: token\ndata: a\\r\\nb\n\n', 'event: done\ndata: [DONE]\n\n']),
    )
    vi.stubGlobal('fetch', fetchMock)

    const events: StreamEvent[] = []
    await streamChat({ message: 'hi', onEvent: (e) => events.push(e) })

    expect(events[0]).toEqual({ type: 'token', text: 'a\r\nb' })
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
