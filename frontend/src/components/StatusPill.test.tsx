import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StatusPill from './StatusPill'

describe('StatusPill', () => {
  it.each([
    ['Active', 'text-emerald-400'],
    ['InShop', 'text-amber-400'],
    ['OutOfService', 'text-red-400'],
    ['Retired', 'text-gray-400'],
  ])('tones the vehicle status %s', (value, toneClass) => {
    render(<StatusPill value={value} />)
    expect(screen.getByText(value).className).toContain(toneClass)
  })

  it.each([
    ['Open', 'text-amber-400'],
    ['InProgress', 'text-sky-400'],
    ['Completed', 'text-emerald-400'],
    ['Cancelled', 'text-gray-400'],
  ])('tones the work-order status %s', (value, toneClass) => {
    render(<StatusPill value={value} kind="workOrder" />)
    expect(screen.getByText(value).className).toContain(toneClass)
  })

  it.each([
    ['Low', 'text-gray-400'],
    ['Medium', 'text-sky-400'],
    ['High', 'text-amber-400'],
    ['Critical', 'text-red-400'],
  ])('tones the priority %s', (value, toneClass) => {
    render(<StatusPill value={value} kind="priority" />)
    expect(screen.getByText(value).className).toContain(toneClass)
  })

  it('falls back to the neutral tone for an unknown value', () => {
    render(<StatusPill value="SomethingNew" />)
    expect(screen.getByText('SomethingNew').className).toContain('text-gray-400')
  })
})
