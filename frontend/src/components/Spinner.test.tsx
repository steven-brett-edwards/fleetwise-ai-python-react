import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Spinner from './Spinner'

describe('Spinner', () => {
  it('renders the label when given', () => {
    render(<Spinner label="Loading vehicles…" />)
    expect(screen.getByText('Loading vehicles…')).toBeInTheDocument()
  })

  it('renders without a label', () => {
    const { container } = render(<Spinner />)
    expect(container.querySelector('.animate-spin')).not.toBeNull()
    expect(container.querySelector('span')).toBeNull()
  })
})
