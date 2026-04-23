import { z } from 'zod'
import { apiGet } from './client'
import { FleetSummarySchema, VehicleSchema, type Vehicle, type FleetSummary } from './schemas'

export interface VehicleFilters {
  status?: string
  department?: string
  fuelType?: string
}

function toQuery(filters?: VehicleFilters): string {
  if (!filters) return ''
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.department) params.set('department', filters.department)
  if (filters.fuelType) params.set('fuel_type', filters.fuelType)
  const s = params.toString()
  return s ? `?${s}` : ''
}

export function getVehicles(filters?: VehicleFilters): Promise<Vehicle[]> {
  return apiGet(`/vehicles${toQuery(filters)}`, (raw) => z.array(VehicleSchema).parse(raw))
}

export function getFleetSummary(): Promise<FleetSummary> {
  return apiGet('/vehicles/summary', (raw) => FleetSummarySchema.parse(raw))
}
