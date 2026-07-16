import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Truck } from 'lucide-react'
import StatCard from './StatCard'

describe('StatCard', () => {
  it('renders the label and value', () => {
    render(<StatCard label="Total vehicles" value={35} />)

    expect(screen.getByText('Total vehicles')).toBeInTheDocument()
    expect(screen.getByText('35')).toBeInTheDocument()
  })

  it('applies the tone class to the value', () => {
    render(<StatCard label="Out of service" value={2} tone="danger" icon={Truck} />)

    expect(screen.getByText('2').className).toContain('--color-danger')
  })
})
