import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { Route } from 'react-router-dom'
import Vehicles from './Vehicles'
import { server } from '../testing/server'
import { renderRoute } from '../testing/render'

function renderVehicles(route = '/vehicles') {
  return renderRoute(<Vehicles />, { path: '/vehicles', route })
}

describe('Vehicles list', () => {
  it('renders one row per vehicle with linked asset numbers', async () => {
    renderVehicles()

    await waitFor(() => expect(screen.getByText('PW-001')).toBeInTheDocument())
    expect(screen.getAllByRole('row')).toHaveLength(4) // header + 3 vehicles
    expect(screen.getByRole('link', { name: 'PW-001' })).toHaveAttribute('href', '/vehicles/1')
    expect(screen.getByText('2019 Chevrolet Silverado 2500')).toBeInTheDocument()
    expect(screen.getByText('42,000')).toBeInTheDocument()
  })

  it('discovers department filter options from the data', async () => {
    renderVehicles()

    await waitFor(() => expect(screen.getByText('PW-001')).toBeInTheDocument())
    const departmentSelect = screen.getByLabelText('Department')
    const optionLabels = Array.from(departmentSelect.querySelectorAll('option')).map(
      (o) => o.textContent,
    )
    expect(optionLabels).toEqual(['All', 'Parks and Recreation', 'Public Works', 'Sanitation'])
  })

  it('filters by status and writes the choice into the URL', async () => {
    renderVehicles()
    await waitFor(() => expect(screen.getByText('PW-001')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'InShop' } })

    // findBy* waits out the refetch the filter change triggers.
    expect(await screen.findByText('PK-014')).toBeInTheDocument()
    expect(screen.queryByText('PW-001')).not.toBeInTheDocument()
  })

  it('filters by department and clears a filter back to All', async () => {
    renderVehicles('/vehicles?status=Active')
    await waitFor(() => expect(screen.getByText('PW-001')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Department'), {
      target: { value: 'Sanitation' },
    })
    expect(await screen.findByText('SN-030')).toBeInTheDocument()
    expect(screen.queryByText('PW-001')).not.toBeInTheDocument()

    // Clearing back to All removes the param (the delete branch).
    fireEvent.change(screen.getByLabelText('Department'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: '' } })
    expect(await screen.findByText('PK-014')).toBeInTheDocument()
  })

  it('changes the fuel filter through the select', async () => {
    renderVehicles()
    await waitFor(() => expect(screen.getByText('PW-001')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Fuel'), { target: { value: 'Electric' } })

    expect(await screen.findByText('SN-030')).toBeInTheDocument()
    expect(screen.queryByText('PW-001')).not.toBeInTheDocument()
  })

  it('initializes filters from the URL (deep-linked fuel filter)', async () => {
    renderVehicles('/vehicles?fuelType=Electric')

    await waitFor(() => expect(screen.getByText('SN-030')).toBeInTheDocument())
    expect(screen.queryByText('PW-001')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Fuel')).toHaveValue('Electric')
  })

  it('shows the empty message when no vehicles match', async () => {
    renderVehicles('/vehicles?status=Retired')

    await waitFor(() =>
      expect(screen.getByText('No vehicles match these filters.')).toBeInTheDocument(),
    )
  })

  it('shows an error banner when the API fails', async () => {
    server.use(http.get('/api/vehicles', () => new HttpResponse(null, { status: 500 })))

    renderVehicles()

    await waitFor(() => expect(screen.getByText("Couldn't load vehicles.")).toBeInTheDocument())
  })

  it('navigates to the vehicle detail route on asset-number click', async () => {
    renderRoute(<Vehicles />, {
      path: '/vehicles',
      route: '/vehicles',
      extraRoutes: <Route path="/vehicles/:id" element={<div>DETAIL PAGE</div>} />,
    })
    await waitFor(() => expect(screen.getByText('PW-001')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('link', { name: 'PW-001' }))

    expect(await screen.findByText('DETAIL PAGE')).toBeInTheDocument()
  })
})
