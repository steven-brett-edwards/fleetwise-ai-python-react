import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../testing/server'
import { vehiclesWire } from '../testing/fixtures'
import {
  getFleetSummary,
  getVehicleById,
  getVehicleMaintenance,
  getVehicleWorkOrders,
  getVehicles,
} from './vehicles'
import { ApiError } from './client'

describe('getVehicles', () => {
  it('returns the full camelized fleet with no filters', async () => {
    const vehicles = await getVehicles()

    expect(vehicles).toHaveLength(vehiclesWire.length)
    expect(vehicles[0]).toMatchObject({
      id: 1,
      assetNumber: 'PW-001',
      fuelType: 'Gasoline',
      currentMileage: 42000,
    })
  })

  it('maps camelCase fuelType to the snake_case fuel_type wire param', async () => {
    // The default handler filters on `fuel_type`; getting exactly the
    // Diesel truck back proves the param-name mapping is intact.
    const vehicles = await getVehicles({ fuelType: 'Diesel' })

    expect(vehicles).toHaveLength(1)
    expect(vehicles[0].assetNumber).toBe('PK-014')
  })

  it('combines multiple filters into one query string', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/vehicles', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json([])
      }),
    )

    await getVehicles({ status: 'Active', department: 'Public Works' })

    const url = new URL(requestedUrl)
    expect(url.searchParams.get('status')).toBe('Active')
    expect(url.searchParams.get('department')).toBe('Public Works')
    expect(url.searchParams.has('fuel_type')).toBe(false)
  })
})

describe('getFleetSummary', () => {
  it('camelizes the summary counters', async () => {
    const summary = await getFleetSummary()

    expect(summary.totalVehicles).toBe(35)
    expect(summary.byStatus.Active).toBe(29)
    expect(summary.byDepartment['Public Works']).toBe(12)
  })
})

describe('getVehicleById', () => {
  it('returns one camelized vehicle', async () => {
    const vehicle = await getVehicleById(2)

    expect(vehicle.assetNumber).toBe('PK-014')
    expect(vehicle.assignedDriver).toBeNull()
    expect(vehicle.notes).toBeNull()
  })

  it('rejects with ApiError on 404', async () => {
    await expect(getVehicleById(999)).rejects.toBeInstanceOf(ApiError)
  })
})

describe('vehicle sub-resources', () => {
  it('returns maintenance records for the vehicle', async () => {
    const records = await getVehicleMaintenance(1)

    expect(records).toHaveLength(2)
    expect(records[0]).toMatchObject({ maintenanceType: 'OilChange', cost: 89.95 })
    expect(records[1].workOrderId).toBeNull()
  })

  it('returns work orders for the vehicle', async () => {
    const workOrders = await getVehicleWorkOrders(1)

    expect(workOrders).toHaveLength(1)
    expect(workOrders[0].workOrderNumber).toBe('WO-2026-00019')
  })
})
