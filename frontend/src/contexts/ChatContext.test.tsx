import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatProvider, useChat } from './ChatContext'
import type { StreamEvent } from '../api/chat'

// The provider owns all chat state; streamChat is the only collaborator.
// Mock it with a controllable implementation: tests capture onEvent to
// emit token/tool/error frames at will, and resolve the returned promise
// to end the turn -- full control over mid-stream states.
vi.mock('../api/chat', () => ({ streamChat: vi.fn() }))

const { streamChat } = await import('../api/chat')
const streamChatMock = vi.mocked(streamChat)

let emit: (event: StreamEvent) => void
let finishTurn: (conversationId: string | null) => void
let rejectTurn: (err: unknown) => void

function wireControllableStream(): void {
  streamChatMock.mockImplementation(({ onEvent }) => {
    emit = onEvent
    return new Promise<string | null>((resolve, reject) => {
      finishTurn = resolve
      rejectTurn = reject
    })
  })
}

function wrapper({ children }: { children: ReactNode }) {
  return <ChatProvider>{children}</ChatProvider>
}

beforeEach(() => {
  streamChatMock.mockReset()
  wireControllableStream()
})

describe('ChatProvider.send', () => {
  it('appends a user message and an empty assistant message, then streams tokens into it', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('How big is the fleet?')
    })

    expect(result.current.streaming).toBe(true)
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0]).toMatchObject({
      role: 'user',
      text: 'How big is the fleet?',
    })
    expect(result.current.messages[1]).toMatchObject({ role: 'assistant', text: '' })

    act(() => {
      emit({ type: 'token', text: 'The fleet has ' })
      emit({ type: 'token', text: '35 vehicles.' })
    })
    expect(result.current.messages[1].text).toBe('The fleet has 35 vehicles.')

    act(() => finishTurn('conv-1'))
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.conversationId).toBe('conv-1')
  })

  it('collects tool events on the assistant message', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('Which are overdue?')
    })
    act(() => {
      emit({ type: 'tool', name: 'search_vehicles' })
      emit({ type: 'tool', name: 'get_overdue_maintenance' })
      emit({ type: 'token', text: 'Two vehicles.' })
      // The done frame carries no payload; the reducer passes it through.
      emit({ type: 'done' })
    })
    act(() => finishTurn('conv-1'))

    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages[1].tools).toEqual([
      'search_vehicles',
      'get_overdue_maintenance',
    ])
  })

  it('threads the follow-up turn with the conversation id from the first turn', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('first')
    })
    act(() => finishTurn('conv-42'))
    await waitFor(() => expect(result.current.conversationId).toBe('conv-42'))

    act(() => {
      void result.current.send('second')
    })
    act(() => finishTurn('conv-42'))
    await waitFor(() => expect(result.current.streaming).toBe(false))

    expect(streamChatMock).toHaveBeenCalledTimes(2)
    expect(streamChatMock.mock.calls[0][0].conversationId).toBeUndefined()
    expect(streamChatMock.mock.calls[1][0].conversationId).toBe('conv-42')
  })

  it('keeps the existing conversation id when a turn returns null', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('first')
    })
    act(() => finishTurn('conv-7'))
    await waitFor(() => expect(result.current.conversationId).toBe('conv-7'))

    act(() => {
      void result.current.send('second')
    })
    act(() => finishTurn(null))
    await waitFor(() => expect(result.current.streaming).toBe(false))

    expect(result.current.conversationId).toBe('conv-7')
  })

  it('records an error event on the assistant message', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('hi')
    })
    act(() => {
      emit({ type: 'error', message: 'model unavailable' })
    })
    act(() => finishTurn(null))

    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages[1].error).toBe('model unavailable')
  })

  it('converts a thrown stream failure into an error on the assistant message', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('hi')
    })
    act(() => rejectTurn(new Error('Chat stream failed: 429')))

    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages[1].error).toBe('Chat stream failed: 429')
  })

  it('ignores blank input', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    await act(() => result.current.send('   '))

    expect(streamChatMock).not.toHaveBeenCalled()
    expect(result.current.messages).toHaveLength(0)
  })

  it('refuses to send while a turn is already streaming', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('first')
    })
    await act(() => result.current.send('second while streaming'))

    expect(streamChatMock).toHaveBeenCalledTimes(1)
    expect(result.current.messages).toHaveLength(2)

    act(() => finishTurn(null))
    await waitFor(() => expect(result.current.streaming).toBe(false))
  })
})

describe('ChatProvider.reset', () => {
  it('clears messages and the conversation id', async () => {
    const { result } = renderHook(() => useChat(), { wrapper })

    act(() => {
      void result.current.send('hello')
    })
    act(() => finishTurn('conv-9'))
    await waitFor(() => expect(result.current.conversationId).toBe('conv-9'))

    act(() => result.current.reset())

    expect(result.current.messages).toHaveLength(0)
    expect(result.current.conversationId).toBeNull()
  })
})

describe('useChat', () => {
  it('throws outside a ChatProvider', () => {
    expect(() => renderHook(() => useChat())).toThrow('useChat must be used inside <ChatProvider>')
  })
})
