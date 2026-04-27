import { z } from 'zod'
import { apiGet } from './client'
import {
  FleetSummarySchema,
  MaintenanceRecordSchema,
  VehicleSchema,
  WorkOrderSchema,
  type FleetSummary,
  type MaintenanceRecord,
  type Vehicle,
  type WorkOrder,
} from './schemas'

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

export function getVehicleById(id: number): Promise<Vehicle> {
  return apiGet(`/vehicles/${id}`, (raw) => VehicleSchema.parse(raw))
}

export function getVehicleMaintenance(id: number): Promise<MaintenanceRecord[]> {
  return apiGet(`/vehicles/${id}/maintenance`, (raw) =>
    z.array(MaintenanceRecordSchema).parse(raw),
  )
}

export function getVehicleWorkOrders(id: number): Promise<WorkOrder[]> {
  return apiGet(`/vehicles/${id}/work-orders`, (raw) => z.array(WorkOrderSchema).parse(raw))
}
