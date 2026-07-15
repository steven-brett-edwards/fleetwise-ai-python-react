import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  fleetSummaryWire,
  maintenanceRecordsWire,
  overdueMaintenanceWire,
  upcomingMaintenanceWire,
  vehiclesWire,
  workOrdersWire,
} from './fixtures'

// Default happy-path handlers for every REST endpoint the frontend calls.
// Individual tests override with `server.use(...)` for error / empty cases;
// `afterEach(server.resetHandlers)` in test-setup restores these.
//
// The vehicles + work-orders list handlers apply the same query-param
// filters the FastAPI routes do, so filter tests exercise the real
// param-mapping in api/vehicles.ts (camelCase fuelType -> snake_case
// fuel_type on the wire) end to end.

export const handlers = [
  // Order matters: /vehicles/summary must be registered before /vehicles/:id
  // or "summary" would parse as an id.
  http.get('/api/vehicles/summary', () => HttpResponse.json(fleetSummaryWire)),

  http.get('/api/vehicles', ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    const department = url.searchParams.get('department')
    const fuelType = url.searchParams.get('fuel_type')
    const rows = vehiclesWire.filter(
      (v) =>
        (!status || v.Status === status) &&
        (!department || v.Department === department) &&
        (!fuelType || v.FuelType === fuelType),
    )
    return HttpResponse.json(rows)
  }),

  http.get('/api/vehicles/:id', ({ params }) => {
    const vehicle = vehiclesWire.find((v) => v.Id === Number(params.id))
    return vehicle ? HttpResponse.json(vehicle) : new HttpResponse(null, { status: 404 })
  }),

  http.get('/api/vehicles/:id/maintenance', ({ params }) =>
    HttpResponse.json(maintenanceRecordsWire.filter((r) => r.VehicleId === Number(params.id))),
  ),

  http.get('/api/vehicles/:id/work-orders', ({ params }) =>
    HttpResponse.json(workOrdersWire.filter((wo) => wo.VehicleId === Number(params.id))),
  ),

  http.get('/api/maintenance/overdue', () => HttpResponse.json(overdueMaintenanceWire)),
  http.get('/api/maintenance/upcoming', () => HttpResponse.json(upcomingMaintenanceWire)),

  http.get('/api/work-orders', ({ request }) => {
    const status = new URL(request.url).searchParams.get('status')
    return HttpResponse.json(
      workOrdersWire.filter((wo) => !status || wo.Status === status),
    )
  }),

  http.get('/api/work-orders/:id', ({ params }) => {
    const wo = workOrdersWire.find((w) => w.Id === Number(params.id))
    return wo ? HttpResponse.json(wo) : new HttpResponse(null, { status: 404 })
  }),
]

export const server = setupServer(...handlers)
