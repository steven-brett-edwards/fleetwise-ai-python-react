import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import WorkOrderDetail from './WorkOrderDetail'
import { renderRoute } from '../testing/render'

function renderDetail(route: string) {
  return renderRoute(<WorkOrderDetail />, { path: '/work-orders/:id', route })
}

describe('WorkOrderDetail', () => {
  it('renders the work order and links to its vehicle once that loads', async () => {
    renderDetail('/work-orders/41')

    await waitFor(() =>
      expect(screen.getByText('Hydraulic lift cylinder failure')).toBeInTheDocument(),
    )
    expect(screen.getByText('WO-2026-00019')).toBeInTheDocument()
    expect(screen.getByText('InProgress')).toBeInTheDocument()
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('R. Chen')).toBeInTheDocument()
    expect(screen.getByText('Parts on order.')).toBeInTheDocument()

    // The vehicle link renders after the second query resolves.
    const vehicleLink = await screen.findByRole('link', { name: /PW-001/ })
    expect(vehicleLink).toHaveAttribute('href', '/vehicles/1')
  })

  it('renders em dashes for the open order nulls and values for the completed one', async () => {
    renderDetail('/work-orders/42')

    await waitFor(() => expect(screen.getByText('Replace serpentine belt')).toBeInTheDocument())
    expect(screen.getByText('2.50')).toBeInTheDocument()
    expect(screen.getByText('$312.40')).toBeInTheDocument()
    // Technician is null on this one.
    expect(screen.getByText('—')).toBeInTheDocument()
    // Null notes: the notes section is absent entirely.
    expect(screen.queryByText('Notes')).not.toBeInTheDocument()
  })

  it('renders not-found for a bad id or a 404', async () => {
    renderDetail('/work-orders/not-a-number')
    expect(screen.getByText('Work order not found')).toBeInTheDocument()
  })

  it('renders not-found when the API has no such order', async () => {
    renderDetail('/work-orders/999')

    await waitFor(() => expect(screen.getByText('Work order not found')).toBeInTheDocument())
  })
})
