import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import WorkOrders from './WorkOrders'
import { server } from '../testing/server'
import { renderRoute } from '../testing/render'

function renderList(route = '/work-orders') {
  return renderRoute(<WorkOrders />, { path: '/work-orders', route })
}

describe('WorkOrders list', () => {
  it('renders rows with status/priority pills and cost fallback', async () => {
    renderList()

    await waitFor(() => expect(screen.getByText('WO-2026-00019')).toBeInTheDocument())
    // Scope to the table -- the status select's options carry the same text.
    const table = within(screen.getByRole('table'))
    expect(table.getByText('InProgress')).toBeInTheDocument()
    expect(table.getByText('Critical')).toBeInTheDocument()
    // Null technician and null cost render em dashes (one per column).
    expect(table.getAllByText('—').length).toBeGreaterThanOrEqual(2)
    expect(table.getByText('$312.40')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'WO-2026-00023' })).toHaveAttribute(
      'href',
      '/work-orders/42',
    )
  })

  it('filters by status via the select and the URL', async () => {
    renderList()
    await waitFor(() => expect(screen.getByText('WO-2026-00019')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'Completed' } })

    // findBy* waits out the refetch the filter change triggers.
    expect(await screen.findByText('WO-2026-00023')).toBeInTheDocument()
    expect(screen.queryByText('WO-2026-00019')).not.toBeInTheDocument()
  })

  it('clears the status filter back to All (param delete branch)', async () => {
    renderList('/work-orders?status=Completed')
    await waitFor(() => expect(screen.getByText('WO-2026-00023')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: '' } })

    expect(await screen.findByText('WO-2026-00019')).toBeInTheDocument()
    expect(screen.getByText('WO-2026-00023')).toBeInTheDocument()
  })

  it('deep-links a status filter from the URL', async () => {
    renderList('/work-orders?status=InProgress')

    await waitFor(() => expect(screen.getByText('WO-2026-00019')).toBeInTheDocument())
    expect(screen.queryByText('WO-2026-00023')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toHaveValue('InProgress')
  })

  it('shows the empty message when the filter matches nothing', async () => {
    renderList('/work-orders?status=Cancelled')

    await waitFor(() =>
      expect(screen.getByText('No work orders match this filter.')).toBeInTheDocument(),
    )
  })

  it('shows an error banner when the API fails', async () => {
    server.use(http.get('/api/work-orders', () => new HttpResponse(null, { status: 500 })))

    renderList()

    await waitFor(() =>
      expect(screen.getByText("Couldn't load work orders.")).toBeInTheDocument(),
    )
  })
})
