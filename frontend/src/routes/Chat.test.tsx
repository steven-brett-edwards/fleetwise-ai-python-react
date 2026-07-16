import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Chat from './Chat'
import { ChatProvider } from '../contexts/ChatContext'
import type { StreamEvent } from '../api/chat'

vi.mock('../api/chat', () => ({ streamChat: vi.fn() }))

const { streamChat } = await import('../api/chat')
const streamChatMock = vi.mocked(streamChat)

let emit: (event: StreamEvent) => void
let finishTurn: (conversationId: string | null) => void

beforeEach(() => {
  streamChatMock.mockReset()
  streamChatMock.mockImplementation(({ onEvent }) => {
    emit = onEvent
    return new Promise<string | null>((resolve) => {
      finishTurn = resolve
    })
  })
})

function renderChat() {
  return render(
    <ChatProvider>
      <Chat />
    </ChatProvider>,
  )
}

function sendMessage(text: string): void {
  const input = screen.getByPlaceholderText(/ask about vehicles/i)
  fireEvent.change(input, { target: { value: text } })
  fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })
}

describe('Chat route', () => {
  it('shows the empty state with suggestions, and picking one sends it', async () => {
    renderChat()

    expect(screen.getByText('Ask about the fleet')).toBeInTheDocument()

    fireEvent.click(screen.getByText('What is the anti-idling rule?'))

    expect(streamChatMock).toHaveBeenCalledTimes(1)
    expect(streamChatMock.mock.calls[0][0].message).toBe('What is the anti-idling rule?')

    act(() => finishTurn(null))
    await waitFor(() => expect(screen.getByPlaceholderText(/ask about/i)).toBeEnabled())
  })

  it('sends on Enter, streams tokens into the assistant bubble, and re-enables input', async () => {
    renderChat()

    sendMessage('How big is the fleet?')

    // User bubble appears immediately; assistant shows the thinking
    // placeholder until the first token arrives.
    expect(screen.getByText('How big is the fleet?')).toBeInTheDocument()
    expect(screen.getByText('Thinking…')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/ask about/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /streaming/i })).toBeDisabled()

    act(() => {
      emit({ type: 'token', text: 'The fleet has ' })
      emit({ type: 'token', text: '**35** vehicles.' })
    })
    act(() => finishTurn('conv-1'))

    await waitFor(() => expect(screen.getByPlaceholderText(/ask about/i)).toBeEnabled())
    // Markdown-rendered: the bold segment is its own element.
    expect(screen.getByText('35')).toBeInTheDocument()
    expect(screen.getByText(/vehicles\./)).toBeInTheDocument()
    expect(screen.queryByText('Thinking…')).not.toBeInTheDocument()
  })

  it('renders tool chips above the assistant reply as tool events arrive', async () => {
    renderChat()

    sendMessage('Which are overdue?')
    act(() => {
      emit({ type: 'tool', name: 'search_vehicles' })
      emit({ type: 'tool', name: 'get_overdue_maintenance' })
      emit({ type: 'token', text: 'Two.' })
    })

    expect(screen.getByText('search_vehicles')).toBeInTheDocument()
    expect(screen.getByText('get_overdue_maintenance')).toBeInTheDocument()

    act(() => finishTurn(null))
    await waitFor(() => expect(screen.getByPlaceholderText(/ask about/i)).toBeEnabled())
  })

  it('renders a GFM table from streamed markdown', async () => {
    renderChat()

    sendMessage('list them')
    act(() => {
      emit({
        type: 'token',
        text: '| Asset | Status |\n|---|---|\n| PW-001 | Active |',
      })
    })
    act(() => finishTurn(null))

    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())
    expect(screen.getByRole('columnheader', { name: 'Asset' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'PW-001' })).toBeInTheDocument()
  })

  it('shows a stream error inside the assistant bubble', async () => {
    renderChat()

    sendMessage('hi')
    act(() => {
      emit({ type: 'error', message: 'rate limited' })
    })
    act(() => finishTurn(null))

    await waitFor(() => expect(screen.getByText('Error: rate limited')).toBeInTheDocument())
  })

  it('New chat resets back to the empty state', async () => {
    renderChat()

    sendMessage('hello')
    act(() => {
      emit({ type: 'token', text: 'Hi!' })
    })
    act(() => finishTurn('conv-1'))
    await waitFor(() => expect(screen.getByRole('button', { name: /new chat/i })).toBeEnabled())

    fireEvent.click(screen.getByRole('button', { name: /new chat/i }))

    expect(screen.getByText('Ask about the fleet')).toBeInTheDocument()
    expect(screen.queryByText('Hi!')).not.toBeInTheDocument()
  })

  it('submits via the Send button as well as Enter', async () => {
    renderChat()

    const input = screen.getByPlaceholderText(/ask about/i)
    fireEvent.change(input, { target: { value: 'button send' } })
    fireEvent.submit(screen.getByRole('button', { name: /send/i }).closest('form')!)

    expect(streamChatMock).toHaveBeenCalledTimes(1)
    expect(streamChatMock.mock.calls[0][0].message).toBe('button send')

    act(() => finishTurn(null))
    await waitFor(() => expect(screen.getByPlaceholderText(/ask about/i)).toBeEnabled())
  })

  it('does not submit blank input', () => {
    renderChat()

    const input = screen.getByPlaceholderText(/ask about/i)
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

    expect(streamChatMock).not.toHaveBeenCalled()
    // Send stays disabled with nothing typed.
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })

  it('Shift+Enter does not submit (newline instead)', () => {
    renderChat()

    const input = screen.getByPlaceholderText(/ask about/i)
    fireEvent.change(input, { target: { value: 'multi\nline' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })

    expect(streamChatMock).not.toHaveBeenCalled()
  })
})
