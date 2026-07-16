import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import Dashboard from './Dashboard'
import { server } from '../testing/server'
import { renderRoute } from '../testing/render'

describe('Dashboard', () => {
  it('renders the four stat cards from the fleet summary', async () => {
    renderRoute(<Dashboard />)

    await waitFor(() => expect(screen.getByText('35')).toBeInTheDocument())
    expect(screen.getByText('Total vehicles')).toBeInTheDocument()
    expect(screen.getByText('29')).toBeInTheDocument() // Active
    expect(screen.getByText('4')).toBeInTheDocument() // InShop
    expect(screen.getByText('2')).toBeInTheDocument() // OutOfService
  })

  it('lists overdue and upcoming maintenance with asset numbers and due info', async () => {
    renderRoute(<Dashboard />)

    await waitFor(() => expect(screen.getByText('#PW-001')).toBeInTheDocument())
    expect(screen.getByText('OilChange')).toBeInTheDocument()
    // Item without a due date renders the em-dash fallback.
    expect(screen.getByText('#PK-014')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    // Upcoming panel content.
    expect(screen.getByText('#SN-030')).toBeInTheDocument()
    expect(screen.getByText('@ 15,000 mi')).toBeInTheDocument()
  })

  it('shows the empty-state line when nothing is overdue', async () => {
    server.use(http.get('/api/maintenance/overdue', () => HttpResponse.json([])))

    renderRoute(<Dashboard />)

    await waitFor(() =>
      expect(screen.getByText('Nothing overdue. Good fleet.')).toBeInTheDocument(),
    )
  })

  it('degrades each panel independently on server errors', async () => {
    server.use(
      http.get('/api/vehicles/summary', () => new HttpResponse(null, { status: 500 })),
      http.get('/api/maintenance/overdue', () => new HttpResponse(null, { status: 500 })),
    )

    renderRoute(<Dashboard />)

    await waitFor(() =>
      expect(screen.getByText("Couldn't load fleet summary.")).toBeInTheDocument(),
    )
    expect(screen.getByText("Couldn't load maintenance data.")).toBeInTheDocument()
    // The upcoming panel still renders its data.
    await waitFor(() => expect(screen.getByText('#SN-030')).toBeInTheDocument())
  })
})
