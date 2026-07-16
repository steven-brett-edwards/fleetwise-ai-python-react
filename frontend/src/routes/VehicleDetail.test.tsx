import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import VehicleDetail from './VehicleDetail'
import { server } from '../testing/server'
import { renderRoute } from '../testing/render'

function renderDetail(route = '/vehicles/1') {
  return renderRoute(<VehicleDetail />, { path: '/vehicles/:id', route })
}

describe('VehicleDetail', () => {
  it('renders the vehicle header, fields, and notes', async () => {
    renderDetail('/vehicles/1')

    await waitFor(() => expect(screen.getByText('2021 Ford F-150')).toBeInTheDocument())
    expect(screen.getByText('PW-001')).toBeInTheDocument()
    expect(screen.getByText('1FTFW1E50MFA00001')).toBeInTheDocument()
    expect(screen.getByText('Dana Reyes')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Plow package installed.')).toBeInTheDocument()
  })

  it('falls back to an em dash for a vehicle with no assigned driver, and hides notes', async () => {
    renderDetail('/vehicles/2')

    await waitFor(() =>
      expect(screen.getByText('2019 Chevrolet Silverado 2500')).toBeInTheDocument(),
    )
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByText('Notes')).not.toBeInTheDocument()
  })

  it('shows maintenance history by default and work orders on tab switch', async () => {
    renderDetail('/vehicles/1')

    await waitFor(() =>
      expect(screen.getByText('Full synthetic oil change')).toBeInTheDocument(),
    )
    expect(screen.getByText('Rotate + balance')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Work orders' }))

    await waitFor(() => expect(screen.getByText('WO-2026-00019')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'WO-2026-00019' })).toHaveAttribute(
      'href',
      '/work-orders/41',
    )
    expect(screen.getByText('Critical')).toBeInTheDocument()
  })

  it('shows the empty message when a vehicle has no maintenance records', async () => {
    renderDetail('/vehicles/3')

    await waitFor(() =>
      expect(screen.getByText('No maintenance records on file.')).toBeInTheDocument(),
    )
  })

  it('shows the work-orders empty message for a vehicle with none', async () => {
    renderDetail('/vehicles/3')
    await waitFor(() => expect(screen.getByText('2023 Tesla Model 3')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Work orders' }))

    await waitFor(() =>
      expect(screen.getByText('No work orders on file.')).toBeInTheDocument(),
    )
  })

  it('surfaces a work-orders-tab load failure', async () => {
    server.use(
      http.get('/api/vehicles/:id/work-orders', () => new HttpResponse(null, { status: 500 })),
    )

    renderDetail('/vehicles/1')
    await waitFor(() => expect(screen.getByText('2021 Ford F-150')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Work orders' }))

    await waitFor(() =>
      expect(screen.getByText("Couldn't load work orders.")).toBeInTheDocument(),
    )
  })

  it('renders not-found for a non-numeric id without calling the API', () => {
    renderDetail('/vehicles/not-a-number')

    expect(screen.getByText('Vehicle not found')).toBeInTheDocument()
  })

  it('renders not-found when the API 404s', async () => {
    renderDetail('/vehicles/999')

    await waitFor(() => expect(screen.getByText('Vehicle not found')).toBeInTheDocument())
  })

  it('surfaces a maintenance-tab load failure without killing the page', async () => {
    server.use(
      http.get('/api/vehicles/:id/maintenance', () => new HttpResponse(null, { status: 500 })),
    )

    renderDetail('/vehicles/1')

    await waitFor(() =>
      expect(screen.getByText("Couldn't load maintenance records.")).toBeInTheDocument(),
    )
    expect(screen.getByText('2021 Ford F-150')).toBeInTheDocument()
  })
})
